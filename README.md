# Video Multi-SRT Multi-HLS

> AI 短剧多语种翻译与音轨外切平台 — 上传视频，一键生成多语言字幕和配音，播放器自由切换。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript: 5.0+](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)](https://www.typescriptlang.org/)

## ✨ 功能特性

- 🎬 **视频上传** — 支持主流视频格式（MP4/MOV/MKV/WebM）
- 🎵 **声源分离** — 自动分离人声和背景音乐（基于 Demucs）
- 📝 **语音识别** — 自动转录源语言字幕（基于 faster-whisper）
- 🌐 **AI 翻译** — 多语种翻译，保留短剧口语化风格（基于 DeepSeek LLM）
- 🔊 **AI 配音** — 多语种语音合成，保留背景音乐（基于 Step TTS）
- 🎭 **外切字幕/音轨** — 原视频不动，字幕和音轨是独立文件，播放器自由切换
- 📦 **一键打包** — 生成字幕、音轨、Manifest，打包下载

## 🏗️ 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    Web Frontend (React)                   │
│  上传视频 → 预览播放 → 切字幕/切音轨 → 下载               │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP API (Spec §7)
┌────────────────────────┴────────────────────────────────┐
│                  Backend API (FastAPI)                    │
│  项目管理 / 状态机 / 对象存储 / 鉴权审计                  │
└────────────────────────┬────────────────────────────────┘
                         │ Skill 契约 (Spec §6)
┌────────────────────────┴────────────────────────────────┐
│               Agent Runtime (编排层)                      │
│  固定模板 / Run Context / 人工 Checkpoint / 重试          │
└────────────────────────┬────────────────────────────────┘
                         │
    ┌────────────┬───────┴───────┬────────────┬───────────┐
    ▼            ▼               ▼            ▼           ▼
┌────────┐ ┌────────┐    ┌──────────┐ ┌──────────┐ ┌─────────┐
│ Media  │ │  ASR   │    │Localize  │ │  Voice   │ │Packaging│
│FFmpeg  │ │Whisper │    │DeepSeek  │ │Step TTS  │ │SRT/VTT  │
│Demucs  │ │        │    │          │ │          │ │Mix/Zip  │
└────────┘ └────────┘    └──────────┘ └──────────┘ └─────────┘
```

## 🚀 快速开始

### 前置依赖

| 依赖 | 用途 | 安装方式 |
|------|------|----------|
| Python 3.11+ | 后端运行时 | [python.org](https://www.python.org/downloads/) |
| Node.js 18+ | 前端构建 | [nodejs.org](https://nodejs.org/) |
| FFmpeg | 音视频处理 | `brew install ffmpeg` / `choco install ffmpeg` |
| Redis | 任务队列 | `brew install redis` / `choco install redis` |

### 1. 克隆项目

```bash
git clone https://github.com/pengcong2020520/video-multisrt-multiHLS.git
cd video-multisrt-multiHLS
```

### 2. 后端配置

```bash
cd apps/api

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -e ".[dev]"
pip install faster-whisper demucs openai torchcodec

# 配置环境变量
cp ../../.env.example .env
# 编辑 .env 填入你的 API Key
```

### 3. 启动后端

```bash
# 启动 Redis
brew services start redis  # Windows: redis-server --service-start

# 启动 API 服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 启动前端

```bash
cd apps/web
npm install
npm run dev
```

打开 http://localhost:5173 即可使用。

## 🔑 环境变量配置

在项目根目录创建 `.env` 文件：

```env
# DeepSeek API (翻译)
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# Step TTS API (语音合成)
STEP_API_KEY=your_step_api_key
STEP_BASE_URL=https://api.stepfun.com/step_plan/v1
STEP_TTS_MODEL=stepaudio-2.5-tts

# 数据库 (MVP 用 SQLite)
DATABASE_URL=sqlite:///./api.sqlite3

# Redis
REDIS_URL=redis://localhost:6379/0

# 对象存储
STORAGE_ROOT=./storage
SIGNED_URL_SECRET=your_secret_here

# 鉴权 (MVP 关闭)
AUTH_ENABLED=false
```

## 📂 项目结构

```
video-multisrt-multi-hls/
├── apps/
│   ├── api/                 # FastAPI 后端
│   │   ├── app/
│   │   │   ├── main.py      # 应用入口
│   │   │   ├── routes.py    # API 路由 (Spec §7)
│   │   │   ├── models.py    # 数据模型 (Spec §4)
│   │   │   ├── services.py  # 业务逻辑 + 状态机
│   │   │   ├── runtime.py   # AgentRuntime 适配层
│   │   │   ├── skill_runner.py   # CompositeSkillRunner
│   │   │   └── persister.py # DB 持久化
│   │   └── tests/
│   └── web/                 # React 前端
│       ├── src/
│       │   ├── pages/       # 7 个页面
│       │   ├── components/  # CustomPlayer 等
│       │   └── api/         # API Client
│       └── package.json
├── packages/
│   ├── shared-types/        # TypeScript 类型契约 (zod)
│   ├── agent-runtime/       # 编排引擎
│   └── skills/              # 5 个 Skill 包
│       ├── media/           # FFmpeg + Demucs
│       ├── asr/             # faster-whisper
│       ├── localization/    # DeepSeek 翻译
│       ├── voice/           # Step TTS
│       └── packaging/       # 字幕/混音/打包
├── docs/                    # 设计文档 (Spec FROZEN)
├── tasks/                   # 任务卡
└── tests/                   # E2E 测试
```

## 🎬 使用流程

```
上传视频 → 自动处理(ASR→翻译→字幕) → 校对编辑 → 继续处理(TTS→混音→打包)
→ 预览播放(切字幕/切音轨) → 下载
```

## 📝 支持的语言

| 代码 | 语言 |
|------|------|
| zh-CN | 中文 |
| en-US | 英语 |
| es-ES | 西班牙语 |
| es-MX | 墨西哥西班牙语 |
| pt-BR | 葡萄牙语（巴西） |

## 📖 文档

- [技术规格 (Spec FROZEN)](docs/spec.md) — 完整 API/数据模型/状态机定义
- [架构设计](docs/architecture.md) — 技术方案与播放器设计
- [产品需求](docs/prd.md) — 功能需求与用户故事
- [Agent/Skill 架构](docs/agent-skill-architecture.md) — 编排模板与 Skill 契约

## 📄 License

MIT License - 见 [LICENSE](LICENSE) 文件
