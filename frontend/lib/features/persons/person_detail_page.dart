import 'package:flutter/material.dart';

import '../../models/chat_message.dart';
import '../../models/person_detail.dart';
import '../../services/api_service.dart';

class PersonDetailPage extends StatefulWidget {
  const PersonDetailPage({
    super.key,
    required this.apiService,
    required this.personId,
    required this.onSimulate,
  });

  final ApiService apiService;
  final String personId;
  final VoidCallback onSimulate;

  @override
  State<PersonDetailPage> createState() => _PersonDetailPageState();
}

class _PersonDetailPageState extends State<PersonDetailPage> {
  PersonDetail? _detail;
  Map<String, dynamic>? _persona;
  List<ChatMessage> _messages = [];
  bool _loading = false;
  bool _generating = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDetail();
  }

  Future<void> _loadDetail() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final detail = await widget.apiService.fetchPersonDetail(widget.personId);
      final messages = await widget.apiService.fetchMessages(widget.personId);
      if (mounted) {
        setState(() {
          _detail = detail;
          _messages = messages;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _deleteMessage(ChatMessage message) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('删除消息'),
        content: Text('确认删除“${message.content}”？相关向量记录也会一并删除。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('删除'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await widget.apiService.deleteMessage(message.id);
    await _loadDetail();
  }

  Future<void> _generatePersona() async {
    setState(() => _generating = true);
    try {
      final persona = await widget.apiService.generatePersona(widget.personId);
      if (mounted) setState(() => _persona = persona);
      await _loadDetail();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('生成画像失败：$error')),
        );
      }
    } finally {
      if (mounted) setState(() => _generating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final detail = _detail;
    return Scaffold(
      appBar: AppBar(
        title: Text(detail?.name ?? '人物详情'),
        actions: [
          IconButton(onPressed: _loadDetail, icon: const Icon(Icons.refresh)),
        ],
      ),
      body: _loading && detail == null
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : detail == null
                  ? const Center(child: Text('未找到人物'))
                  : ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        FilledButton.icon(
                          onPressed: _generating ? null : _generatePersona,
                          icon: const Icon(Icons.auto_awesome),
                          label:
                              Text(_generating ? 'MiMo 分析中...' : '生成/更新人物画像'),
                        ),
                        const SizedBox(height: 8),
                        OutlinedButton.icon(
                          onPressed: widget.onSimulate,
                          icon: const Icon(Icons.psychology),
                          label: const Text('基于此人物进行关系推演'),
                        ),
                        if (_persona != null) ...[
                          const SizedBox(height: 16),
                          _PersonaCard(persona: _persona!),
                        ],
                        const SizedBox(height: 16),
                        Text('长期记忆',
                            style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 8),
                        if (detail.memories.isEmpty)
                          const Text('暂无记忆')
                        else
                          ...detail.memories.map(
                            (memory) => Card(
                              child: ListTile(
                                title: Text(memory.event),
                                subtitle: Text(
                                  '情绪：${memory.emotion} · '
                                  '重要性 ${(memory.importance * 100).toStringAsFixed(0)}%',
                                ),
                              ),
                            ),
                          ),
                        const SizedBox(height: 16),
                        Text('消息预览',
                            style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 8),
                        ..._messages.take(20).map(
                              (message) => Card(
                                child: ListTile(
                                  title: Text(message.content),
                                  subtitle: Text(message.senderName),
                                  trailing: IconButton(
                                    tooltip: '删除消息',
                                    onPressed: () => _deleteMessage(message),
                                    icon: const Icon(Icons.delete_outline),
                                  ),
                                ),
                              ),
                            ),
                        Text(
                          '共 ${_messages.length} 条消息，'
                          '${detail.vectorRefs.length} 条向量记录。',
                        ),
                      ],
                    ),
    );
  }
}

class _PersonaCard extends StatelessWidget {
  const _PersonaCard({required this.persona});

  final Map<String, dynamic> persona;

  @override
  Widget build(BuildContext context) {
    String listText(String key) {
      final value = persona[key];
      return value is List ? value.join('、') : '';
    }

    return Card(
      color: Theme.of(context).colorScheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('MiMo 人物画像', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('特征：${listText('traits')}'),
            Text('沟通方式：${listText('communication')}'),
            Text('兴趣：${listText('interests')}'),
            Text('情绪模式：${listText('emotion_patterns')}'),
            Text('关键词：${listText('keywords')}'),
            const SizedBox(height: 8),
            Text(persona['evidence_note']?.toString() ?? ''),
          ],
        ),
      ),
    );
  }
}
