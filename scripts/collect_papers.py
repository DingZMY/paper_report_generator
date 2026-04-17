"""
collect_papers.py — 从 PubMed 采集系统/合成生物学领域顶刊论文

使用 NCBI E-utilities API：
  esearch → 获取符合条件的 PMID 列表
  efetch  → 批量获取论文详情（XML 格式）

输出：data/papers/YYYY-WW.json
"""

import os
import json
import time
import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

# ─── 配置 ──────────────────────────────────────────────────────────────────────

PUBMED_API_KEY = os.getenv("PUBMED_API_KEY", "")
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL_NAME = "bio-digest"
TOOL_EMAIL = "bio-digest@github.com"

# 目标期刊（PubMed Journal Title Abbreviation [ta]）
JOURNALS = [
    # Nature 系列
    "Nature",
    "Nat Biotechnol",
    "Nat Chem Biol",
    "Nat Methods",
    "Nat Chem",
    "Nat Commun",
    "Nat Phys",
    # Cell 系列
    "Cell",
    "Cell Syst",
    "Cell Chem Biol",
    # Science 系列
    "Science",
    "Sci Adv",
    # 理论/定量生物学专刊
    "Mol Syst Biol",        # Molecular Systems Biology
    "PLoS Comput Biol",     # PLoS Computational Biology
    "PLoS Biol",
    "Elife",
    # 物理/生物物理
    "Phys Rev Lett",        # Physical Review Letters
    "Biophys J",            # Biophysical Journal
    # 核酸/基因工程
    "Nucleic Acids Res",    # Nucleic Acids Research
    "ACS Synth Biol",       # ACS Synthetic Biology
]

