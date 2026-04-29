import json
import os
import re
import sys

from openai import OpenAI


DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-v4-pro"


def make_client() -> OpenAI:
    if not DEEPSEEK_API_KEY:
        print("[错误] 未设置 DEEPSEEK_API_KEY 环境变量。", file=sys.stderr)
        sys.exit(1)
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def extract_json(text: str) -> dict | None:
    """从模型输出中健壮地提取 JSON 对象。"""
    if not text or not text.strip():
        return None

    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    cleaned = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None