#!/usr/bin/env python3
"""Monitor roundtable SSE stream and summarize agent behavior."""
import json
import sys
import time
from collections import defaultdict
from urllib.parse import urlencode
from urllib.request import urlopen

GROUP_ID = sys.argv[1] if len(sys.argv) > 1 else "g_1781253949_12"
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8765"
LOG_PATH = sys.argv[3] if len(sys.argv) > 3 else "/tmp/roundtable-run.log"

TEXT = (
    "@all 三轮圆桌讨论（严格按流程：立论→对齐交锋→共识草案→确认投票）。"
    "议题：myteam Agent 外挂记忆架构——Hub 已预留 AgentMemoryProvider，默认 native；"
    "群/圆桌 session 按 group 隔离。"
    "请从产品、架构、研究角度简要表态并相互回应；"
    "若三轮后无法完全一致，主持必须整理「已共识」与「仍存分歧（需用户拍板）」"
    "及保守方案，交我确认。"
)

params = urlencode(
    {
        "sender": "user",
        "text": TEXT,
        "mode": "roundtable",
        "rounds": "3",
    }
)
url = f"{BASE}/api/groups/{GROUP_ID}/chat?{params}"

phases = []
turns = defaultdict(list)
errors = []
done_payload = None
start = time.time()

print(f"Starting roundtable: {GROUP_ID}", flush=True)
print(f"Log: {LOG_PATH}", flush=True)

with open(LOG_PATH, "w", encoding="utf-8") as log:
    log.write(f"# roundtable start {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log.write(f"URL: {url}\n\n")

    try:
        with urlopen(url, timeout=7200) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                log.write(line + "\n")
                log.flush()

                if line.startswith("event:"):
                    current_event = line.split(":", 1)[1].strip()
                    continue
                if line.startswith("data:"):
                    try:
                        data = json.loads(line.split(":", 1)[1].strip())
                    except json.JSONDecodeError:
                        continue
                    evt = current_event if "current_event" in dir() else data.get("event")
                    if line.startswith("data:") and "event" in str(type(data)):
                        pass

                # SSE format: event: xxx \n data: {...}
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    # infer from keys
                    if "phase" in data and "msg_id" in data:
                        phases.append(data)
                        print(
                            f"[{time.time()-start:.0f}s] phase={data.get('phase')} "
                            f"round={data.get('round_num','')} cycle={data.get('cycle','')}",
                            flush=True,
                        )
                    elif data.get("agent_id") and data.get("phase"):
                        turns[data["agent_id"]].append(data.get("phase"))
                        print(
                            f"[{time.time()-start:.0f}s] turn agent={data.get('agent_id')} "
                            f"phase={data.get('phase')} round={data.get('round_num','')}",
                            flush=True,
                        )
                    elif "consensus" in data or data.get("event") == "roundtable_done":
                        done_payload = data
                        print(f"[{time.time()-start:.0f}s] DONE: {json.dumps(data, ensure_ascii=False)[:500]}", flush=True)
                    elif data.get("message"):
                        errors.append(data["message"])
                        print(f"[{time.time()-start:.0f}s] ERROR: {data['message']}", flush=True)
    except Exception as e:
        log.write(f"\n# stream error: {e}\n")
        print(f"Stream error: {e}", flush=True)

print("\n=== Summary ===", flush=True)
print(f"Duration: {time.time()-start:.1f}s", flush=True)
print(f"Phases logged: {len(phases)}", flush=True)
for agent, plist in sorted(turns.items()):
    print(f"  {agent}: {plist}", flush=True)
if errors:
    print(f"Errors: {errors}", flush=True)
if done_payload:
    print(f"Done payload: {json.dumps(done_payload, ensure_ascii=False, indent=2)}", flush=True)
