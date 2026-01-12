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

# Fetch job-level details for the latest run
run_id = latest.get('id')

import time
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--wait', action='store_true', help='Poll until run completes')
args = parser.parse_args()

def print_jobs(run_id):
    jobs_url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs/{run_id}/jobs"
    req = Request(jobs_url, headers={"User-Agent": "MarketStimulator-checker"})
    try:
        with urlopen(req, timeout=10) as jr:
            jdata = json.load(jr)
    except Exception as e:
        print('Failed to fetch job details:', e)
        return
    jobs = jdata.get('jobs', [])
    if jobs:
        print('\nJobs for latest run:')
        for job in jobs:
            print(f"Job: {job.get('name')} status={job.get('status')} conclusion={job.get('conclusion')} url={job.get('html_url')}")
            for step in job.get('steps', []):
                print(f"  - Step: {step.get('name')} | status={step.get('status')} | concl={step.get('conclusion')}")

if run_id:
    print_jobs(run_id)

    if args.wait:
        # poll the run until it is completed
        run_url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs/{run_id}"
        while True:
            req = Request(run_url, headers={"User-Agent": "MarketStimulator-checker"})
            with urlopen(req, timeout=10) as rr:
                rdata = json.load(rr)
            status = rdata.get('status')
            conclusion = rdata.get('conclusion')
            print(f"Run status: {status}, conclusion: {conclusion}")
            if status == 'completed':
                print('Run completed. Refreshing job details...')
                print_jobs(run_id)
                break
            time.sleep(5)
