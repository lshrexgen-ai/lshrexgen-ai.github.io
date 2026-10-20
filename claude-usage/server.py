#!/usr/bin/env python3
"""Claude Code 토큰 사용량 실시간 대시보드 서버 (표준 라이브러리만 사용).

~/.claude/projects/**/*.jsonl 의 assistant 메시지 usage 값을 집계해서
/api/usage 로 제공하고, 같은 포트에서 index.html 대시보드를 서빙합니다.

사용법:
  python3 server.py --window-limit 5000000 --host 0.0.0.0 --port 8787
  같은 Wi-Fi의 휴대폰에서 http://<PC의 IP>:8787 접속

--window-limit 은 5시간 구간 한도(토큰)입니다. Claude 구독의 실제 잔여량은
로컬 로그로 알 수 없으므로, 본인이 보는 한도를 직접 넣어야 잔여량이 계산됩니다.
카운트 기준: input + output + cache_creation (cache_read 는 제외)
"""

import argparse
import glob
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
WINDOW = timedelta(hours=5)
KST = timezone(timedelta(hours=9))

_lock = threading.Lock()
_cache = {"sig": None, "records": []}


def load_records():
    """모든 jsonl을 읽어 (timestamp, model, usage) 목록을 만든다. 파일 변경이 없으면 캐시 사용."""
    files = glob.glob(os.path.join(PROJECTS_DIR, "**", "*.jsonl"), recursive=True)
    sig = tuple(sorted((f, os.path.getmtime(f), os.path.getsize(f)) for f in files))
    with _lock:
        if sig == _cache["sig"]:
            return _cache["records"]

    seen = set()
    records = []
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = d.get("message")
                    if not isinstance(msg, dict) or not msg.get("usage"):
                        continue
                    # 한 응답이 여러 줄로 기록되므로 message id 로 중복 제거
                    key = msg.get("id") or d.get("uuid")
                    if key in seen:
                        continue
                    seen.add(key)
                    ts = d.get("timestamp")
                    if not ts:
                        continue
                    when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    records.append((when, msg.get("model") or "unknown", msg["usage"]))
        except OSError:
            continue

    records.sort(key=lambda r: r[0])
    with _lock:
        _cache["sig"] = sig
        _cache["records"] = records
    return records


def tally(usages):
    t = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "messages": 0}
    for u in usages:
        t["input"] += u.get("input_tokens", 0) or 0
        t["output"] += u.get("output_tokens", 0) or 0
        t["cache_creation"] += u.get("cache_creation_input_tokens", 0) or 0
        t["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
        t["messages"] += 1
    t["counted"] = t["input"] + t["output"] + t["cache_creation"]
    return t


def build_payload(window_limit, daily_limit):
    records = load_records()
    now = datetime.now(timezone.utc)
    win_start = now - WINDOW
    in_window = [r for r in records if r[0] >= win_start]

    # 현재 5시간 구간의 리셋 시각 = 구간 내 가장 오래된 메시지 + 5시간 (추정)
    reset_at = None
    if in_window:
        reset_at = min(r[0] for r in in_window) + WINDOW

    window = tally(r[2] for r in in_window)
    window["limit"] = window_limit
    window["remaining"] = max(window_limit - window["counted"], 0) if window_limit else None
    window["percent"] = round(window["counted"] / window_limit * 100, 1) if window_limit else None
    window["reset_at"] = reset_at.isoformat() if reset_at else None

    today_kst = now.astimezone(KST).date()
    today = [r for r in records if r[0].astimezone(KST).date() == today_kst]
    today_t = tally(r[2] for r in today)
    today_t["limit"] = daily_limit
    today_t["remaining"] = max(daily_limit - today_t["counted"], 0) if daily_limit else None
    today_t["percent"] = round(today_t["counted"] / daily_limit * 100, 1) if daily_limit else None

    # 최근 7일 일별
    days = []
    for i in range(6, -1, -1):
        d = today_kst - timedelta(days=i)
        day_usages = [r[2] for r in records if r[0].astimezone(KST).date() == d]
        days.append({"date": d.isoformat(), **tally(day_usages)})

    # 최근 5시간 모델별
    by_model = {}
    for when, model, u in in_window:
        by_model.setdefault(model, []).append(u)
    models = {m: tally(us) for m, us in by_model.items()}

    return {
        "generated_at": now.isoformat(),
        "window": window,
        "today": today_t,
        "days": days,
        "models": models,
        "source_messages": len(records),
    }


def make_handler(window_limit, daily_limit):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/api/usage":
                body = json.dumps(build_payload(window_limit, daily_limit), ensure_ascii=False).encode()
                self._send(200, "application/json; charset=utf-8", body, no_cache=True)
            elif path in ("/", "/index.html"):
                with open(os.path.join(HERE, "index.html"), "rb") as fh:
                    self._send(200, "text/html; charset=utf-8", fh.read(), no_cache=True)
            else:
                self._send(404, "text/plain; charset=utf-8", b"not found")

        def _send(self, code, ctype, body, no_cache=False):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if no_cache:
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    return Handler


def main():
    p = argparse.ArgumentParser(description="Claude 토큰 사용량 대시보드")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--window-limit", type=int, default=0,
                   help="5시간 구간 한도 (토큰). 0이면 잔여량 계산 안 함")
    p.add_argument("--daily-limit", type=int, default=0,
                   help="일일 한도 (토큰). 0이면 잔여량 계산 안 함")
    args = p.parse_args()

    srv = ThreadingHTTPServer((args.host, args.port), make_handler(args.window_limit, args.daily_limit))
    print(f"대시보드: http://{args.host}:{args.port}  (휴대폰은 PC의 IP 주소로 접속)")
    print(f"로그 경로: {PROJECTS_DIR}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("종료")


if __name__ == "__main__":
    main()
