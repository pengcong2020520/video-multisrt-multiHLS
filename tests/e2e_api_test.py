#!/usr/bin/env python3
"""
端到端 API 级别测试 — 验证完整链路：
上传 → probe → extract_audio → separate_sources → ASR → translate → proofreading →
subtitle → TTS → stitch → mix → manifest → zip

用第一性原理：每一步都验证上一步的输出是否合理，而不是盲目继续。
"""
import os
import sys
import json
import time
import requests
import tempfile

# 配置
API_BASE = "http://localhost:8000/api"
TEST_VIDEO = os.path.expanduser("~/jarvis/projects/video-multisrt-multi-hls/tests/fixtures/test_short_drama.mp4")
AUTH_HEADERS = {"X-User-Id": "test_user"}
TIMEOUT = 120

def step(name, n, total=14):
    print(f"\n{'='*60}")
    print(f"  [{n}/{total}] {name}")
    print(f"{'='*60}")

def assert_ok(resp, expected_status=200):
    if resp.status_code != expected_status:
        print(f"❌ HTTP {resp.status_code}: {resp.text[:500]}")
        sys.exit(1)
    print(f"✅ HTTP {resp.status_code}")

def assert_not_empty(value, name):
    if not value:
        print(f"❌ {name} is empty!")
        sys.exit(1)
    print(f"✅ {name}: {str(value)[:100]}")

TOTAL = 14

# ============================================================
# Step 1: 健康检查
# ============================================================
step("健康检查", 1, TOTAL)
resp = requests.get("http://localhost:8000/healthz", timeout=10)
assert_ok(resp)
print(f"Response: {resp.json()}")

# ============================================================
# Step 2: 创建项目
# ============================================================
step("创建项目", 2, TOTAL)
resp = requests.post(f"{API_BASE}/projects", 
    json={
        "name": "e2e_test_001",
        "source_language": "zh-CN",
        "target_languages": ["en-US"],
        "translation_style": "short_drama_localized"
    },
    headers=AUTH_HEADERS, timeout=TIMEOUT)
assert_ok(resp)  # 200 or 201
project = resp.json()
project_id = project["project_id"]
upload_url = project.get("upload_url", "")
assert_not_empty(project_id, "project_id")
print(f"Project: {json.dumps(project, indent=2, ensure_ascii=False)}")

# ============================================================
# Step 3: 上传视频
# ============================================================
step("上传视频", 3, TOTAL)
# 直接把文件复制到 storage 目录（MVP 本地存储）
# 先检查 upload_url 是不是本地路径
print(f"upload_url: {upload_url}")
# 通过签名 URL 上传
if upload_url and upload_url.startswith("http"):
    with open(TEST_VIDEO, "rb") as f:
        resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"}, timeout=TIMEOUT)
        if resp.status_code in (200, 201, 204):
            print(f"✅ 上传成功 ({resp.status_code})")
        else:
            # 签名 URL 上传不工作，直接复制到本地存储
            print(f"⚠️ PUT 上传返回 {resp.status_code}，尝试本地复制")
            storage_root = os.path.expanduser("~/jarvis/projects/video-multisrt-multi-hls/apps/api/storage")
            project_storage = os.path.join(storage_root, project_id, "source")
            os.makedirs(project_storage, exist_ok=True)
            import shutil
            shutil.copy(TEST_VIDEO, os.path.join(project_storage, "source.mp4"))
            print(f"✅ 文件已复制到 {project_storage}/source.mp4")
else:
    # 本地存储模式：直接把文件放到 storage 目录
    storage_root = os.path.expanduser("~/jarvis/projects/video-multisrt-multi-hls/apps/api/storage")
    project_storage = os.path.join(storage_root, project_id, "source")
    os.makedirs(project_storage, exist_ok=True)
    import shutil
    shutil.copy(TEST_VIDEO, os.path.join(project_storage, "source.mp4"))
    print(f"✅ 文件已复制到 {project_storage}/source.mp4")

# ============================================================
# Step 4: 提交处理（subtitle_draft 模板，先跑到翻译）
# ============================================================
step("提交处理 (subtitle_draft)", 4, TOTAL)
resp = requests.post(f"{API_BASE}/projects/{project_id}/process",
    json={
        "enable_source_separation": True,
        "enable_diarization": False,
        "generate_tts": False,
        "generate_preview_mp4": False,
        "agent_template": "subtitle_draft"
    },
    headers=AUTH_HEADERS, timeout=TIMEOUT)