# ── 主题条款：聚焦系统/合成生物学 + 理论生物物理 ──────────────────────────────
# 正向匹配：偏物理/理论方向，兼容 omics 方法开发类文章
# 原则：关键词必须足够领域特异；过于通用的词（machine learning / algorithm /
#       nonequilibrium 等）移至排除词或删去，避免引入材料、气候、电子等噪声。
TOPIC_INCLUDE = (
    # MeSH 主题词（领域特异性高）
    '"Synthetic Biology"[MeSH] OR "Systems Biology"[MeSH] '
    'OR "Biophysics"[MeSH] OR "Biophysical Phenomena"[MeSH] '
    # 系统 / 合成生物学
    'OR "synthetic biology"[tiab] OR "systems biology"[tiab] '
    'OR "gene circuit"[tiab] OR "genetic circuit"[tiab] '
    'OR "gene regulatory network"[tiab] OR "biological network"[tiab] '
    'OR "metabolic flux"[tiab] OR "metabolic engineering"[tiab] '
    'OR "cell-free"[tiab] OR "optogenetics"[tiab] '
    'OR "CRISPR"[tiab] OR "genome editing"[tiab] '
    'OR "protein design"[tiab] OR "de novo protein"[tiab] '
    # 理论 / 计算 / 物理（生物领域特异的措辞）
    'OR "mathematical model"[tiab] OR "computational model"[tiab] '
    'OR "theoretical model"[tiab] OR "biophysical model"[tiab] '
    'OR "stochastic"[tiab] OR "noise in gene expression"[tiab] '
    'OR "quantitative biology"[tiab] OR "theoretical biophysics"[tiab] '
    'OR "statistical mechanics"[tiab] '
    'OR "information theory"[tiab] OR "mutual information"[tiab] '
    'OR "entropy production"[tiab] '
    'OR "free energy landscape"[tiab] OR "energy landscape"[tiab] '
    'OR "dynamical systems"[tiab] OR "bifurcation"[tiab] '
    'OR "reaction-diffusion"[tiab] OR "Turing pattern"[tiab] '
    'OR "active matter"[tiab] OR "living matter"[tiab] '
    'OR "self-organization"[tiab] '
    # single-molecule: keep biophysics-specific phrasing, avoid sequencing/biochemistry
    'OR "single-molecule imaging"[tiab] OR "single-molecule tracking"[tiab] '
    'OR "single-molecule force"[tiab] OR "single-molecule kinetics"[tiab] '
    'OR "molecular motor"[tiab] '
    'OR "force generation"[tiab] OR "mechanobiology"[tiab] '
    'OR "membrane tension"[tiab] OR "cytoskeletal dynamics"[tiab] '
)
# 负向排除：非生物物理领域 + 纯描述性 omics + 结构解析 + 临床
TOPIC_EXCLUDE = (
    # 非生物的凝聚态 / 材料科学
    '"thermoelectric"[tiab] OR "solar cell"[tiab] OR "perovskite"[tiab] '
    'OR "magnon"[tiab] OR "dichalcogenide"[tiab] '
    'OR "memristor"[tiab] OR "Ising machine"[tiab] '
    'OR "titanium alloy"[tiab] OR "metal alloy"[tiab] '
    # 非生物的电子 / 计算硬件
    'OR "CMOS"[tiab] OR "probabilistic computing"[tiab] '
    'OR "random telegraph noise"[tiab] '
    # 单分子磁体（区别于生物学单分子研究）
    'OR "single-molecule magnet"[tiab] '
    # 地球 / 气候科学
    'OR "sea level"[tiab] OR "land subsidence"[tiab] '
    'OR "surface albedo"[tiab] OR "climate model"[tiab] '
    # 非生物工程 / 机器人
    'OR "wearable robotics"[tiab] OR "wearable robot"[tiab] '
    'OR "artificial tendon"[tiab] OR "artificial muscle"[tiab] '
    # 其他非目标
    'OR "asteroid"[tiab] OR "meteorite"[tiab] '
    # 纯结构解析（非理论/动力学）
    'OR "cryo-EM structure"[tiab] OR "crystal structure"[tiab] '
    'OR "X-ray crystallography"[tiab] OR "structure determination"[tiab] '
    'OR "cryo-electron tomography"[tiab] '
    # 纯描述性 omics 普查
    'OR "transcriptomic landscape"[tiab] OR "genomic landscape"[tiab] '
    'OR "epigenomic landscape"[tiab] OR "proteomic landscape"[tiab] '
    'OR "single-cell atlas"[tiab] OR "cell atlas"[tiab] '
    'OR "whole genome sequencing"[tiab] OR "whole exome"[tiab] '
    'OR "metagenomics survey"[tiab] OR "metagenomic survey"[tiab] '
    # 非目标临床方向
    'OR "clinical trial"[tiab] OR "randomized controlled"[tiab] '
    'OR "case report"[tiab] OR "cohort study"[tiab] '
    'OR "Mendelian randomization"[tiab] '
    # 纯 omics 技术（非方法论文）
    'OR "single-molecule sequencing"[tiab] '
    # 天然产物普查
    'OR "biosynthetic survey"[tiab] OR "secondary metabolite survey"[tiab] '
    # 无机 / 化学模拟酶
    'OR "nuclease-mimicking"[tiab] OR "enzyme-mimicking"[tiab] '
    # 种群遗传学控制（基因驱动驱虫，非生物物理）
    'OR "population suppression"[tiab] OR "gene drive"[tiab]'
)

# 仅保留 Research Article（排除 Review、Comment、Editorial、News 等）
ARTICLE_TYPE_CLAUSE = (
    '"Journal Article"[pt] '
    'NOT "Review"[pt] '
    'NOT "Comment"[pt] '
    'NOT "Editorial"[pt] '
    'NOT "News"[pt] '
    'NOT "Letter"[pt]'
)

