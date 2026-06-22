AI Relationship OS —— Windows 使用说明
========================================

当前版本：v0.7.0

一、安装与启动
1. 推荐运行 RelationshipOS-Setup-0.7.0.exe 完成安装。
2. 也可以解压 ZIP，但必须保留 relationship_os.exe、data、backend 和 DLL 的相对位置。
3. 启动 AI Relationship OS。客户端会自动启动本机后端，并等待健康检查通过。
4. 关闭客户端后，由客户端启动的后端进程会一并退出。

二、数据与网络
- 客户端只连接本机 http://127.0.0.1:8000。
- 数据目录和日志目录由后端配置决定；正式版默认位于 %LOCALAPPDATA%\RelationshipOS。
- 可在设置页迁移数据目录到其他位置。
- 只有使用 AI 功能时，必要文本才会发送到已配置的远程模型服务。
- 支持 OpenAI 兼容接口（如 MiMo）和本地 Ollama 模型（如 Gemma）。
- 安装包不包含真实 API Key；请在应用设置页首次配置。

三、功能使用
1. 注册本机账号 → 填写 API Key（设置页）。
2. 导入聊天记录：支持 TXT、WhatsApp、Telegram、JSON、CSV 等格式。
   - 也支持 PDF 和图片 OCR 提取。
   - 上传后需填写聊天中你的名称。
3. 人物管理：查看 AI 生成的画像，手动合并或批量生成。
4. 关系推演：选择人物，输入场景，获取概率预测和场景对比。
5. 群体推演：多角色多轮博弈模拟。
6. 关系图谱：查看人物关系拓扑图、时间线和知识图谱。
7. 人物世界：创建虚构/历史角色沙盘，外部知识搜索导入。
8. 数据管理：明文 JSON 导出、密码加密 .rosbackup 备份与恢复，并兼容恢复旧版 ZIP。

备份密码不会保存，忘记密码后无法恢复。.rosbackup 使用 AES-256-GCM 加密；
本地 SQLite 数据库本身目前未整库加密，请保护 Windows 账号和数据目录。

四、常见问题
- 提示"未找到后端程序"：重新安装，或确认 backend\relationship_os_backend.exe 未被安全软件隔离。
- 提示"后端启动超时"：确认本机 8000 端口未被其他程序占用，并查看 %LOCALAPPDATA%\RelationshipOS\logs。
- 直接解压 ZIP 后无法启动：请完整解压，不要只复制 EXE。
- AI 调用失败：检查 API Key 和网络；可尝试切换到 Ollama 本地模式。

五、开发者发布
1. 安装锁定的构建依赖：backend\.venv\Scripts\python.exe -m pip install --require-hashes -r backend\requirements-build.txt
2. 安装 Inno Setup 6。
3. 在仓库根目录运行：
   powershell -ExecutionPolicy Bypass -File scripts\Release-Windows.ps1 -Version 0.7.0
4. 若只生成 ZIP：
   powershell -ExecutionPolicy Bypass -File scripts\Release-Windows.ps1 -Version 0.7.0 -SkipInstaller
5. 发布目录会同时生成 ZIP、安装程序和 SHA256 校验文件。

发布脚本直接调用 Flutter SDK 的 dart.exe 与 flutter_tools.snapshot，
保留当前 Flutter snapshot workaround，不依赖 flutter.bat。
