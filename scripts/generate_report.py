"""
generate_report.py — 读取最新 JSON 数据，用 Jinja2 模板渲染报告

输出：
  docs/reports/<week>.html  — 卡片式双语 HTML（GitHub Pages）
  reports/<week>.md         — Markdown 存档
  docs/index.html           — 首页（自动维护期刊列表）
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

# ─── 期刊颜色配置 ────────────────────────────────────────────────────────────

JOURNAL_COLOR_MAP = {
    "Nature":              "#1B5E20",
    "Nat Biotechnol":      "#2E7D32",
    "Nat Chem Biol":       "#388E3C",
    "Nat Methods":         "#43A047",
    "Nat Chem":            "#66BB6A",
    "Nat Struct Mol Biol": "#81C784",
    "Nat Commun":          "#A5D6A7",
    "Cell":                "#0D47A1",
    "Cell Syst":           "#1565C0",
    "Cell Chem Biol":      "#1976D2",
    "Science":             "#E65100",
    "Sci Adv":             "#F57C00",
}

DEFAULT_COLOR = "#607D8B"


def _journal_color(journal: str) -> str:
    journal_lc = journal.lower()
    for key, color in JOURNAL_COLOR_MAP.items():
        if key.lower() in journal_lc:
            return color
    return DEFAULT_COLOR


def _journal_family(journal: str) -> str:
    j = journal.lower()
    if "nat" in j or "nature" in j:
        return "nature"
    if "cell" in j:
        return "cell"
    if "sci" in j or "science" in j:
        return "science"
    return "other"


# ─── 数据准备 ─────────────────────────────────────────────────────────────────

def enrich_papers(papers: list[dict]) -> list[dict]:
    """注入前端渲染所需的衍生字段。"""
    for p in papers:
        journal = p.get("journal", "")
        p["journal_color"] = _journal_color(journal)
        p["family"] = _journal_family(journal)
    return papers


def load_latest(data_dir: Path) -> tuple[dict, Path] | None:
    json_files = sorted(data_dir.glob("*.json"), reverse=True)
    if not json_files:
        return None
    target = json_files[0]
    with open(target, encoding="utf-8") as f:
        data = json.load(f)
    return data, target


# ─── 渲染 ────────────────────────────────────────────────────────────────────

def build_context(data: dict) -> dict:
    papers = enrich_papers(data.get("papers", []))

    nature_papers = [p for p in papers if p["family"] == "nature"]
    cell_papers   = [p for p in papers if p["family"] == "cell"]
    science_papers = [p for p in papers if p["family"] == "science"]
    other_papers  = [p for p in papers if p["family"] == "other"]

    unique_journals = sorted({p["journal"] for p in papers})
    translated_count = sum(1 for p in papers if p.get("abstract_zh"))

    return {
        "week":              data.get("week", ""),
        "generated_at":      datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "date_range":        data.get("date_range", {}),
        "total":             len(papers),
        "translated_count":  translated_count,
        "unique_journals":   unique_journals,
        "papers":            papers,
        "nature_papers":     nature_papers,
        "cell_papers":       cell_papers,
        "science_papers":    science_papers,
        "other_papers":      other_papers,
    }


def render_html(context: dict, env: Environment, out_dir: Path) -> Path:
    tmpl = env.get_template("report.html.j2")
    html = tmpl.render(**context)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{context['week']}.html"
    path.write_text(html, encoding="utf-8")
    return path


def render_markdown(context: dict, env: Environment, out_dir: Path) -> Path:
    tmpl = env.get_template("report.md.j2")
    md = tmpl.render(**context)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{context['week']}.md"
    path.write_text(md, encoding="utf-8")
    return path


def render_index(all_data_files: list[Path], env: Environment, docs_dir: Path) -> Path:
    """重新生成 docs/index.html，包含所有历史周报的链接。"""
    weeks = []
    for fp in sorted(all_data_files, reverse=True):
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        weeks.append({
            "week":       d.get("week", fp.stem),
            "total":      d.get("total", 0),
            "date_range": d.get("date_range", {}),
            "url":        f"reports/{d.get('week', fp.stem)}.html",
        })

    tmpl = env.get_template("index.html.j2")
    html = tmpl.render(
        weeks=weeks,
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )
    docs_dir.mkdir(exist_ok=True)
    path = docs_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


# ─── 主流程 ───────────────────────────────────────────────────────────────────

def main():
    data_dir = Path("data/papers")
    result = load_latest(data_dir)
    if result is None:
        print("[报告] data/papers/ 中无数据文件，请先运行 collect_papers.py")
        sys.exit(0)

    data, data_path = result
    context = build_context(data)
    week = context["week"]

    env = Environment(loader=FileSystemLoader("templates"), autoescape=False)

    # HTML 报告
    html_path = render_html(context, env, Path("docs/reports"))
    print(f"[报告] HTML → {html_path}")

    # Markdown 报告
    md_path = render_markdown(context, env, Path("reports"))
    print(f"[报告] Markdown → {md_path}")

    # 更新首页
    all_data_files = sorted(data_dir.glob("*.json"), reverse=True)
    index_path = render_index(all_data_files, env, Path("docs"))
    print(f"[报告] 首页 → {index_path}")

    print(f"\n[报告] 完成 {week}：共 {context['total']} 篇，已翻译 {context['translated_count']} 篇")


if __name__ == "__main__":
    main()
