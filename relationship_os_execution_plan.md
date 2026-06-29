# AI Relationship OS —— 项目长期执行方案

## 产品定位

AI Relationship OS 帮助用户导入真实聊天记录，自动构建人物画像、关系记忆和关系推演能力，让 AI 理解用户现实世界的人际关系。

核心目标：

> 成为用户现实世界关系的认知层

当前版本：**v0.8.4**

---

## 第一阶段（0——3 个月）

目标：验证需求与留存

成功指标：

- 100——300 名内测用户
- 7 日留存 >25%
- 平均每人建立 >5 个人物
- 每周使用 >3 次

### 核心功能

#### 1. 聊天记录导入

支持格式：

- TXT
- WhatsApp 导出
- Telegram 导出
- JSON / CSV
- PDF / 图片 OCR 提取

流程：上传记录 → 联系人拆分 → 消息结构化 → 指纹去重 → 数据库

#### 2. 人物画像生成

输出：

- 性格特征
- 沟通方式
- 兴趣
- 情绪模式
- 关键词
- 置信度

#### 3. AI 关系推演

输入："我要请假两天" → 输出：65% 先问项目进度 / 20% 同意 / 15% 拒绝

原因：项目话题出现 12 次，重视结果

---

## 第二阶段（3——6 个月）—— 已完成

新增能力（v0.4——v0.6.2）：

### 人物世界（Persona Worlds）
- 虚构或真实人物沙盘模拟
- 本地人物目录 + Wikidata / Wikipedia 外部搜索导入
- 世界内人物推演、事件归档
- 世界数据导入/导出

### 群体推演
- 多角色多轮博弈模拟
- 各角色立场演变与共识分析

### 策略报告
- 推演会话自动生成 Markdown 报告
- 支持导出 PDF

### 关系图谱
- 人物关系拓扑图
- 关系时间线
- 知识图谱视图

### 数据管理
- 完整数据导出（JSON）
- AES-256-GCM 密码加密 `.rosbackup` / 旧版 ZIP 恢复兼容
- 数据目录可迁移

---

## 技术架构

```
聊天记录 → 人物提取 → 长期记忆 → 向量数据库 → 推演引擎 → AI 输出
```

### 技术栈

| 层 | 技术 | 说明 |
|---|---|---|
| 前端 | Flutter (Windows) | Dart SDK 3.4+ |
| 后端 | FastAPI + Uvicorn | Python 3.11+ |
| 数据库 | SQLite / PostgreSQL + pgvector | 默认 SQLite 单机部署 |
| 缓存 | Redis | 开发环境使用，单机版可跳过 |
| 存储 | MinIO / S3 | 开发环境使用，单机版本地存储 |
| 加密 | AES-256-GCM + DPAPI | 密码备份加密；Windows DPAPI 保护本地设置密钥 |
| AI 客户端 | OpenAI 兼容接口 / Ollama | 支持 MiMo、Gemma 等模型；含本地回退 |
| 嵌入 | 远程 API / 本地哈希回退 | 不依赖嵌入服务即可工作 |
| 打包 | PyInstaller + Inno Setup | 生成独立 EXE 和安装程序 |

### 数据库结构（25 张表）

```
users、persons、messages、person_memories、relationships
message_vectors、simulation_logs、simulation_sessions
simulation_messages、simulation_evidences
relationship_events、relationship_event_evidences
communication_scenarios、strategy_reports
group_simulations、group_simulation_rounds
persona_worlds、world_personas、world_relationships
world_sources、world_import_tasks
world_simulations、world_simulation_rounds、world_events
import_tasks
```

---

## 项目目录

