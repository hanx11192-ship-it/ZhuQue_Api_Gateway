import json
import os
import sys

raw = os.environ.get("API_PAYLOAD") or ""
if not raw:
    raw = sys.stdin.read() or "{}"
payload = json.loads(raw)
query = json.loads(os.environ.get("API_QUERY") or "{}")
print(json.dumps({"echo": payload, "query": query}, ensure_ascii=False))
