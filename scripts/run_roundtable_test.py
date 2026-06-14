#!/usr/bin/env python3
"""Clear group, start roundtable with normal agenda, monitor full flow."""
from __future__ import annotations

import json
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GROUP_ID = sys.argv[1] if len(sys.argv) > 1 else "g_1781253949_12"
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8765"
AGENDA = sys.argv[3] if len(sys.argv) > 3 else "@all myteam 是否需要支持群聊消息撤回？"
LOG = Path(sys.argv[4] if len(sys.argv) > 4 else "/tmp/roundtable-test.log")


def api(method: str, path: str, body: dict | None = None) -> dict:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_group() -> dict:
    return api("GET", f"/api/groups/{GROUP_ID}").get("group", {})


def log(line: str) -> None:
    ts = time.strftime("%H:%M:%S")
    msg = f"[{ts}] {line}"
    print(msg, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def monitor_events(stop: threading.Event, phases: list, turns: list, errors: list, done: list):
    url = f"{BASE}/api/groups/{GROUP_ID}/events"
    try:
        with urlopen(url, timeout=7200) as resp:
            for raw in resp:
                if stop.is_set():
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    continue
                try:
                    evt = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                name = evt.get("event", "")
                data = evt.get("data") or evt
                if name == "roundtable_phase":
                    phases.append(data)
                    log(f"PHASE {data.get('phase')} round={data.get('round_num','')} cycle={data.get('cycle','')}")
                elif name == "roundtable_turn":
                    turns.append(data)
                    log(f"TURN {data.get('agent_id')} phase={data.get('phase')} r={data.get('round_num')}")
                elif name == "roundtable_start":
                    log(f"START agenda={str(data.get('agenda',''))[:80]} speakers={data.get('speakers')}")
                elif name == "roundtable_done":
                    done.append(data)
                    log(f"DONE consensus={data.get('consensus')} participation={data.get('participation_rate')}")
                elif name == "roundtable_turn_failed":
                    errors.append(data)
                    log(f"TURN_FAIL {data}")
                elif name == "roundtable_aborted":
                    errors.append(data)
                    log(f"ABORT {data}")
                elif name == "error":
                    errors.append(data)
                    log(f"ERROR {data}")
    except Exception as e:
        if not stop.is_set():
            log(f"events stream ended: {e}")


def poll_messages(msg_id: str, seen: set, phase_counts: defaultdict):
    g = get_group()
    for m in g.get("messages") or []:
        mid = m.get("id", "")
        if mid in seen:
            continue
        if not m.get("roundtable") and mid != msg_id:
            continue
        seen.add(mid)
        phase = m.get("roundtable_phase") or "-"
        sender = m.get("sender", "?")
        text = (m.get("text") or "").replace("\n", " ")[:120]
        phase_counts[phase] += 1
        log(f"MSG {sender} phase={phase} :: {text}")


def main() -> int:
    LOG.write_text(f"# roundtable test {time.strftime('%Y-%m-%d %H:%M:%S')}\n", encoding="utf-8")
    log(f"Group {GROUP_ID}")
    log(f"Agenda: {AGENDA}")

    status = api("GET", f"/api/groups/{GROUP_ID}/chat/status")
    if status.get("active"):
        log("ABORT: chat already active")
        return 1

    before = len(get_group().get("messages") or [])
    cleared = api("POST", f"/api/groups/{GROUP_ID}/clear")
    log(f"CLEAR: {cleared.get('message')} (was {before} msgs)")
    after_clear = len(get_group().get("messages") or [])
    log(f"Messages after clear: {after_clear}")

    phases: list = []
    turns: list = []
    errors: list = []
    done: list = []
    stop = threading.Event()
    t = threading.Thread(target=monitor_events, args=(stop, phases, turns, errors, done), daemon=True)
    t.start()
    time.sleep(0.5)

    params = urlencode({"sender": "user", "text": AGENDA, "rounds": "3"})
    url = f"{BASE}/api/groups/{GROUP_ID}/chat?{params}"
    log(f"TRIGGER {url}")
    msg_id = ""
    with urlopen(url, timeout=120) as resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                evt = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if evt.get("event") == "roundtable_detached":
                msg_id = (evt.get("data") or {}).get("msg_id", "")
                log(f"DETACHED msg_id={msg_id}")

    if not msg_id:
        log("FAIL: no msg_id from detached event")
        stop.set()
        return 1

    seen: set = set()
    phase_counts: defaultdict = defaultdict(int)
    start = time.time()
    last_active = True
    while time.time() - start < 7200:
        poll_messages(msg_id, seen, phase_counts)
        active = api("GET", f"/api/groups/{GROUP_ID}/chat/status").get("active")
        if done or (not active and last_active and time.time() - start > 30):
            if not active:
                time.sleep(2)
                poll_messages(msg_id, seen, phase_counts)
                break
        last_active = active
        if done:
            time.sleep(3)
            poll_messages(msg_id, seen, phase_counts)
            if not api("GET", f"/api/groups/{GROUP_ID}/chat/status").get("active"):
                break
        time.sleep(8)

    stop.set()
    t.join(timeout=2)

    g = get_group()
    summary_msg = None
    for m in reversed(g.get("messages") or []):
        if m.get("roundtable_consensus"):
            summary_msg = m
            break

    transcript_rel = (summary_msg or {}).get("roundtable_transcript", "")
    transcript_path = Path("/Users/kuanghualong/Project/Cursor/myteam") / transcript_rel if transcript_rel else None

    log("=== SUMMARY ===")
    log(f"Duration: {time.time()-start:.0f}s active={last_active}")
    log(f"SSE phases: {[p.get('phase') for p in phases]}")
    log(f"SSE turns by agent: {dict((a, sum(1 for t in turns if t.get('agent_id')==a)) for a in sorted({t.get('agent_id') for t in turns}))}")
    log(f"Message phases: {dict(phase_counts)}")
    if summary_msg:
        log(f"CONSENSUS: {summary_msg.get('roundtable_consensus')}")
        log(f"Summary preview: {(summary_msg.get('text') or '')[:300]}")
    else:
        log("CONSENSUS: (no closure message yet)")
    if errors:
        log(f"Errors: {errors}")
    if transcript_path and transcript_path.is_file():
        log(f"Transcript: {transcript_path}")
        head = transcript_path.read_text(encoding="utf-8", errors="replace")[:500]
        log(f"Transcript head: {head.replace(chr(10), ' | ')}")

    return 0 if summary_msg and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
