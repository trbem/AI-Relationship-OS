import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import '../../models/chat_preview.dart';
import '../../models/import_task.dart';
import '../../services/api_service.dart';
import '../../services/windows_file_picker.dart';

class ImportPage extends StatefulWidget {
  const ImportPage({super.key, required this.apiService});

  final ApiService apiService;

  @override
  State<ImportPage> createState() => _ImportPageState();
}

class _ImportPageState extends State<ImportPage> {
  final _selfNameController = TextEditingController();
  final _filePicker = const WindowsFilePicker();
  SelectedFile? _selectedFile;
  ChatPreview? _preview;
  ImportTask? _task;
  bool _selecting = false;
  bool _uploading = false;
  String? _error;
  Timer? _pollTimer;

  Future<void> _selectFile() async {
    setState(() {
      _selecting = true;
      _error = null;
    });
    try {
      final selected = await _filePicker.pickChatFile();
      if (selected != null && mounted) {
        final file = File(selected.path);
        final preview = await widget.apiService.previewChat(
          filename: selected.name,
          bytes: await file.readAsBytes(),
        );
        setState(() {
          _selectedFile = selected;
          _preview = preview;
          _task = null;
          if (preview.senderNames.length == 2 &&
              !_selfNameController.text.trim().isNotEmpty) {
            _selfNameController.text = preview.senderNames.first;
          }
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _selecting = false);
    }
  }

  Future<void> _upload() async {
    final selected = _selectedFile;
    final selfName = _selfNameController.text.trim();
    if (selected == null) {
      setState(() => _error = '请先选择聊天记录文件。');
      return;
    }
    if (selfName.isEmpty) {
      setState(() => _error = '请输入聊天记录中代表你自己的发送者名称。');
      return;
    }

    final file = File(selected.path);
    if (!await file.exists()) {
      setState(() => _error = '所选文件已不存在，请重新选择。');
      return;
    }
    if (await file.length() > 50 * 1024 * 1024) {
      setState(() => _error = '文件超过 50 MB，请拆分后导入。');
      return;
    }
    if (_preview == null || !_preview!.senderNames.contains(selfName)) {
      setState(() => _error = '请选择预览中识别到的本人名称。');
      return;
    }

    setState(() {
      _uploading = true;
      _error = null;
      _task = null;
    });
    try {
      final task = await widget.apiService.createImportTask(
        filename: selected.name,
        bytes: await file.readAsBytes(),
        selfName: selfName,
      );
      if (!mounted) return;
      setState(() => _task = task);
      if (!task.isFinished && task.id.isNotEmpty) _startPolling();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(
      const Duration(seconds: 2),
      (_) => _refreshTask(),
    );
    _refreshTask();
  }

  Future<void> _refreshTask() async {
    final taskId = _task?.id;
    if (taskId == null || taskId.isEmpty) return;
    try {
      final task = await widget.apiService.fetchImportTask(taskId);
      if (!mounted) return;
      setState(() => _task = task);
      if (task.isFinished) _pollTimer?.cancel();
    } catch (error) {
      _pollTimer?.cancel();
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _retry() async {
    final taskId = _task?.id;
    if (taskId == null || taskId.isEmpty) return;
    setState(() => _error = null);
    try {
      final task = await widget.apiService.retryImportTask(taskId);
      if (!mounted) return;
      setState(() => _task = task);
      if (!task.isFinished) _startPolling();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _selfNameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final busy = _selecting || _uploading;
    return Scaffold(
      appBar: AppBar(title: const Text('导入聊天记录')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            '支持 TXT、CSV、JSON、Markdown、图片和 PDF。文件会先抽取/识别文本，再进入预览，不会直接写入数据库。',
          ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: busy ? null : _selectFile,
            icon: const Icon(Icons.folder_open),
            label: Text(_selecting ? '正在打开...' : '选择聊天记录'),
          ),
          if (_selectedFile != null) ...[
            const SizedBox(height: 8),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.description_outlined),
              title: Text(_selectedFile!.name),
              subtitle: Text(
                _selectedFile!.path,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
          if (_preview != null) ...[
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '导入预览',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      '${_preview!.format.toUpperCase()} · '
                      '${_preview!.encoding} · '
                      '${_preview!.messageCount} 条消息',
                    ),
                    Text(
                      '${_preview!.inputType} · ${_preview!.extractionMethod}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    if (_preview!.warnings.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      ..._preview!.warnings.map(
                        (warning) => Text(
                          warning,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      initialValue: _preview!.senderNames
                              .contains(_selfNameController.text)
                          ? _selfNameController.text
                          : null,
                      decoration: const InputDecoration(
                        labelText: '聊天记录中的本人名称',
                        border: OutlineInputBorder(),
                      ),
                      items: _preview!.senderNames
                          .map(
                            (name) => DropdownMenuItem(
                              value: name,
                              child: Text(name),
                            ),
                          )
                          .toList(),
                      onChanged: busy
                          ? null
                          : (value) => _selfNameController.text = value ?? '',
                    ),
                    const SizedBox(height: 12),
                    ..._preview!.sample.take(5).map(
                          (message) => Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Text(
                              '${message.senderName}: ${message.content}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                    if (_preview!.recognizedText.isNotEmpty) ...[
                      const Divider(height: 24),
                      Text(
                        '识别文本',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      const SizedBox(height: 6),
                      SelectableText(
                        _preview!.recognizedText,
                        maxLines: 8,
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: busy ? null : _upload,
            icon: const Icon(Icons.upload_file),
            label: Text(_uploading ? '正在上传...' : '开始导入'),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
          if (_task != null) ...[
            const SizedBox(height: 20),
            _ImportProgressCard(
              task: _task!,
              onRetry: _task!.canRetry ? _retry : null,
            ),
          ],
        ],
      ),
    );
  }
}

class _ImportProgressCard extends StatelessWidget {
  const _ImportProgressCard({required this.task, this.onRetry});

  final ImportTask task;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final result = task.result;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('导入进度', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            LinearProgressIndicator(value: task.progress),
            const SizedBox(height: 12),
            for (final stage in const [
              ImportStage.parsing,
              ImportStage.storing,
              ImportStage.memory,
              ImportStage.vectors,
            ])
              _StageRow(stage: stage, current: task.stage),
            if (task.message.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(task.message),
            ],
            if (result != null) ...[
              const SizedBox(height: 12),
              Text(
                '导入完成：${result.contacts} 个联系人，'
                '${result.messages} 条消息。',
              ),
            ],
            if (onRetry != null) ...[
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.replay),
                label: const Text('重试失败任务'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _StageRow extends StatelessWidget {
  const _StageRow({required this.stage, required this.current});

  final ImportStage stage;
  final ImportStage current;

  @override
  Widget build(BuildContext context) {
    const ordered = [
      ImportStage.parsing,
      ImportStage.storing,
      ImportStage.memory,
      ImportStage.vectors,
      ImportStage.completed,
    ];
    final stageIndex = ordered.indexOf(stage);
    final currentIndex = ordered.indexOf(current);
    final failed = current == ImportStage.failed;
    final completed = !failed && currentIndex > stageIndex;
    final active = !failed && current == stage;
    final label = switch (stage) {
      ImportStage.parsing => '解析文件',
      ImportStage.storing => '写入数据库',
      ImportStage.memory => '提取记忆',
      ImportStage.vectors => '生成向量',
      _ => '',
    };
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        completed
            ? Icons.check_circle
            : active
                ? Icons.sync
                : Icons.radio_button_unchecked,
        color: completed
            ? Colors.green
            : active
                ? Theme.of(context).colorScheme.primary
                : null,
      ),
      title: Text(label),
    );
  }
}
