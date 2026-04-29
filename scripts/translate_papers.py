"""
translate_papers.py — 调用 DeepSeek API 翻译摘要并提炼核心发现

使用 OpenAI 兼容接口：
  base_url = https://api.deepseek.com
  model    = deepseek-v4-pro

对每篇未翻译的论文：
  - 翻译英文摘要 → abstract_zh
  - 提炼 3 条核心发现 → key_findings

增量处理：已有 abstract_zh 的论文直接跳过。
输出：就地更新 data/papers/<week>.json
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime
from openai import OpenAI, APIError, RateLimitError

from deepseek_utils import MODEL, extract_json, make_client

REQUEST_DELAY = 1.2    # 每次请求后等待（秒），保守限速
MAX_RETRIES = 3
RETRY_DELAY = 5.0

SYSTEM_PROMPT = """你是系统生物学与合成生物学领域的顶级学者。你的任务是处理一篇科研论文的摘要，输出严格的 JSON 格式，不要包含任何额外文字。

JSON 结构如下：
{
  "abstract_zh": "将英文摘要翻译为准确、流畅的中文简体",
  "key_findings": [
    "核心发现1：用一句话概括（不超过50字）",
    "核心发现2：用一句话概括（不超过50字）",
    "核心发现3：用一句话概括（不超过50字）"
  ]
}

翻译要求：
- 保留专业术语的准确性（如 CRISPR、operon、metabolic flux 等）
- 遇到无中文对应的缩写，保留英文原词并在首次出现时括注中文
- 核心发现要突出科学贡献，避免泛泛而谈"""


def translate_paper(client: OpenAI, paper: dict) -> dict | None:
    """
    调用 DeepSeek 翻译单篇论文。
    返回 {"abstract_zh": str, "key_findings": [str, ...]} 或 None（失败时）。
    """
    user_msg = (
        f"题目：{paper['title']}\n"
        f"期刊：{paper['journal']}\n"
        f"摘要（英文）：\n{paper['abstract']}"
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=1,
                max_tokens=2500,
            )
            msg = response.choices[0].message
            # thinking 模型有时 content 为空，答案在 reasoning_content 中
            content = msg.content or ""
            if not content.strip():
                content = getattr(msg, "reasoning_content", "") or ""
            result = extract_json(content)
            if result and "abstract_zh" in result and "key_findings" in result:
                return result
            # 模型返回了非预期格式
            print(f"  [警告] 第 {attempt} 次返回格式异常，原始输出：{content[:200]}")
        except RateLimitError:
            wait = RETRY_DELAY * attempt
            print(f"  [限速] 等待 {wait}s 后重试（第 {attempt}/{MAX_RETRIES} 次）...")
            time.sleep(wait)
        except APIError as e:
            print(f"  [API 错误] {e}（第 {attempt}/{MAX_RETRIES} 次）")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            print(f"  [未知错误] {e}", file=sys.stderr)
            break

    return None


# ─── 文件处理 ─────────────────────────────────────────────────────────────────

def process_file(json_path: Path) -> int:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    papers = data["papers"]
    client = make_client()
    updated = 0
    skipped = 0
    errors = 0

    print(f"[翻译] 共 {len(papers)} 篇论文，逐一处理中...\n")

    for i, paper in enumerate(papers, start=1):
        prefix = f"[{i:>3}/{len(papers)}]"

        # 已翻译则跳过
        if paper.get("abstract_zh"):
            print(f"{prefix} ⏭  跳过（已翻译）：{paper['pmid']}")
            skipped += 1
            continue

        # 无摘要则跳过
        if not paper.get("abstract"):
            print(f"{prefix} ⏭  跳过（无摘要）：{paper['pmid']}")
            skipped += 1
            continue

        title_preview = paper["title"][:65] + ("..." if len(paper["title"]) > 65 else "")
        print(f"{prefix} 🔄 翻译：{title_preview}")

        result = translate_paper(client, paper)
        if result:
            paper["abstract_zh"] = result.get("abstract_zh", "")
            paper["key_findings"] = result.get("key_findings", [])
            paper["translated_at"] = datetime.utcnow().isoformat() + "Z"
            updated += 1
            print(f"  ✅ 完成")
        else:
            errors += 1
            print(f"  ❌ 翻译失败，跳过")

        time.sleep(REQUEST_DELAY)

    # 写回文件
    data["papers"] = papers
    data["translated_count"] = updated
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[翻译] 完成：{updated} 篇翻译 | {skipped} 篇跳过 | {errors} 篇失败")
    return updated


# ─── 主流程 ───────────────────────────────────────────────────────────────────

def main():
    data_dir = Path("data/papers")
    json_files = sorted(data_dir.glob("*.json"), reverse=True)

    if not json_files:
        print("[翻译] data/papers/ 目录下无数据文件，请先运行 collect_papers.py")
        sys.exit(0)

    target = json_files[0]
    print(f"[翻译] 目标文件：{target}")
    process_file(target)


if __name__ == "__main__":
    main()
