#!/usr/bin/env python3
"""Simple script to check the latest GitHub Actions run for this repo."""
import json
import sys
from urllib.request import urlopen, Request

OWNER = "aparnakumarishaw-stack"
REPO = "MarketStimulator"
URL = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs"

req = Request(URL, headers={"User-Agent": "MarketStimulator-checker"})
try:
    with urlopen(req, timeout=10) as r:
        data = json.load(r)
except Exception as e:
    print("Failed to fetch Actions runs:", e)
    sys.exit(2)

runs = data.get("workflow_runs", [])
if not runs:
    print("No workflow runs found.")
    sys.exit(0)

latest = runs[0]
print("Latest workflow run:")
print(f"  id: {latest.get('id')}")
print(f"  name: {latest.get('name')}")
print(f"  status: {latest.get('status')}")
print(f"  conclusion: {latest.get('conclusion')}")
print(f"  url: {latest.get('html_url')}")
print(f"  branch: {latest.get('head_branch')}")
print(f"  started: {latest.get('run_started_at')}")

# Print a short summary of recent runs
print('\nRecent runs:')
for r in runs[:5]:
    print(f" - {r.get('name')} [{r.get('head_branch')}] status={r.get('status')} concl={r.get('conclusion')} url={r.get('html_url')}")
