"""aggregate_feedback.py — 将反馈事件 JSONL 聚合为稳定快照。"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EVENTS_DIR = REPO_ROOT / "data/feedback/events"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data/feedback/aggregated/latest.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate Bio Digest feedback events into a stable snapshot")
    parser.add_argument(
        "--events-dir",
        default=str(DEFAULT_EVENTS_DIR),
        help="Directory containing feedback JSONL event files",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Output JSON path for the aggregated snapshot",
    )
    return parser.parse_args()


def load_events(events_dir: Path) -> list[dict]:
    events = []
    for path in sorted(events_dir.glob("*.jsonl")):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return events


def _sort_key(event: dict) -> tuple[str, str, str]:
    return (
        str(event.get("timestamp") or ""),
        str(event.get("received_at") or ""),
        str(event.get("pmid") or ""),
    )


def aggregate_events(events: list[dict]) -> list[dict]:
    states: dict[tuple[str, str], dict] = {}

    for event in sorted(events, key=_sort_key):
        pmid = str(event.get("pmid") or "").strip()
        if not pmid:
            continue

        week = str(event.get("week") or "")
        key = (pmid, week)
        state = states.setdefault(
            key,
            {
                "pmid": pmid,
                "week": week,
                "favorite": {"active": False, "updated_at": None, "events": 0},
                "archive": {"active": False, "updated_at": None, "events": 0},
                "review": {"decision": None, "updated_at": None, "events": 0},
                "last_event_at": None,
            },
        )

        signal = event.get("signal")
        action = event.get("action")
        event_time = event.get("timestamp") or event.get("received_at") or utc_now_iso()

        if signal in {"favorite", "archive"}:
            active = action == "add"
            state[signal]["active"] = active
            state[signal]["updated_at"] = event_time
            state[signal]["events"] += 1
        elif signal == "review" and action in {"keep", "discard"}:
            state["review"]["decision"] = action
            state["review"]["updated_at"] = event_time
            state["review"]["events"] += 1

        state["last_event_at"] = event_time

    return sorted(states.values(), key=lambda item: (item["week"], item["pmid"]))


def build_snapshot(events_dir: Path, labels: list[dict], event_count: int) -> dict:
    return {
        "generated_at": utc_now_iso(),
        "source_dir": str(events_dir),
        "event_count": event_count,
        "paper_count": len(labels),
        "labels": labels,
    }


def main():
    args = parse_args()
    events_dir = Path(args.events_dir).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    events = load_events(events_dir) if events_dir.exists() else []
    labels = aggregate_events(events)
    snapshot = build_snapshot(events_dir, labels, len(events))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2)

    print(
        f"[feedback] snapshot -> {output_path} | "
        f"events={snapshot['event_count']} | papers={snapshot['paper_count']}"
    )


if __name__ == "__main__":
    main()