# ── Python 内容后过滤 ────────────────────────────────────────────────────────
# 仅当 PubMed 查询因关键词共现无法精准排除时，在 Python 层级对标题做额外过滤。
_TITLE_EXCLUDE_SUBSTRINGS = [
    # 癌症/白血病临床应用（误由 single-molecule tracking 命中）
    "leukemogenic",
    "leukemia",
    # 高血压药理（误匹配 synthetic biology 关键词）
    "hypertension",
    "angiotensin",
    # 天然产物普查（biosynthetic survey 在 PubMed tiab 中无法被 NOT 精准捕获）
    "biocontrol fungi",
    "hypocrealean",
    # 寄生虫生物学（与系统/计算生物学无关）
    "Plasmodium falciparum",
    "Plasmodium",
    # CRISPR-Cas9 的结构/甲基化机制研究（偏生化/结构，非工程/系统方向）
    "methylation-sensitive editing",
]


def _is_on_topic(paper: dict) -> bool:
    """Python 层面的二次过滤：标题中含有排除子串则返回 False。"""
    title_lower = paper.get("title", "").lower()
    for substr in _TITLE_EXCLUDE_SUBSTRINGS:
        if substr.lower() in title_lower:
            print(f"  [后过滤] 命中排除规则（'{substr}'）：{paper['title'][:60]}")
            return False
    return True


# 不应被收录的 publication type（XML 解析时二次过滤）
EXCLUDED_PUB_TYPES = {
    "review", "comment", "editorial", "letter", "news", "retraction of publication",
    "published erratum", "expression of concern",
}

REQUEST_DELAY = 0.4   # 无 API Key 时 3 req/s；有 Key 时可调低


# ─── 查询构建 ──────────────────────────────────────────────────────────────────

def build_query(days_back: int = 7) -> tuple[str, str, str]:
    today = datetime.utcnow()
    start = today - timedelta(days=days_back)
    journal_clause = " OR ".join(f'"{j}"[ta]' for j in JOURNALS)
    query = (
        f"({journal_clause})"
        f" AND ({TOPIC_INCLUDE})"
        f" NOT ({TOPIC_EXCLUDE})"
        f" AND ({ARTICLE_TYPE_CLAUSE})"
    )
    return query, start.strftime("%Y/%m/%d"), today.strftime("%Y/%m/%d")


# ─── E-utilities 调用 ─────────────────────────────────────────────────────────

def _base_params() -> dict:
    params = {"tool": TOOL_NAME, "email": TOOL_EMAIL}
    if PUBMED_API_KEY:
        params["api_key"] = PUBMED_API_KEY
    return params


