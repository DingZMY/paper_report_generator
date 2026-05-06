"""
filter_papers.py — 调用 DeepSeek API 对采集结果做二次语义筛选

目标：
  - 优先保留偏方法论、框架、工具、理论、机制层面的论文
  - 剔除偏应用导向的 case study、常规代谢工程、无方法创新的组学分析
  - 对少数有趣的演化/机制 case study 可酌情保留

输出：就地更新 data/papers/<week>.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from deepseek_utils import MODEL, extract_json, make_client


REQUEST_DELAY = 1.2
MAX_RETRIES = 3
RETRY_DELAY = 5.0
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY_CONFIG = REPO_ROOT / "configs/filter_policy.json"


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_filter_policy(config_path: Path | None = None) -> dict:
    resolved_config_path = config_path or DEFAULT_POLICY_CONFIG
    with open(resolved_config_path, encoding="utf-8") as handle:
        policy = json.load(handle)

    prompt_version = policy.get("active_prompt_version")
    if not isinstance(prompt_version, str) or not prompt_version.strip():
        raise ValueError("filter policy 缺少 active_prompt_version")

    policy_version = str(policy.get("policy_version") or "unversioned")
    prompt_path_value = policy.get("prompt_path") or f"configs/filter_prompts/{prompt_version}.txt"
    if not isinstance(prompt_path_value, str) or not prompt_path_value.strip():
        raise ValueError("filter policy 缺少有效的 prompt_path")

    prompt_path = _resolve_repo_path(prompt_path_value)
    system_prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not system_prompt:
        raise ValueError(f"prompt 文件为空：{prompt_path}")

    return {
        "policy_version": policy_version,
        "active_prompt_version": prompt_version,
        "evaluation_snapshot_id": policy.get("evaluation_snapshot_id"),
        "config_path": _display_path(resolved_config_path),
        "prompt_path": _display_path(prompt_path),
        "system_prompt": system_prompt,
    }


def filter_paper(client, paper: dict, system_prompt: str) -> dict | None:
    try:
        from openai import APIError, RateLimitError
    except ModuleNotFoundError as error:
        raise RuntimeError("当前 Python 环境未安装 openai 依赖，无法执行 LLM 筛选。") from error

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
                    {"role": "system", "content": system_prompt},
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


def process_file(json_path: Path, policy: dict) -> int:
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
    print(
        f"[筛选] 当前策略：policy={policy['policy_version']} | "
        f"prompt={policy['active_prompt_version']} | {policy['prompt_path']}\n"
    )

    for index, paper in enumerate(papers, start=1):
        prefix = f"[{index:>3}/{len(papers)}]"

        existing = paper.get("llm_filter")
        if (
            isinstance(existing, dict)
            and existing.get("decision") == "keep"
            and existing.get("prompt_version") == policy["active_prompt_version"]
            and existing.get("policy_version") == policy["policy_version"]
        ):
            print(f"{prefix} ⏭  跳过（已保留）：{paper['pmid']}")
            kept_papers.append(paper)
            skipped += 1
            continue

        title_preview = paper["title"][:65] + ("..." if len(paper["title"]) > 65 else "")
        print(f"{prefix} 🧪 筛选：{title_preview}")

        result = filter_paper(client, paper, policy["system_prompt"])
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
            "prompt_version": policy["active_prompt_version"],
            "policy_version": policy["policy_version"],
            "evaluation_snapshot_id": policy["evaluation_snapshot_id"],
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
                "prompt_version": policy["active_prompt_version"],
                "policy_version": policy["policy_version"],
            })
            print(f"  🚫 剔除：{result['bucket']} | {result['reason']}")

        time.sleep(REQUEST_DELAY)

    data["pre_llm_filter_total"] = len(papers)
    data["llm_filtered_out"] = len(filtered_out)
    data["llm_filter_model"] = MODEL
    data["llm_filter_prompt_version"] = policy["active_prompt_version"]
    data["llm_filter_policy_version"] = policy["policy_version"]
    data["llm_filter_evaluation_snapshot_id"] = policy["evaluation_snapshot_id"]
    data["llm_filter_policy_config"] = policy["config_path"]
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="使用 DeepSeek 对论文进行二次语义筛选")
    parser.add_argument(
        "--policy-config",
        help="筛选策略 JSON 路径，默认使用 FILTER_POLICY_CONFIG 或 configs/filter_policy.json",
    )
    parser.add_argument(
        "--file",
        help="指定要处理的 JSON 文件，默认处理 data/papers/ 下最新一期",
    )
    parser.add_argument(
        "--print-policy",
        action="store_true",
        help="打印解析后的筛选策略并退出，不调用 API",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    policy_config = args.policy_config or os.environ.get("FILTER_POLICY_CONFIG")
    policy = load_filter_policy(_resolve_repo_path(policy_config) if policy_config else None)

    if args.print_policy:
        print(
            json.dumps(
                {
                    "policy_version": policy["policy_version"],
                    "active_prompt_version": policy["active_prompt_version"],
                    "evaluation_snapshot_id": policy["evaluation_snapshot_id"],
                    "config_path": policy["config_path"],
                    "prompt_path": policy["prompt_path"],
                    "prompt_preview": policy["system_prompt"][:120],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    data_dir = Path("data/papers")
    json_files = sorted(data_dir.glob("*.json"), reverse=True)

    if args.file:
        target = Path(args.file)
    elif not json_files:
        print("[筛选] data/papers/ 目录下无数据文件，请先运行 collect_papers.py")
        sys.exit(0)
    else:
        target = json_files[0]

    print(f"[筛选] 目标文件：{target}")
    process_file(target, policy)


if __name__ == "__main__":
    main()