"""
filter_papers.py — 调用 DeepSeek API 对采集结果做二次语义筛选

目标：
  - 优先保留偏方法论、框架、工具、理论、机制层面的论文
  - 剔除偏应用导向的 case study、常规代谢工程、无方法创新的组学分析
  - 对少数有趣的演化/机制 case study 可酌情保留

输出：就地更新 data/papers/<week>.json
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

from openai import OpenAI, APIError, RateLimitError

from deepseek_utils import MODEL, extract_json, make_client


REQUEST_DELAY = 1.2
MAX_RETRIES = 3
RETRY_DELAY = 5.0

SYSTEM_PROMPT = """你是系统生物学、合成生物学与理论生物学方向的资深编委。你的任务是判断一篇论文是否应该进入“偏方法论”的精选周报。

筛选原则：
- 优先保留：新方法、新框架、新工具、新建模范式、新实验平台、新计算策略、能普适迁移的机制洞察
- 可以保留：有明显概念新意、机制新意或演化启发性的 case study，即使不是纯方法论文
- 倾向剔除：
  1. 纯应用导向的代谢工程/产物优化/特定酶或特定通路案例
  2. 仅把现成 omics / CRISPR / 机器学习工具套到具体系统上、但方法本身无创新
  3. 主要价值在某一具体疾病、菌株、细胞系或材料体系的经验性结果，缺乏可迁移方法论
  4. 常规的工具优化，如果主要是局部性能改良而非带来新的方法学能力

请输出严格 JSON，不要附加任何解释文字：
{
  "decision": "keep" 或 "discard",
  "bucket": "method" | "framework" | "mechanism_case" | "application_case" | "descriptive_study" | "incremental_tooling" | "other",
  "reason": "一句中文简述，说明保留或剔除的核心原因，不超过60字"
}
"""


def filter_paper(client: OpenAI, paper: dict) -> dict | None:
    user_msg = (
        f"题目：{paper['title']}\n"
        f"期刊：{paper['journal']}\n"
        f"发表日期：{paper.get('pub_date', '')}\n"
        f"关键词：{', '.join(paper.get('keywords') or [])}\n"
        f"摘要：\n{paper.get('abstract', '')}"
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.2,
                max_tokens=600,
            )
            msg = response.choices[0].message
            content = msg.content or ""
            if not content.strip():
                content = getattr(msg, "reasoning_content", "") or ""

            result = extract_json(content)
            if not result:
                print(f"  [警告] 第 {attempt} 次返回格式异常，原始输出：{content[:200]}")
                continue

            decision = result.get("decision")
            bucket = result.get("bucket")
            reason = result.get("reason")
            if decision in {"keep", "discard"} and isinstance(bucket, str) and isinstance(reason, str):
                return result

            print(f"  [警告] 第 {attempt} 次返回字段不完整：{content[:200]}")
        except RateLimitError:
            wait = RETRY_DELAY * attempt
            print(f"  [限速] 等待 {wait}s 后重试（第 {attempt}/{MAX_RETRIES} 次）...")
            time.sleep(wait)
        except APIError as error:
            print(f"  [API 错误] {error}（第 {attempt}/{MAX_RETRIES} 次）")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except Exception as error:
            print(f"  [未知错误] {error}", file=sys.stderr)
            break

    return None


def process_file(json_path: Path) -> int:
    with open(json_path, encoding="utf-8") as handle:
        data = json.load(handle)

    papers = data.get("papers", [])
    client = make_client()
    kept_papers = []
    filtered_out = []
    kept = 0
    skipped = 0
    errors = 0

    print(f"[筛选] 共 {len(papers)} 篇论文，逐一进行 LLM 语义筛选...\n")

    for index, paper in enumerate(papers, start=1):
        prefix = f"[{index:>3}/{len(papers)}]"

        existing = paper.get("llm_filter")
        if isinstance(existing, dict) and existing.get("decision") == "keep":
            print(f"{prefix} ⏭  跳过（已保留）：{paper['pmid']}")
            kept_papers.append(paper)
            skipped += 1
            continue

        title_preview = paper["title"][:65] + ("..." if len(paper["title"]) > 65 else "")
        print(f"{prefix} 🧪 筛选：{title_preview}")

        result = filter_paper(client, paper)
        if result is None:
            errors += 1
            kept_papers.append(paper)
            print("  ⚠️  筛选失败，默认保留")
            time.sleep(REQUEST_DELAY)
            continue

        paper["llm_filter"] = {
            "decision": result["decision"],
            "bucket": result["bucket"],
            "reason": result["reason"],
            "model": MODEL,
            "filtered_at": datetime.utcnow().isoformat() + "Z",
        }

        if result["decision"] == "keep":
            kept += 1
            kept_papers.append(paper)
            print(f"  ✅ 保留：{result['bucket']} | {result['reason']}")
        else:
            filtered_out.append({
                "pmid": paper.get("pmid"),
                "title": paper.get("title"),
                "journal": paper.get("journal"),
                "bucket": result["bucket"],
                "reason": result["reason"],
            })
            print(f"  🚫 剔除：{result['bucket']} | {result['reason']}")

        time.sleep(REQUEST_DELAY)

    data["pre_llm_filter_total"] = len(papers)
    data["llm_filtered_out"] = len(filtered_out)
    data["llm_filter_model"] = MODEL
    data["llm_filtered_at"] = datetime.utcnow().isoformat() + "Z"
    data["filtered_out_papers"] = filtered_out
    data["papers"] = kept_papers
    data["total"] = len(kept_papers)

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    print(
        f"\n[筛选] 完成：保留 {len(kept_papers)} 篇 | 剔除 {len(filtered_out)} 篇 | "
        f"跳过 {skipped} 篇 | 失败默认保留 {errors} 篇"
    )
    return len(kept_papers)


def main():
    data_dir = Path("data/papers")
    json_files = sorted(data_dir.glob("*.json"), reverse=True)

    if not json_files:
        print("[筛选] data/papers/ 目录下无数据文件，请先运行 collect_papers.py")
        sys.exit(0)

    target = json_files[0]
    print(f"[筛选] 目标文件：{target}")
    process_file(target)


if __name__ == "__main__":
    main()