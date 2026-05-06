"""feedback_server.py — 接收浏览器反馈事件并落盘为 JSONL。"""

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data/feedback/events"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_event(event: dict) -> list[str]:
    errors = []
    required_string_fields = [
        "schema_version",
        "signal",
        "action",
        "pmid",
        "timestamp",
        "client_id",
        "source_path",
    ]

    for field in required_string_fields:
        value = event.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"missing or invalid field: {field}")

    if event.get("signal") not in {"favorite", "archive", "review"}:
        errors.append("signal must be one of favorite/archive/review")

    if event.get("action") not in {"add", "remove", "keep", "discard"}:
        errors.append("action must be one of add/remove/keep/discard")

    metadata = event.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        errors.append("metadata must be an object when provided")

    return errors


def read_events(data_dir: Path, limit: int | None = None) -> list[dict]:
    events = []
    for path in sorted(data_dir.glob("*.jsonl")):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if limit is None or limit >= len(events):
        return events
    return events[-limit:]


def make_handler(data_dir: Path):
    class FeedbackHandler(BaseHTTPRequestHandler):
        def _write_json(self, status: int, payload: dict):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self._write_json(200, {"status": "ok"})

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/feedback/health":
                self._write_json(
                    200,
                    {
                        "status": "ok",
                        "data_dir": str(data_dir),
                        "timestamp": utc_now_iso(),
                    },
                )
                return

            if parsed.path == "/api/feedback/export":
                query = parse_qs(parsed.query)
                limit = None
                if "limit" in query:
                    try:
                        limit = max(0, int(query["limit"][0]))
                    except ValueError:
                        self._write_json(400, {"status": "error", "message": "invalid limit"})
                        return

                events = read_events(data_dir, limit)
                self._write_json(200, {"status": "ok", "count": len(events), "events": events})
                return

            self._write_json(404, {"status": "error", "message": "not found"})

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != "/api/feedback/events":
                self._write_json(404, {"status": "error", "message": "not found"})
                return

            content_length = self.headers.get("Content-Length", "0")
            try:
                payload_size = int(content_length)
            except ValueError:
                self._write_json(400, {"status": "error", "message": "invalid Content-Length"})
                return

            if payload_size <= 0:
                self._write_json(400, {"status": "error", "message": "empty body"})
                return

            raw_body = self.rfile.read(payload_size)
            try:
                event = json.loads(raw_body.decode("utf-8"))
            except json.JSONDecodeError:
                self._write_json(400, {"status": "error", "message": "invalid json"})
                return

            errors = validate_event(event)
            if errors:
                self._write_json(400, {"status": "error", "message": "invalid event", "errors": errors})
                return

            data_dir.mkdir(parents=True, exist_ok=True)
            event["received_at"] = utc_now_iso()
            output_path = data_dir / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
            with open(output_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")

            self._write_json(
                202,
                {
                    "status": "accepted",
                    "path": str(output_path),
                    "pmid": event.get("pmid"),
                    "signal": event.get("signal"),
                    "action": event.get("action"),
                },
            )

        def log_message(self, fmt: str, *args):
            print(f"[feedback] {self.address_string()} - {fmt % args}")

    return FeedbackHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Bio Digest feedback ingestion server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind, default 127.0.0.1")
    parser.add_argument("--port", type=int, default=8787, help="Port to bind, default 8787")
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Directory to store feedback JSONL files",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    data_dir = Path(args.data_dir).expanduser().resolve()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(data_dir))
    print(f"[feedback] listening on http://{args.host}:{args.port}")
    print(f"[feedback] writing events to {data_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[feedback] stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()