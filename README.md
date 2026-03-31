---
title: AIAstro
emoji: ⭐
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# AstroChat ⭐

AI 驱动的专业占星分析平台 | AI-powered professional astrology analysis platform

基于 RAG（检索增强生成）技术，结合占星书籍语料与大语言模型，提供本命盘、行运、合盘、太阳回归等多维度星盘解读。

Built on RAG (Retrieval-Augmented Generation), combining astrological book corpus with LLMs to deliver multi-dimensional chart interpretations including natal charts, transits, synastry, and solar returns.

---

## 功能 Features

### ✅ 已上线 Live

|
 功能 Feature 
|
 说明 Description 
|
|
---
|
---
|
|
 本命盘分析 Natal Chart 
|
 行星落座/落宫、相位解读、格局标签（群星、大三角、T三角等），支持点击标签查看详情 — Planet sign/house placements, aspect interpretations, pattern tags (stellium, grand trine, T-square, etc.) with clickable detail tooltips 
|
|
 行运分析 Transits 
|
 每日行运相位 AI 四维解读（整体能量、重点相位、机遇挑战、建议） — Daily transit aspects with AI 4-dimension analysis (overall energy, key aspects, opportunities & challenges, advice) 
|
|
 合盘分析 Synastry 
|
 双人 SVG 盘图 + AI 关系多维度解读 — Dual-chart SVG + AI multi-dimensional relationship analysis 
|
|
 太阳回归盘 Solar Return 
|
 年度运势 RAG + Gemini 解读，含评分系统 — Annual forecast with RAG + Gemini interpretation and scoring 
|
|
 出生时间校正 Rectification 
|
 三阶段校正：人生事件扫描 → 上升星座性格问卷 → 生命主题置信度验证 — 3-phase: life event scan → ASC personality quiz → life theme confidence check 
|
|
 用户系统 User System 
|
 注册登录 + 星盘保存 + 访客模式 + 待审核队列 — Registration/login + chart saving + guest mode + review queue 
|
|
 国内访问 CN Access 
|
 自动检测地区，一键切换 DeepSeek + 高德地图 — Auto region detection, one-click switch to DeepSeek + Amap 
|
|
 移动端适配 Mobile 
|
 全站响应式布局 — Fully responsive layout 
|

### 🚧 开发中 In Development

|
 功能 Feature 
|
 说明 Description 
|
|
---
|
---
|
|
 推运 Progressions 
|
 次限/三限推运分析 — Secondary/tertiary progressions 
|
|
 方向法 Directions 
|
 主限/太阳弧方向法 — Primary directions / solar arc 
|
|
 合盘评分 Synastry Scoring 
|
 关系维度评分与排序 — Multi-dimensional relationship scoring & ranking 
|

---

## 技术栈 Tech Stack

|
 层 Layer 
|
 技术 Technology 
|
|
---
|
---
|
|
 前端 Frontend 
|
 React + Vite + Tailwind CSS 
|
|
 后端 Backend 
|
 Python FastAPI + Kerykeion 
|
|
 AI 模型 AI Models 
|
 Google Gemini (overseas) / DeepSeek (China), auto fallback 
|
|
 RAG 
|
 Qdrant Cloud vector search + astrology book corpus 
|
|
 数据库 Database 
|
 SQLite (local) / Turso libSQL (production) 
|
|
 部署 Deployment 
|
 HuggingFace Spaces (Docker) 
|

---

## 项目结构 Project Structure
AIAstro/
├── frontend/ # React frontend
│ └── src/
│ ├── components/ # UI components
│ ├── contexts/ # Auth / ChartSession / Region
│ ├── pages/ # Feature pages
│ └── utils/ # Utilities
├── astrology_api/ # FastAPI backend
│ └── app/
│ ├── api/ # Routers (natal, transit, synastry, interpret, etc.)
│ ├── core/ # Calculation engine
│ ├── rag.py # RAG core module
│ └── db.py # Database ORM
├── CHANGELOG.md
└── README.md

text

---

## 本地开发 Local Development

### 环境要求 Prerequisites
- Node.js 18+
- Python 3.9+

### 启动后端 Start Backend

```bash
cd astrology_api
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env           # Configure API keys
uvicorn main:app --port 8001 --reload
启动前端 Start Frontend
bash
cd frontend
npm install
npm run dev
访问 Visit http://localhost:5173

环境变量 Environment Variables
变量 Variable	用途 Purpose	必需 Required
GOOGLE_API_KEY	Gemini API	✅
QDRANT_URL	Qdrant Cloud endpoint	✅
QDRANT_API_KEY	Qdrant API key	✅
JWT_SECRET	JWT signing secret	✅
AUTH_USERNAME	Admin username	✅
AUTH_PASSWORD	Admin password	✅
TURSO_DATABASE_URL	Turso database (production)	Production only
TURSO_AUTH_TOKEN	Turso auth token	Production only
DEEPSEEK_API_KEY	DeepSeek API (China region)	Optional
VITE_AMAP_KEY	Amap / 高德地图 key (China region)	Optional
致谢 Acknowledgments
本项目 fork 自 Bessaq/asoaosq，原项目为基于 Kerykeion 的 Python FastAPI 星盘计算 API。

This project is forked from Bessaq/asoaosq, a Python FastAPI astrological calculation API built on Kerykeion.

License
MIT

text

---

确认内容没问题后：

```bash
del frontend\README.md
del astrology_api\README.md
git add -A
git commit -m "docs: rewrite README (zh/en bilingual), remove outdated READMEs"