assert_ok(resp)
run_data = resp.json()
run_id = run_data.get("run_id")
assert_not_empty(run_id, "run_id")
print(f"Run: {json.dumps(run_data, indent=2)}")

# ============================================================
# Step 5: 等待处理完成（轮询 AgentRun 状态）
# ============================================================
step("等待处理完成", 5, TOTAL)
max_wait = 300  # 5 分钟
waited = 0
final_status = None
agent_run = None
skill_runs = []

while waited < max_wait:
    resp = requests.get(f"{API_BASE}/agent-runs/{run_id}",
        headers=AUTH_HEADERS, timeout=TIMEOUT)
    assert_ok(resp)
    data = resp.json()
    agent_run = data.get("agent_run", {})
    skill_runs = data.get("skill_runs", [])
    status = agent_run.get("status", "unknown")
    current_step = agent_run.get("current_step", "")
    
    print(f"  [{waited}s] status={status}, step={current_step}, skills={len(skill_runs)}")
    
    if status in ("succeeded", "failed", "waiting_human"):
        final_status = status
        break
    
    time.sleep(5)
    waited += 5

print(f"\n最终状态: {final_status}")
if final_status == "failed":
    print(f"❌ 处理失败！")
    print(f"AgentRun: {json.dumps(agent_run, indent=2, ensure_ascii=False)}")
    for sr in skill_runs:
        if sr.get("status") == "failed":
            print(f"Failed SkillRun: {json.dumps(sr, indent=2, ensure_ascii=False)}")
    sys.exit(1)

# ============================================================
# Step 6: 检查 SkillRun 记录
# ============================================================
step("检查 SkillRun 记录", 6, TOTAL)
print(f"SkillRun 数量: {len(skill_runs)}")
for sr in skill_runs:
    print(f"  - {sr.get('skill_name')}: {sr.get('status')} ({sr.get('started_at','')} → {sr.get('finished_at','')})")
    if sr.get("error"):
        print(f"    error: {sr['error']}")

# ============================================================
# Step 7: 检查项目详情
# ============================================================
step("检查项目详情", 7, TOTAL)
resp = requests.get(f"{API_BASE}/projects/{project_id}",
    headers=AUTH_HEADERS, timeout=TIMEOUT)
assert_ok(resp)
project_detail = resp.json()
print(f"Project status: {project_detail.get('project', {}).get('status')}")
print(f"Duration: {project_detail.get('project', {}).get('duration_ms')}ms")
print(f"Assets: {len(project_detail.get('assets', []))}")
for a in project_detail.get("assets", []):
    print(f"  - {a.get('type')}: {a.get('uri','')[:80]}")
print(f"Languages: {project_detail.get('languages', [])}")

# ============================================================
# Step 8: 检查 Segments（ASR 结果）
# ============================================================
step("检查 Segments（ASR 结果）", 8, TOTAL)
resp = requests.get(f"{API_BASE}/projects/{project_id}/segments?target_language=en-US",
    headers=AUTH_HEADERS, timeout=TIMEOUT)
assert_ok(resp)
segments_data = resp.json()
segments = segments_data.get("segments", [])
print(f"Segments 数量: {len(segments)}")
for seg in segments[:5]:
    s = seg.get("segment", {})
    t = seg.get("translation", {})
    print(f"  [{s.get('start_ms','?')}-{s.get('end_ms','?')}] {s.get('source_text','')}")
    print(f"    → {t.get('text','(无翻译)')}")
    if seg.get("tts_job"):
        print(f"    TTS: {seg['tts_job'].get('status','?')}")

if len(segments) == 0:
    print("⚠️ 没有 segments！ASR 可能没有识别到内容。")

