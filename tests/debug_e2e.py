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

# 7. 如果 waiting_human，先 PATCH 一个 segment（满足 proofreading 确认条件），再 continue
status = data.get("agent_run",{}).get("status","")
if status == "waiting_human":
    # 先 PATCH segment 满足 _has_saved_human_edit 检查
    if segs:
        seg_id = segs[0].get("segment",{}).get("segment_id","")
        if seg_id:
            print(f"\n6.5. PATCH segment {seg_id} (satisfy proofreading requirement)")
            r = requests.patch(f"{API}/projects/{pid}/segments/{seg_id}",
                json={"translation_text": segs[0].get("translation",{}).get("text","")},
                headers=H, timeout=30)
            print(f"   PATCH: {r.status_code}")
    
    print(f"\n7. Continue (proofreading → TTS + mix + manifest)")
    r = requests.post(f"{API}/agent-runs/{rid}/continue",
        json={"checkpoint":"proofreading","confirmed":True},
        headers=H, timeout=600)
    print(f"   Continue: {r.status_code} {r.text[:200]}")
    
    # 等待完成
    for i in range(120):
        r = requests.get(f"{API}/agent-runs/{rid}", headers={"X-User-Id":"test"}, timeout=10)
        data2 = r.json()
        st = data2.get("agent_run",{}).get("status","")
        step = data2.get("agent_run",{}).get("current_step","")
        print(f"   [{i*5}s] status={st} step={step}")
        if st in ("succeeded","failed"):
            break
        time.sleep(5)
    
    # 检查最终 skill runs
    for sr in data2.get("skill_runs",[]):
        print(f"   skill={sr.get('skill_name')} status={sr.get('status')} error={sr.get('error')}")
    
    # 查最终 segments
    r = requests.get(f"{API}/projects/{pid}/segments?target_language=en-US", headers={"X-User-Id":"test"}, timeout=10)
    segs2 = r.json().get("segments",[])
    print(f"\n8. Final segments: {len(segs2)}")
    for s in segs2[:5]:
        seg = s.get("segment",{})
        tr = s.get("translation",{})
        tts = s.get("tts_job") or {}
        print(f"   [{seg.get('start_ms')}-{seg.get('end_ms')}] {seg.get('source_text','')}")
        print(f"     → {tr.get('text','')}")
        print(f"     TTS: status={tts.get('status','?')} voice={tts.get('voice_id','?')} dur={tts.get('actual_duration_ms','?')}")
    
    # 查 manifest
    r = requests.get(f"{API}/projects/{pid}/manifest", headers={"X-User-Id":"test"}, timeout=10)
    print(f"\n9. Manifest: {r.status_code}")
    if r.status_code == 200:
        manifest = r.json()
        print(f"   subtitles={len(manifest.get('subtitles',[]))}")
        print(f"   audio_tracks={len(manifest.get('audio_tracks',[]))}")
        print(f"   downloads={len(manifest.get('downloads',[]))}")
    
    # 查文件
    print(f"\n10. Generated files:")
    for root, dirs, files in os.walk(STORAGE):
        for f in files:
            fp = os.path.join(root, f)
            print(f"   {os.path.relpath(fp, STORAGE)} ({os.path.getsize(fp)//1024}KB)")
