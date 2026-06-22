import 'package:flutter/material.dart';

import '../../models/system_status.dart';
import '../../services/api_service.dart';

class StartupPage extends StatefulWidget {
  const StartupPage({
    super.key,
    required this.apiService,
    required this.onReady,
  });

  final ApiService apiService;
  final Future<void> Function() onReady;

  @override
  State<StartupPage> createState() => _StartupPageState();
}

class _StartupPageState extends State<StartupPage> {
  SystemStatus? _status;
  String? _error;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _check();
  }

  Future<void> _check() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final status = await widget.apiService.fetchSystemStatus();
      if (!mounted) return;
      setState(() => _status = status);
      if (status.canContinue) await widget.onReady();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = _status;
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Card(
            margin: const EdgeInsets.all(24),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Icon(Icons.hub, size: 52),
                  const SizedBox(height: 12),
                  Text(
                    '正在启动 Relationship OS',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 24),
                  _StatusRow(
                    label: '本地服务',
                    ready: status?.backendReady,
                  ),
                  _StatusRow(
                    label: '本地数据库',
                    ready: status?.databaseReady,
                  ),
                  _StatusRow(
                    label: 'AI 服务',
                    ready: status?.aiReady,
                    optional: true,
                  ),
                  if (status != null)
                    Text(
                      '版本 ${status.version}',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  if (_loading) ...[
                    const SizedBox(height: 16),
                    const LinearProgressIndicator(),
                  ],
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Text(
                      _error!,
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ],
                  if (!_loading && (status?.canContinue != true)) ...[
                    const SizedBox(height: 16),
                    FilledButton.icon(
                      onPressed: _check,
                      icon: const Icon(Icons.refresh),
                      label: const Text('重新检查'),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _StatusRow extends StatelessWidget {
  const _StatusRow({
    required this.label,
    required this.ready,
    this.optional = false,
  });

  final String label;
  final bool? ready;
  final bool optional;

  @override
  Widget build(BuildContext context) {
    final icon = ready == null
        ? const CircularProgressIndicator(strokeWidth: 2)
        : Icon(
            ready! ? Icons.check_circle : Icons.error_outline,
            color: ready! ? Colors.green : Colors.orange,
          );
    return ListTile(
      leading: SizedBox(width: 24, height: 24, child: Center(child: icon)),
      title: Text(label),
      trailing: Text(
        ready == null
            ? '检查中'
            : ready!
                ? '正常'
                : optional
                    ? '未配置'
                    : '异常',
      ),
    );
  }
}