def esearch(query: str, mindate: str, maxdate: str, retmax: int = 200) -> list[str]:
    params = {
        **_base_params(),
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "retmode": "json",
        "sort": "pub_date",
        "datetype": "pdat",
        "mindate": mindate,
        "maxdate": maxdate,
    }
    # Use POST to avoid 414 URI Too Long when the query is large
    resp = requests.post(f"{EUTILS_BASE}/esearch.fcgi", data=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    result = data.get("esearchresult", {})
    count = int(result.get("count", 0))
    ids = result.get("idlist", [])
    print(f"  PubMed 命中：{count} 条，本次取回 {len(ids)} 条")
    return ids


def efetch(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    params = {
        **_base_params(),
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml",
    }
    resp = requests.get(f"{EUTILS_BASE}/efetch.fcgi", params=params, timeout=60)
    resp.raise_for_status()
    return _parse_pubmed_xml(resp.text)


# ─── XML 解析 ─────────────────────────────────────────────────────────────────

def _text(el) -> str:
    """递归提取元素的全部文本（含子标签）。"""
    return "".join(el.itertext()) if el is not None else ""


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print(f"  XML 解析错误：{e}", file=sys.stderr)
        return []

    papers = []
    for article in root.findall(".//PubmedArticle"):
        p: dict = {}

        # PMID
        p["pmid"] = _text(article.find(".//PMID"))

        # 标题
        p["title"] = _text(article.find(".//ArticleTitle")).strip()

        # 期刊缩写
        iso = article.find(".//ISOAbbreviation")
        journal_full = article.find(".//Journal/Title")
        p["journal"] = _text(iso) if iso is not None else _text(journal_full)

        # 作者列表（最多显示 6 位，之后用 et al.）
        authors = []
        for author in article.findall(".//Author"):
            last = author.findtext("LastName", "")
            fore = author.findtext("ForeName", "")
            if last:
                authors.append(f"{last} {fore}".strip())
        if len(authors) > 6:
            p["authors"] = authors[:6] + ["et al."]
        else:
            p["authors"] = authors

        # 摘要
        abstract_parts = article.findall(".//AbstractText")
        if abstract_parts:
            chunks = []
            for part in abstract_parts:
                label = part.get("Label", "")
                text = _text(part)
                chunks.append(f"{label}: {text}" if label else text)
            p["abstract"] = " ".join(chunks).strip()
        else:
            p["abstract"] = ""

        # DOI
        doi_el = article.find(".//ArticleId[@IdType='doi']")
        p["doi"] = doi_el.text.strip() if doi_el is not None else ""
        p["url"] = (
            f"https://doi.org/{p['doi']}"
            if p["doi"]
            else f"https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/"
        )

        # 发表日期
        pub_date_el = article.find(".//PubDate")
        if pub_date_el is not None:
            year = pub_date_el.findtext("Year", "")
            month = pub_date_el.findtext("Month", "")
            day = pub_date_el.findtext("Day", "")
            parts = [x for x in [year, month, day] if x]
            p["pub_date"] = "-".join(parts)
        else:
            p["pub_date"] = ""

        # Publication types（用于二次过滤非 research article）
        pub_types = [
            _text(pt).lower()
            for pt in article.findall(".//PublicationTypeList/PublicationType")
        ]
        p["pub_types"] = pub_types

        # MeSH 关键词（最多 10 个）
        keywords = [_text(k) for k in article.findall(".//MeshHeading/DescriptorName")]
        p["keywords"] = keywords[:10]

        # 翻译占位符
        p["abstract_zh"] = None
        p["key_findings"] = None
        p["translated_at"] = None

        # 过滤：无标题、无摘要、或属于排除类型的条目跳过
        if not p["title"] or not p["abstract"]:
            continue
        if any(pt in EXCLUDED_PUB_TYPES for pt in pub_types):
            print(f"  [过滤] 非 research article（{pub_types}）：{p['title'][:60]}")
            continue
        if not _is_on_topic(p):
            continue

        papers.append(p)

    return papers


# ─── 主流程 ───────────────────────────────────────────────────────────────────

def main():
    days_back = int(os.getenv("DAYS_BACK", "7"))
    query, mindate, maxdate = build_query(days_back=days_back)

    print(f"[采集] 时间范围：{mindate} → {maxdate}")
    print(f"[采集] 查询语句：{query[:120]}...")

    pmids = esearch(query, mindate, maxdate)

    papers: list[dict] = []
    if pmids:
        # 分批 efetch，每批 50 条，避免请求过长
        batch_size = 50
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i : i + batch_size]
            print(f"  efetch 批次 {i // batch_size + 1}（{len(batch)} 条）...")
            papers.extend(efetch(batch))
            if i + batch_size < len(pmids):
                time.sleep(REQUEST_DELAY)
        print(f"[采集] 共获取 {len(papers)} 篇论文详情")
    else:
        print("[采集] 本周无符合条件的论文。")

    # 确定输出路径
    week = datetime.utcnow().strftime("%Y-W%V")
    out_dir = Path("data/papers")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{week}.json"

    # 加载已有数据，保留已完成的翻译（增量模式）
    existing_map: dict[str, dict] = {}
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            old_data = json.load(f)
        for p in old_data.get("papers", []):
            existing_map[p["pmid"]] = p

    for p in papers:
        if p["pmid"] in existing_map:
            old = existing_map[p["pmid"]]
            p["abstract_zh"] = old.get("abstract_zh")
            p["key_findings"] = old.get("key_findings")
            p["translated_at"] = old.get("translated_at")

    output = {
        "week": week,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "date_range": {"start": mindate, "end": maxdate},
        "total": len(papers),
        "papers": papers,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[采集] 已保存至 {out_path}（{len(papers)} 篇）")


if __name__ == "__main__":
    main()