```
backend/
├── app/
│   ├── api/routes/
│   │   ├── chat.py            # 聊天导入、消息管理
│   │   ├── person.py          # 人物管理、画像生成
│   │   ├── simulate.py        # 单人场景推演
│   │   ├── group_simulations.py  # 群体推演
│   │   ├── graph.py           # 关系图谱
│   │   ├── reports.py         # 策略报告
│   │   ├── worlds.py          # 人物世界
│   │   ├── data.py            # 数据导出/备份/恢复
│   │   └── system.py          # 系统设置、认证
│   ├── models/                # 25 个 SQLAlchemy 实体
│   ├── services/              # AI 客户端、聊天解析、画像、嵌入、记忆、推演引擎等
│   ├── vector/                # 向量存储（pgvector / 余弦相似度回退）
│   ├── catalog/               # 人物世界模板目录
│   └── auth/                  # JWT 认证
├── migrations/
├── docker/
└── tests/

frontend/
└── lib/
    ├── features/              # 页面：auth, home, import, persons, simulation, group, map, settings, startup, worlds
    ├── models/                # 数据模型
    ├── services/              # API 服务、凭据存储、文件选择器
    └── widgets/               # 通用组件

scripts/                       # 构建脚本
installer/                     # Inno Setup 配置
```

---

## 开发路线

### 已完成（Week 1——12）

- [x] 用户认证（JWT）
- [x] 数据库架构（25 张表 + 增量迁移）
- [x] 聊天记录导入（多格式）
- [x] PDF / 图片 OCR 提取
- [x] 人物画像生成（含本地回退）
- [x] 长期记忆提取
- [x] 向量检索（SQLite + pgvector 双模式）
- [x] 关系事件提取
- [x] AI 关系推演（单人 + 场景对比）
- [x] 关系图谱（拓扑图 + 时间线 + 知识图谱）
- [x] 群体推演
- [x] 策略报告 + PDF 导出
- [x] 人物世界模块
- [x] 外部知识导入（Wikidata / Wikipedia）
- [x] 明文 JSON 导出 / AES-256-GCM 密码备份 / 旧版 ZIP 恢复
- [x] Windows 安装程序打包

### 后续规划

- [ ] 微信聊天记录解析
- [ ] 多语言支持
- [ ] 桌面端 UI 优化
- [ ] 内测收集与留存优化

---

## 顶层 AI 规则

禁止："王总一定会生气"

允许："根据历史聊天模式：62% 概率优先关注项目进度"

规则：模型只能进行基于历史模式的概率推测，不允许输出确定性预测。
---

## v0.8.0 已实现

- 独立 OpenAI Web Search 适配层，基于 Responses API `web_search` 工具获取角色世界候选与来源。
- 世界导入任务升级为后台任务：`queued/searching/extracting/needs_disambiguation/preview/partial/failed/completed/discarded`。
- 新增结构化错误协议、显式 AI 知识兜底、真实 URL 验证、50 人容量限制、新建/追加导入和去重保护。
- Flutter 完成设置页配置检查、搜索向导、进度/错误/来源预览、联网验证/AI 生成候选筛选和导入目标选择。
- 构建号：`0.8.0+9`。
---

## v0.8.1 已实现

- 修复 OpenAI Web Search Base URL 漏 `/v1` 时连接测试请求到 `/responses` 的问题。
- HTTP 404 改为 `WEB_SEARCH_UNSUPPORTED`，提示检查 `https://api.openai.com/v1`，不再误报 `NETWORK_UNAVAILABLE`。
- Flutter 构建号：`0.8.1+10`。
---

## v0.8.2 已实现
- 人物世界联网导入新增默认 `free_web` provider：免费网页搜索 + 当前 AI 模型提取，不要求 OpenAI 原生 Web Search。
- OpenAI 原生 Web Search 保留为可选高级 provider；后端 `POST /api/world-imports/search` 支持 `provider=free_web|openai_web_search`，旧请求默认 `free_web`。
- Flutter 设置页和导入向导增加 provider 选择，免费网页搜索不显示 OpenAI Web Search Key/Base URL/Model。
- Flutter 构建号：`0.8.2+11`。

---

## v0.8.3 已实现
- 修复人物世界联网导入的 `needs_disambiguation` 前端状态处理。
- 当作品存在小说、电视剧、游戏或同名版本歧义时，Flutter 会显示版本选择弹窗，选择后调用 `/resolve` 继续任务。
- `needs_disambiguation` 不再误触发 “No verified characters found” 或 AI 未验证候选生成。
- Flutter 构建号：`0.8.3+12`。
