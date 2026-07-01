#!/usr/bin/env python3
"""Debug script: create project, copy video, submit process, check result."""
import os, sys, json, shutil, time
import requests

API = "http://localhost:8000/api"
H = {"X-User-Id": "test", "Content-Type": "application/json"}
VIDEO = os.path.expanduser("~/jarvis/projects/video-multisrt-multi-hls/tests/fixtures/test_short_drama.mp4")
STORAGE = os.path.expanduser("~/jarvis/projects/video-multisrt-multi-hls/apps/api/storage")

# 1. 创建项目
r = requests.post(f"{API}/projects", json={"name":"debug","source_language":"zh-CN","target_languages":["en-US"],"translation_style":"short_drama_localized"}, headers=H, timeout=30)
print(f"1. Create project: {r.status_code}")
proj = r.json()
pid = proj["project_id"]
print(f"   project_id={pid}")

# 2. 复制视频 — 路径必须匹配 DB 里的 URI：storage://private/projects/{pid}/source/source.mp4
dst = os.path.join(STORAGE, "projects", pid, "source", "source.mp4")
os.makedirs(os.path.dirname(dst), exist_ok=True)
shutil.copy(VIDEO, dst)
print(f"2. Video copied to {dst}")

# 3. 提交处理
r = requests.post(f"{API}/projects/{pid}/process", json={"enable_source_separation":True,"enable_diarization":False,"generate_tts":False,"generate_preview_mp4":False,"agent_template":"subtitle_draft"}, headers=H, timeout=300)
print(f"3. Process: {r.status_code}")
print(f"   Response: {r.text[:500]}")
run = r.json()
rid = run.get("run_id","")
print(f"   run_id={rid}")

# 4. 查 agent-run
if rid:
    r = requests.get(f"{API}/agent-runs/{rid}", headers={"X-User-Id":"test"}, timeout=10)
    print(f"4. AgentRun: {r.status_code}")
    data = r.json()
    print(f"   status={data.get('agent_run',{}).get('status')}")
    print(f"   step={data.get('agent_run',{}).get('current_step')}")
    for sr in data.get("skill_runs",[]):
        print(f"   skill={sr.get('skill_name')} status={sr.get('status')} error={sr.get('error')}")

# 5. 查 segments
r = requests.get(f"{API}/projects/{pid}/segments?target_language=en-US", headers={"X-User-Id":"test"}, timeout=10)
print(f"5. Segments: {r.status_code}")
segs = r.json().get("segments",[])
print(f"   count={len(segs)}")
for s in segs[:3]:
    seg = s.get("segment",{})
    tr = s.get("translation",{})
    print(f"   [{seg.get('start_ms')}-{seg.get('end_ms')}] {seg.get('source_text','')} → {tr.get('text','')}")

# 6. 查项目详情
r = requests.get(f"{API}/projects/{pid}", headers={"X-User-Id":"test"}, timeout=10)
print(f"6. Project: {r.status_code}")
pd = r.json()
print(f"   status={pd.get('project',{}).get('status')}")
print(f"   duration={pd.get('project',{}).get('duration_ms')}")
print(f"   assets={len(pd.get('assets',[]))}")
for a in pd.get("assets",[]):
    print(f"     {a.get('type')}: {a.get('uri','')[:60]}")
