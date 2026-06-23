# AI Relationship OS

## v0.8.3 修复：联网导入作品消歧

- 修复“三国演义”等查询已找到联网验证人物但停在 `needs_disambiguation` 时，前端误弹 `No verified characters found` 的问题。
- 当搜索结果可能对应小说、电视剧、游戏或同名作品时，导入向导会先让用户选择作品版本，再继续导入。
- `needs_disambiguation` 不再触发 AI 未验证候选生成，避免把“需要确认版本”误判为“没有找到人物”。

## v0.8.2 新增：免费网页搜索 + 当前 AI 模型提取

- 人物世界联网导入默认改为 `free_web`：先用 DuckDuckGo HTML、Wikipedia/Wikidata 等公开网页资料搜索，再交给当前 AI 模型提取人物世界。
- Mimo、OpenAI-compatible、Ollama 都可以作为提取模型；它们本身不需要原生联网能力。
- OpenAI 原生 Web Search 保留为高级可选 provider，不再是默认导入方式。
- `POST /api/world-imports/search` 新增 `provider`，旧请求不传时自动使用 `free_web`。
- Flutter 设置页改为“联网搜索导入”，免费网页搜索不需要额外 Key；只有选中 OpenAI 原生 Web Search 时才显示对应配置。

## v0.8.1 热修：OpenAI Web Search 连接

- Web Search Base URL 填写 `https://api.openai.com` 时会自动规范化为 `https://api.openai.com/v1`。
- 误填完整 endpoint `https://api.openai.com/v1/responses` 时会自动折回 Base URL。
- HTTP 404 会明确提示端点不支持 Responses Web Search，不再误报为网络不可用。
## v0.8.0 新增：AI 联网导入角色世界

- 新增独立 OpenAI Web Search 配置，不影响原有 Mimo、OpenAI-compatible 或 Ollama 推演配置。
- `POST /api/world-imports/search` 创建可恢复后台任务，支持搜索、进度查询、取消、重试、同名作品消歧、AI 知识兜底和确认导入。
- 最多请求 50 名角色；如果联网只找到 N 人，就展示并允许导入 N 人，不伪造数量。
- 联网候选必须带真实 URL 来源；AI 生成兜底候选会标记为 `generated_unverified`，不会生成假链接。
- Flutter 新增“AI 联网导入世界”向导，可新建世界或追加到已有世界，并显示来源、置信度、错误原因和部分成功结果。
AI Relationship OS 是一套 Windows 单机关系认知系统，基于真实聊天记录自动构建人物画像、长期记忆、关系图谱与概率性关系推演。

**核心目标：成为用户现实世界关系的认知层。**

当前版本：**v0.8.3**

---

## 功能总览

### 聊天记录导入
- 支持格式：TXT、WhatsApp 导出、Telegram 导出、JSON、CSV
- 支持 PDF / 图片 OCR 提取（pypdf + Tesseract）
- 自动拆分联系人、结构化消息、去重指纹

### 人物画像
- AI 生成性格特征、沟通方式、兴趣、情绪模式、置信度评估
- 支持手动合并人物与批量生成画像

### 长期记忆与向量检索
- 从对话自动提取关键记忆（标注情绪与重要度）
- 向量存储支持语义搜索（SQLite 本地余弦相似度 / PostgreSQL pgvector）

### 关系图谱
- 人物关系地图（节点 + 连线 + 交互摘要）
- 关系时间线
- 知识图谱视图

### 关系推演
- 单人场景推演：多轮概率预测、场景分支对比
- 群体推演：多角色多轮博弈模拟
- 策略报告：自动生成 Markdown 报告并导出 PDF
- 所有推演均基于历史模式概率推断，禁止确定性预测

### 人物世界（Persona Worlds）
- 创建虚构或历史角色沙盘
- 本地人物目录 + 外部搜索（Wikidata / Wikipedia）
- 世界内人物推演与事件归档
- 世界数据导入/导出

