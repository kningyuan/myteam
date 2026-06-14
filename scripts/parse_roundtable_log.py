#!/usr/bin/env python3
"""Parse roundtable SSE log (data: JSON lines) and print phase/turn timeline."""
import json
import re
import sys
from collections import defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/roundtable-run.log"
turns = []
phases = []
errors = []
done = None

with open(path, encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        evt = obj.get("event")
        data = obj.get("data") or {}
        if evt == "roundtable_phase":
            phases.append(data)
        elif evt == "roundtable_turn":
            turns.append(data)
        elif evt == "roundtable_done":
            done = data
        elif evt == "error":
            errors.append(data.get("message", str(data)))
        elif evt == "roundtable_start":
            print("START:", json.dumps(data, ensure_ascii=False))

print(f"\nPhases ({len(phases)}):")
for p in phases:
    print(f"  - {p.get('phase')} round={p.get('round','?')} speakers={p.get('speaker_count')}")

by_agent = defaultdict(list)
for t in turns:
    by_agent[t.get("agent_id", "?")].append(t.get("phase"))

print(f"\nTurns by agent ({len(turns)} total):")
for aid, plist in sorted(by_agent.items()):
    print(f"  {aid}: {' → '.join(plist)}")

if errors:
    print("\nErrors:", errors)
if done:
    print("\nDONE:", json.dumps(done, ensure_ascii=False, indent=2))
