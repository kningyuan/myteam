#!/usr/bin/env python3
"""群聊稳定性集成探测：模式识别、detached SSE、刷新后 status/events、消息持久化。"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://localhost:8765"
GROUP_ID = "g_1781253949_12"


def api(path: str, *, method: str = "GET", timeout: float = 10) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def read_sse_first_events(path: str, max_events: int = 8, timeout: float = 45) -> list[dict]:
    url = f"{BASE}{path}"
    req = urllib.request.Request(url)
    events: list[dict] = []
    deadline = time.time() + timeout
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        buf = ""
        while len(events) < max_events and time.time() < deadline:
            chunk = resp.read(4096)
            if not chunk:
                break
            buf += chunk.decode(errors="replace")
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                for line in block.split("\n"):
                    if not line.startswith("data:"):
                        continue
                    data_raw = line[5:].strip()
                    if data_raw == "[DONE]":
                        return events
                    try:
                        payload = json.loads(data_raw)
                    except json.JSONDecodeError:
                        continue
                    events.append(payload)
                    evt_name = str(payload.get("event") or "")
                    if evt_name in ("roundtable_detached", "notify_detached", "error"):
                        return events
    return events


def msg_count() -> int:
    g = api(f"/api/groups/{urllib.parse.quote(GROUP_ID)}")
    group = g.get("group") if isinstance(g.get("group"), dict) else g
    return len(group.get("messages") or [])


def main() -> int:
    failures: list[str] = []

    print("== 0. Hub health ==")
    try:
        st0 = api(f"/api/groups/{urllib.parse.quote(GROUP_ID)}/chat/status")
        print("  OK hub reachable, chat/status:", st0)
    except Exception as e:
        print("  FAIL hub not reachable:", e)
        return 1

    print("== 1. chat/status endpoint ==")
    try:
        st = api(f"/api/groups/{urllib.parse.quote(GROUP_ID)}/chat/status")
        assert "active" in st, st
        print("  OK", st)
    except Exception as e:
        failures.append(f"chat/status: {e}")

    print("== 2. mode=roundtable detached ==")
    before = msg_count()
    q = urllib.parse.urlencode({
        "sender": "user",
        "text": "@all 稳定性探测：请用一句话说明 myteam 群聊最需要改进的一点",
        "mode": "roundtable",
        "rounds": "1",
    })
    try:
        evts = read_sse_first_events(f"/api/groups/{urllib.parse.quote(GROUP_ID)}/chat?{q}")
        names = [str(e.get("event") or "") for e in evts]
        print("  events:", names[:12])
        if "roundtable_detached" not in names:
            failures.append(f"roundtable: no detached, got {names}")
        else:
            print("  OK roundtable_detached received")
    except Exception as e:
        failures.append(f"roundtable SSE: {e}")

    print("  poll status after detach (simulate refresh UI) ==")
    active_seen = False
    for i in range(12):
        time.sleep(2)
        st = api(f"/api/groups/{urllib.parse.quote(GROUP_ID)}/chat/status")
        if st.get("active"):
            active_seen = True
            print(f"  t+{(i+1)*2}s active=True")
        after = msg_count()
        if after > before:
            print(f"  messages grew {before} -> {after}")
            break
    if not active_seen:
        print("  note: active never true (maybe finished fast or endpoint stale hub)")

    print("== 3. mode=notify detached (@main only, fast) ==")
    before2 = msg_count()
    q2 = urllib.parse.urlencode({
        "sender": "user",
        "text": "@main 稳定性探测：回复 OK 两个字母即可",
        "mode": "notify",
    })
    try:
        evts2 = read_sse_first_events(f"/api/groups/{urllib.parse.quote(GROUP_ID)}/chat?{q2}")
        names2 = [str(e.get("event") or "") for e in evts2]
        print("  events:", names2[:12])
        if "notify_detached" not in names2:
            failures.append(f"notify: no detached, got {names2}")
        else:
            print("  OK notify_detached received")
    except Exception as e:
        failures.append(f"notify SSE: {e}")

    for i in range(15):
        time.sleep(2)
        after2 = msg_count()
        if after2 > before2:
            print(f"  notify messages {before2} -> {after2}")
            break

    print("== 4. events SSE subscription ==")
    try:
        url = f"{BASE}/api/groups/{urllib.parse.quote(GROUP_ID)}/events"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=8) as resp:
            chunk = resp.read(256)
            print("  OK events stream opens, bytes:", len(chunk))
    except urllib.error.HTTPError as e:
        failures.append(f"events SSE HTTP {e.code}")
    except Exception as e:
        if "timed out" in str(e).lower():
            print("  OK events stream (idle, no immediate bytes)")
        else:
            failures.append(f"events SSE: {e}")

    print("\n== Summary ==")
    if failures:
        for f in failures:
            print("  FAIL", f)
        return 1
    print("  All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