# ============================================================
# Step 9: 如果在 waiting_human，继续执行（生成 TTS + 混音 + 打包）
# ============================================================
if final_status == "waiting_human":
    step("继续执行（continue → TTS + 混音 + 打包）", 9, TOTAL)
    resp = requests.post(f"{API_BASE}/agent-runs/{run_id}/continue",
        json={"checkpoint": "proofreading", "confirmed": True},
        headers=AUTH_HEADERS, timeout=TIMEOUT)
    assert_ok(resp)
    print(f"Continue: {resp.json()}")
    
    # 等待完成
    waited2 = 0
    while waited2 < max_wait:
        resp = requests.get(f"{API_BASE}/agent-runs/{run_id}",
            headers=AUTH_HEADERS, timeout=TIMEOUT)
        data = resp.json()
        status = data.get("agent_run", {}).get("status", "")
        step_name = data.get("agent_run", {}).get("current_step", "")
        print(f"  [{waited2}s] status={status}, step={step_name}")
        if status in ("succeeded", "failed"):
            final_status = status
            break
        time.sleep(5)
        waited2 += 5
    
    print(f"最终状态: {final_status}")
    if final_status == "failed":
        print(f"❌ 生成阶段失败！")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        sys.exit(1)
else:
    step("跳过 continue（非 waiting_human 状态）", 9, TOTAL)
    print(f"当前状态: {final_status}")

# ============================================================
# Step 10: 检查最终 Segments（含翻译和 TTS）
# ============================================================
step("检查最终 Segments（含翻译和 TTS）", 10, TOTAL)
resp = requests.get(f"{API_BASE}/projects/{project_id}/segments?target_language=en-US",
    headers=AUTH_HEADERS, timeout=TIMEOUT)
assert_ok(resp)
segments_data = resp.json()
segments = segments_data.get("segments", [])
print(f"Segments 数量: {len(segments)}")
for seg in segments[:5]:
    s = seg.get("segment", {})
    t = seg.get("translation", {})
    tts = seg.get("tts_job", {})
    print(f"  [{s.get('start_ms','?')}-{s.get('end_ms','?')}] {s.get('source_text','')}")
    print(f"    → {t.get('text','(无翻译)')}")
    print(f"    TTS: status={tts.get('status','?')}, voice={tts.get('voice_id','?')}, dur={tts.get('actual_duration_ms','?')}ms")

# ============================================================
# Step 11: 检查 Manifest
# ============================================================
step("检查 Manifest", 11, TOTAL)
resp = requests.get(f"{API_BASE}/projects/{project_id}/manifest",
    headers=AUTH_HEADERS, timeout=TIMEOUT)
if resp.status_code == 200:
    manifest = resp.json()
    print(f"Manifest: {json.dumps(manifest, indent=2, ensure_ascii=False)[:1000]}")
    print(f"  字幕数: {len(manifest.get('subtitles', []))}")
    print(f"  音轨数: {len(manifest.get('audio_tracks', []))}")
    print(f"  下载数: {len(manifest.get('downloads', []))}")
else:
    print(f"⚠️ Manifest 不可用: HTTP {resp.status_code}")
    print(f"  {resp.text[:300]}")

# ============================================================
# Step 12: 请求下载包
# ============================================================
step("请求下载包", 12, TOTAL)
resp = requests.post(f"{API_BASE}/projects/{project_id}/packages",
    json={"version_id": "v1", "languages": ["en-US"], "include_intermediate_assets": True},
    headers=AUTH_HEADERS, timeout=TIMEOUT)
if resp.status_code in (200, 201):
    pkg = resp.json()
    print(f"Package: {json.dumps(pkg, indent=2)}")
else:
    print(f"⚠️ 下载包请求失败: HTTP {resp.status_code}")
    print(f"  {resp.text[:300]}")

# ============================================================
# Step 13: 检查生成的文件
# ============================================================
step("检查生成的文件", 13, TOTAL)
storage_root = os.path.expanduser("~/jarvis/projects/video-multisrt-multi-hls/apps/api/storage")
project_storage = os.path.join(storage_root, project_id)
if os.path.exists(project_storage):
    for root, dirs, files in os.walk(project_storage):
        for f in files:
            fpath = os.path.join(root, f)
            size = os.path.getsize(fpath)
            relpath = os.path.relpath(fpath, project_storage)
            print(f"  {relpath} ({size//1024}KB)")
else:
    print(f"⚠️ 存储目录不存在: {project_storage}")

# ============================================================
# Step 14: 总结
# ============================================================
step("总结", 14, TOTAL)
print(f"项目 ID: {project_id}")
print(f"最终状态: {final_status}")
print(f"SkillRun 数: {len(skill_runs)}")
print(f"Segments 数: {len(segments)}")
print(f"\n{'='*60}")
if final_status == "succeeded":
    print("🎉 端到端测试通过！")
else:
    print(f"⚠️ 端到端测试未完全成功，最终状态: {final_status}")
print(f"{'='*60}")