### 数据管理
- 完整数据导出（JSON）
- 密码加密 `.rosbackup` 备份 / 恢复（兼容恢复旧版 ZIP）
- JSON 导出为明文，仅用于人工读取
- 设置本地数据目录迁移

---

## Windows 使用

1. 运行 `dist/RelationshipOS-Setup-0.8.3.exe` 安装。
2. 从开始菜单启动 **Relationship OS**。
3. 注册本机账号，在设置页填写 API Key（支持 OpenAI 兼容接口 / Ollama）。
4. 在导入页上传聊天文件，填写聊天中你的名称即可开始。

程序自动启动本地后端，无需安装 Python、PostgreSQL 或 Docker。
数据默认保存于 `%LOCALAPPDATA%\RelationshipOS`，可随时迁移目录。
只有调用 AI 功能时，必要文本才会发送到配置的模型服务。

---

## 技术架构

```
聊天记录 → 人物提取 → 长期记忆 → 向量数据库 → 推演引擎 → AI 输出
```

| 层 | 技术选型 |
|---|---|
| 前端 | Flutter (Windows) |
| 后端 | FastAPI + Uvicorn |
| 数据库 | SQLite（默认）/ PostgreSQL + pgvector |
| 缓存 | Redis |
| 存储 | MinIO / S3 |
| 加密 | AES-256-GCM 密码备份 + DPAPI（Windows 设置密钥） |
| AI | LLM API（OpenAI 兼容 / Ollama）+ 本地回退 |
| 打包 | PyInstaller + Inno Setup |

---

## 项目结构

```
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── api/routes/     # 路由：chat, person, simulate, graph, reports, worlds, data, system, group
│   │   ├── auth/           # JWT 认证
│   │   ├── models/         # SQLAlchemy 实体（25 张表）
│   │   ├── services/       # 核心服务：AI客户端、聊天解析、人物画像、嵌入、记忆、推演引擎等
│   │   ├── vector/         # 向量存储（pgvector / 余弦相似度回退）
│   │   └── catalog/        # 人物世界模板目录
│   ├── migrations/         # 数据库迁移
│   ├── docker/             # Docker 配置
│   └── tests/              # 后端测试
├── frontend/               # Flutter 客户端
│   └── lib/
│       ├── features/       # 页面：auth, home, import, persons, simulation, group, map, settings, startup, worlds
│       ├── models/         # 数据模型
│       ├── services/       # API 服务、凭据存储
│       └── widgets/        # 通用组件
├── scripts/                # 构建脚本（backend_entry, Build-Backend, Release-Windows）
├── installer/              # Inno Setup 安装脚本
├── tools/                  # 工具（git-shim）
└── docker-compose.yml      # 开发环境基础设施
```

---

## 开发指南

### 环境要求
- Python 3.11+
- Flutter SDK 3.4+
- （可选）Docker Desktop

### 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-build.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### 启动 Flutter 客户端

```powershell
cd frontend
flutter pub get
flutter run -d windows
```

### 基础设施（可选 PostgreSQL + Redis + MinIO）

```powershell
docker compose up -d
```

### 运行测试

```powershell
# 后端
cd backend
.\.venv\Scripts\python.exe -m pytest -q

# 前端
cd frontend
flutter test
```

### 构建发布

```powershell
powershell -ExecutionPolicy Bypass -File scripts\Release-Windows.ps1 -Version 0.8.3
```

发布脚本生成完整 ZIP、Inno Setup 安装程序及 SHA256 校验文件。

> `.rosbackup` 使用用户密码加密，忘记密码无法恢复。SQLite 数据库本身目前未整库加密；请保护 Windows 账号和本地数据目录。

---

## 顶层 AI 规则

- **禁止**："王总一定会生气"
- **允许**："根据历史聊天模式：62% 概率优先关注项目进度"
- 模型只能基于历史模式进行概率推测，不允许输出确定性预测。
