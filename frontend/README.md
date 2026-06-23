# AI Relationship OS —— Flutter 客户端

## v0.8.0 UI 重点

- 设置页新增独立 OpenAI Web Search 配置与连接测试。
- 人物世界页面新增 AI 联网导入向导：输入作品/世界描述、选择 1–50 人目标、查看后台进度、处理同名作品、预览来源并确认导入。
- 搜索失败会显示结构化中文原因；用户可显式选择 AI 知识生成未验证候选或补足到 50 人。
当前版本：**v0.8.1**

## 项目概述

AI Relationship OS 的 Flutter Windows 桌面客户端，与 FastAPI 后端配合，
提供聊天导入、人物管理、关系推演、群体博弈、人物世界等功能。

## 运行环境

- Flutter SDK 3.4+
- Dart SDK 3.4+
- Windows 10/11

## 项目结构

```
lib/
├── main.dart                  # 应用入口
├── app.dart                   # MaterialApp 与路由配置
├── features/
│   ├── auth/                  # 登录/注册页面
│   ├── startup/               # 启动页（后端健康检查）
│   ├── home/                  # 主页导航
│   ├── import/                # 聊天记录导入页面
│   ├── persons/               # 人物列表 + 详情页
│   ├── simulation/            # 单人场景推演
│   ├── group/                 # 群体推演
│   ├── map/                   # 关系图谱（拓扑图）
│   ├── worlds/                # 人物世界管理
│   └── settings/              # 系统设置
├── models/                    # 数据模型（DTO）
├── services/                  # API 服务、凭据存储、文件选择器
└── widgets/                   # 通用 UI 组件
```

## 启动开发

```powershell
cd frontend
flutter pub get
flutter run -d windows
```

客户端默认连接本地后端 `http://127.0.0.1:8000`。

首次启动或打包后运行，客户端会自动尝试启动后端 EXE 并等待健康检查通过。

## 运行测试

```powershell
flutter test
```

## 构建发布

前端由仓库根目录的构建脚本统一打包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\Release-Windows.ps1 -Version 0.8.1
```

构建产物包含 Flutter 编译的 `relationship_os.exe` 及所需 DLL。

## 技术要点

- 使用原生 Windows HTTP 客户端连接本机后端
- 本地凭据加密存储（DPAPI），不暴露 API Key
- Material Design 3 风格 UI
- 通过 `Process.start` 管理后端 EXE 生命周期
