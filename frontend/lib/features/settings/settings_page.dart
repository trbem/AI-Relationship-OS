import 'dart:io';

import 'package:flutter/material.dart';

import '../../models/app_settings.dart';
import '../../services/api_service.dart';
import '../../services/windows_file_picker.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({
    super.key,
    required this.apiService,
    required this.onLogout,
    this.filePicker = const WindowsFilePicker(),
  });

  final ApiService apiService;
  final Future<void> Function() onLogout;
  final WindowsFilePicker filePicker;

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final _apiKeyController = TextEditingController();
  final _baseUrlController = TextEditingController();
  final _webSearchApiKeyController = TextEditingController();
  final _webSearchBaseUrlController = TextEditingController();
  final _webSearchModelController = TextEditingController();
  final _webSearchTimeoutController = TextEditingController();
  String _provider = 'openai_compatible';
  final _modelController = TextEditingController();
  final _ollamaUrlController = TextEditingController();
  final _timeoutController = TextEditingController();
  final _temperatureController = TextEditingController();
  final _dataDirectoryController = TextEditingController();
  bool _ollamaEnabled = true;
  bool _hasStoredApiKey = false;
  bool _hasStoredWebSearchApiKey = false;
  String _activeModelProvider = 'openai_compatible';
  String _activeModelLabel = '';
  String _fallbackModelLabel = '';
  bool _remoteConfigured = false;
  bool _loading = false;
  bool _saving = false;
  bool _testing = false;
  bool _testingWebSearch = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final settings = await widget.apiService.fetchSettings();
      if (!mounted) return;
      setState(() {
        _provider = settings.provider;
        _baseUrlController.text = settings.baseUrl;
        _modelController.text = settings.model;
        _webSearchBaseUrlController.text = settings.webSearchBaseUrl;
        _webSearchModelController.text = settings.webSearchModel;
        _webSearchTimeoutController.text =
            settings.webSearchTimeoutSeconds.toString();
        _ollamaEnabled = settings.ollamaEnabled;
        _ollamaUrlController.text = settings.ollamaBaseUrl;
        _timeoutController.text = settings.timeoutSeconds.toString();
        _temperatureController.text = settings.temperature.toString();
        _dataDirectoryController.text = settings.dataDirectory;
        _hasStoredApiKey = settings.hasStoredApiKey;
        _hasStoredWebSearchApiKey = settings.hasStoredWebSearchApiKey;
        _activeModelProvider = settings.activeModelProvider;
        _activeModelLabel = settings.activeModelLabel;
        _fallbackModelLabel = settings.fallbackModelLabel;
        _remoteConfigured = settings.remoteConfigured;
      });
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  int? _webSearchTimeout() =>
      int.tryParse(_webSearchTimeoutController.text.trim());

  AppSettings _settingsFromFields({
    required int timeout,
    required double temperature,
    int? webSearchTimeout,
  }) =>
      AppSettings(
        mimoApiKey: _apiKeyController.text.trim(),
        provider: _provider,
        baseUrl: _baseUrlController.text.trim(),
        model: _modelController.text.trim(),
        webSearchApiKey: _webSearchApiKeyController.text.trim(),
        webSearchBaseUrl: _webSearchBaseUrlController.text.trim(),
        webSearchModel: _webSearchModelController.text.trim(),
        webSearchTimeoutSeconds: webSearchTimeout ?? _webSearchTimeout() ?? 120,
        ollamaEnabled: _ollamaEnabled,
        ollamaBaseUrl: _ollamaUrlController.text.trim(),
        timeoutSeconds: timeout,
        temperature: temperature,
        dataDirectory: _dataDirectoryController.text.trim(),
        hasStoredApiKey: _hasStoredApiKey,
        hasStoredWebSearchApiKey: _hasStoredWebSearchApiKey,
      );

  Future<void> _save() async {
    final timeout = int.tryParse(_timeoutController.text.trim());
    if (timeout == null || timeout < 10 || timeout > 600) {
      setState(() => _error = '超时时间请输入 10 到 600 秒。');
      return;
    }
    if (_modelController.text.trim().isEmpty) {
      setState(() => _error = '模型名称不能为空。');
      return;
    }
    if (_provider == 'openai_compatible') {
      if (_baseUrlController.text.trim().isEmpty) {
        setState(() => _error = 'OpenAI 兼容 Base URL 不能为空。');
        return;
      }
      if (!_hasStoredApiKey && _apiKeyController.text.trim().isEmpty) {
        setState(() => _error = 'OpenAI 兼容 API Key 不能为空。');
        return;
      }
    }
    final temperature = double.tryParse(_temperatureController.text.trim());
    if (temperature == null || temperature < 0 || temperature > 2) {
      setState(() => _error = 'Temperature 必须在 0 到 2 之间。');
      return;
    }
    final webSearchTimeout = _webSearchTimeout();
    if (webSearchTimeout == null ||
        webSearchTimeout < 10 ||
        webSearchTimeout > 600) {
      setState(() =>
          _error = 'Web Search timeout must be between 10 and 600 seconds.');
      return;
    }
    final submittedWebSearchKey = _webSearchApiKeyController.text.trim();
    final webSearchConfigured =
        _hasStoredWebSearchApiKey || submittedWebSearchKey.isNotEmpty;
    if (webSearchConfigured && _webSearchModelController.text.trim().isEmpty) {
      setState(() => _error = 'Web Search Model cannot be empty.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final saved = await widget.apiService.updateSettings(
        _settingsFromFields(
          timeout: timeout,
          temperature: temperature,
          webSearchTimeout: webSearchTimeout,
        ),
      );
      if (!mounted) return;
      setState(() {
        _apiKeyController.clear();
        _webSearchApiKeyController.clear();
        _hasStoredApiKey = saved.hasStoredApiKey;
        _hasStoredWebSearchApiKey =
            saved.hasStoredWebSearchApiKey || submittedWebSearchKey.isNotEmpty;
        _activeModelProvider = saved.activeModelProvider;
        _activeModelLabel = saved.activeModelLabel;
        _fallbackModelLabel = saved.fallbackModelLabel;
        _remoteConfigured = saved.remoteConfigured;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            saved.restartRequired ? '设置和数据已保存，请重启应用完成数据目录切换。' : '设置已保存。',
          ),
        ),
      );
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _testConnection() async {
    final timeout = int.tryParse(_timeoutController.text.trim());
    if (timeout == null || timeout < 10 || timeout > 600) {
      setState(() => _error = '超时时间请输入 10 到 600 秒。');
      return;
    }
    if (_modelController.text.trim().isEmpty) {
      setState(() => _error = '模型名称不能为空。');
      return;
    }
    if (_provider == 'openai_compatible' &&
        _baseUrlController.text.trim().isEmpty) {
      setState(() => _error = 'OpenAI 兼容 Base URL 不能为空。');
      return;
    }
    final temperature = double.tryParse(_temperatureController.text.trim());
    if (temperature == null || temperature < 0 || temperature > 2) {
      setState(() => _error = 'Temperature 必须在 0 到 2 之间。');
      return;
    }
    setState(() {
      _testing = true;
      _error = null;
    });
    try {
      final result = await widget.apiService.testAiConnection(
        _settingsFromFields(timeout: timeout, temperature: temperature),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            '连接成功：${result['provider']} · ${result['model']} · ${result['message']}',
          ),
        ),
      );
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _testing = false);
    }
  }

  Future<void> _testWebSearchConnection() async {
    final webSearchTimeout = _webSearchTimeout();
    if (webSearchTimeout == null ||
        webSearchTimeout < 10 ||
        webSearchTimeout > 600) {
      setState(() =>
          _error = 'Web Search timeout must be between 10 and 600 seconds.');
      return;
    }
    if (_webSearchBaseUrlController.text.trim().isEmpty) {
      setState(() => _error = 'Web Search Base URL cannot be empty.');
      return;
    }
    if (_webSearchModelController.text.trim().isEmpty) {
      setState(() => _error = 'Web Search Model cannot be empty.');
      return;
    }
    if (!_hasStoredWebSearchApiKey &&
        _webSearchApiKeyController.text.trim().isEmpty) {
      setState(() => _error = 'Web Search API Key cannot be empty.');
      return;
    }
    setState(() {
      _testingWebSearch = true;
      _error = null;
    });
    try {
      final result = await widget.apiService.testWebSearchConnection(
        _settingsFromFields(
          timeout: int.tryParse(_timeoutController.text.trim()) ?? 120,
          temperature:
              double.tryParse(_temperatureController.text.trim()) ?? 0.2,
          webSearchTimeout: webSearchTimeout,
        ),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Web Search connected: ${result['provider'] ?? 'openai'} · '
            '${result['model'] ?? _webSearchModelController.text.trim()}',
          ),
        ),
      );
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _testingWebSearch = false);
    }
  }

  Future<void> _chooseDataDirectory() async {
    final path = await widget.filePicker.pickDirectory();
    if (path != null && mounted) {
      setState(() => _dataDirectoryController.text = path);
    }
  }

  Future<void> _backup() async {
    final password = await _showBackupPasswordDialog();
    if (password == null || !mounted) return;
    try {
      final path = await widget.filePicker.pickSavePath(
        filename: 'relationship-os-backup.rosbackup',
        filter: '加密备份 (*.rosbackup)|*.rosbackup',
      );
      if (path == null) return;
      await File(path).writeAsBytes(
        await widget.apiService.downloadBackup(password: password),
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('备份已保存到 $path')),
        );
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<String?> _showBackupPasswordDialog() async {
    final passwordController = TextEditingController();
    final confirmationController = TextEditingController();
    String? validationMessage;
    try {
      return await showDialog<String>(
        context: context,
        barrierDismissible: false,
        builder: (dialogContext) => StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: const Text('创建加密备份'),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('密码仅用于本次备份，不会被记录或保存。'),
                const SizedBox(height: 12),
                TextField(
                  controller: passwordController,
                  obscureText: true,
                  autofocus: true,
                  decoration: const InputDecoration(
                    labelText: '备份密码（至少 10 个字符）',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: confirmationController,
                  obscureText: true,
                  decoration: InputDecoration(
                    labelText: '确认密码',
                    border: const OutlineInputBorder(),
                    errorText: validationMessage,
                  ),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialogContext),
                child: const Text('取消'),
              ),
              FilledButton(
                onPressed: () {
                  final password = passwordController.text;
                  final confirmation = confirmationController.text;
                  if (password.length < 10) {
                    setDialogState(() => validationMessage = '密码至少需要 10 个字符。');
                  } else if (password != confirmation) {
                    setDialogState(() => validationMessage = '两次输入的密码不一致。');
                  } else {
                    Navigator.pop(dialogContext, password);
                  }
                },
                child: const Text('继续'),
              ),
            ],
          ),
        ),
      );
    } finally {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        passwordController.dispose();
        confirmationController.dispose();
      });
    }
  }

  Future<void> _exportJson() async {
    try {
      final path = await widget.filePicker.pickSavePath(
        filename: 'relationship-os-export.json',
        filter: 'JSON 数据 (*.json)|*.json',
      );
      if (path == null) return;
      await File(path).writeAsBytes(await widget.apiService.downloadExport());
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('未加密 JSON 数据已导出到 $path')),
        );
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _restore() async {
    final selected = await widget.filePicker.pickBackupFile();
    if (selected == null || !mounted) return;
    final encrypted = selected.name.toLowerCase().endsWith('.rosbackup');
    final passwordController = TextEditingController();
    String? password;
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('恢复备份'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('恢复会替换当前账号的联系人、消息和记忆。'),
            const SizedBox(height: 12),
            if (encrypted)
              TextField(
                controller: passwordController,
                obscureText: true,
                autofocus: true,
                decoration: const InputDecoration(
                  labelText: '备份密码',
                  border: OutlineInputBorder(),
                ),
              )
            else
              Text(
                '警告：这是旧版未加密 ZIP 备份。',
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () {
              if (encrypted && passwordController.text.isEmpty) return;
              password = encrypted ? passwordController.text : null;
              Navigator.pop(context, true);
            },
            child: const Text('恢复'),
          ),
        ],
      ),
    );
    WidgetsBinding.instance.addPostFrameCallback((_) {
      passwordController.dispose();
    });
    if (confirmed != true) return;
    try {
      final file = File(selected.path);
      await widget.apiService.restoreBackup(
        filename: selected.name,
        bytes: await file.readAsBytes(),
        password: password,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('备份恢复完成。')),
        );
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  void dispose() {
    _apiKeyController.dispose();
    _baseUrlController.dispose();
    _webSearchApiKeyController.dispose();
    _webSearchBaseUrlController.dispose();
    _webSearchModelController.dispose();
    _webSearchTimeoutController.dispose();
    _modelController.dispose();
    _ollamaUrlController.dispose();
    _timeoutController.dispose();
    _temperatureController.dispose();
    _dataDirectoryController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('设置'),
        actions: [
          IconButton(
            onPressed: _loading ? null : _load,
            tooltip: '重新加载',
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text('AI 服务', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 12),
                Card(
                  color: const Color(0xFFF7F2FF),
                  child: ListTile(
                    leading: Icon(
                      _activeModelProvider == 'openai_compatible'
                          ? Icons.cloud_outlined
                          : Icons.computer_outlined,
                    ),
                    title: Text(
                      _activeModelLabel.isEmpty
                          ? '当前主模型未明确'
                          : '当前主模型：$_activeModelLabel',
                    ),
                    subtitle: Text(
                      '远程配置：${_remoteConfigured ? '已配置' : '未配置'} · '
                      '失败兜底：${_fallbackModelLabel.isEmpty ? '未启用' : _fallbackModelLabel}',
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _apiKeyController,
                  obscureText: true,
                  decoration: InputDecoration(
                    labelText: 'OpenAI 兼容 API Key',
                    hintText: _hasStoredApiKey ? '已安全保存；留空表示不修改' : '输入 API Key',
                    border: const OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: _provider,
                  decoration: const InputDecoration(
                    labelText: 'Provider',
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: 'openai_compatible',
                      child: Text('OpenAI 兼容'),
                    ),
                    DropdownMenuItem(
                      value: 'ollama',
                      child: Text('Ollama'),
                    ),
                  ],
                  onChanged: (value) {
                    if (value == null) return;
                    setState(() => _provider = value);
                  },
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _baseUrlController,
                  decoration: const InputDecoration(
                    labelText: 'Base URL',
                    hintText: 'https://api.openai.com/v1',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _modelController,
                  decoration: const InputDecoration(
                    labelText: 'Model',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                Text('OpenAI Web Search',
                    style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 8),
                TextField(
                  controller: _webSearchApiKeyController,
                  obscureText: true,
                  decoration: InputDecoration(
                    labelText: 'Web Search API Key',
                    hintText: _hasStoredWebSearchApiKey
                        ? 'Stored securely; leave blank to keep unchanged'
                        : 'Enter API Key',
                    border: const OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _webSearchBaseUrlController,
                  decoration: const InputDecoration(
                    labelText: 'Web Search Base URL',
                    hintText: 'https://api.openai.com/v1',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _webSearchModelController,
                  decoration: const InputDecoration(
                    labelText: 'Web Search Model',
                    hintText:
                        'Required, e.g. a Responses model with web search support',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _webSearchTimeoutController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Web Search Timeout (seconds)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: (_saving || _testingWebSearch)
                      ? null
                      : _testWebSearchConnection,
                  icon: const Icon(Icons.travel_explore),
                  label: Text(_testingWebSearch
                      ? 'Testing Web Search...'
                      : 'Test Web Search'),
                ),
                const SizedBox(height: 12),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('远程服务不可用时使用 Ollama'),
                  value: _ollamaEnabled,
                  onChanged: (value) => setState(() => _ollamaEnabled = value),
                ),
                TextField(
                  controller: _ollamaUrlController,
                  enabled: _ollamaEnabled,
                  decoration: const InputDecoration(
                    labelText: 'Ollama 地址',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _timeoutController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: '请求超时（秒）',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _temperatureController,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Temperature',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _dataDirectoryController,
                  readOnly: true,
                  decoration: const InputDecoration(
                    labelText: '本地数据目录',
                    helperText: '保存后数据会迁移到新目录，重启应用后生效。',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _saving ? null : _chooseDataDirectory,
                  icon: const Icon(Icons.folder_open),
                  label: const Text('选择数据目录'),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: _saving ? null : _save,
                  icon: const Icon(Icons.save_outlined),
                  label: Text(_saving ? '正在保存...' : '保存设置'),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: (_saving || _testing) ? null : _testConnection,
                  icon: const Icon(Icons.wifi_tethering),
                  label: Text(_testing ? '正在测试...' : '测试连接'),
                ),
                const SizedBox(height: 24),
                const Divider(),
                Text('数据管理', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    OutlinedButton.icon(
                      onPressed: _backup,
                      icon: const Icon(Icons.backup_outlined),
                      label: const Text('创建备份'),
                    ),
                    OutlinedButton.icon(
                      onPressed: _restore,
                      icon: const Icon(Icons.restore),
                      label: const Text('恢复备份'),
                    ),
                    OutlinedButton.icon(
                      onPressed: _exportJson,
                      icon: const Icon(Icons.file_download_outlined),
                      label: const Text('导出 JSON（未加密）'),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _saving ? null : widget.onLogout,
                  icon: const Icon(Icons.logout),
                  label: const Text('退出登录'),
                ),
              ],
            ),
    );
  }
}
