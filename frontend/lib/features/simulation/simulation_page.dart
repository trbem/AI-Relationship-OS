import 'package:flutter/material.dart';

import '../../models/person_summary.dart';
import '../../models/simulation_result.dart';
import '../../models/simulation_seed.dart';
import '../../models/simulation_session.dart';
import '../../services/api_service.dart';

class SimulationPage extends StatefulWidget {
  const SimulationPage({super.key, required this.apiService, this.seed});

  final ApiService apiService;
  final SimulationSeed? seed;

  @override
  State<SimulationPage> createState() => _SimulationPageState();
}

class _SimulationPageState extends State<SimulationPage> {
  final _controller = TextEditingController();
  List<PersonSummary> _persons = [];
  List<SimulationSession> _sessions = [];
  SimulationSession? _selected;
  String? _personId;
  bool _loading = true;
  bool _sending = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _applySeed();
    _load();
  }

  @override
  void didUpdateWidget(covariant SimulationPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.seed != widget.seed) _applySeed();
  }

  void _applySeed() {
    final seed = widget.seed;
    if (seed == null) return;
    _personId = seed.personId;
    if ((seed.question ?? '').trim().isNotEmpty) {
      _controller.text = seed.question!.trim();
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final values = await Future.wait([
        widget.apiService.fetchPersons(),
        widget.apiService.fetchSimulationSessions(),
      ]);
      if (!mounted) return;
      final persons = values[0] as List<PersonSummary>;
      final sessions = values[1] as List<SimulationSession>;
      setState(() {
        _persons = persons;
        _sessions = sessions;
        _personId ??= persons.isEmpty ? null : persons.first.id;
      });
      if (_selected == null && sessions.isNotEmpty) {
        await _select(sessions.first.id);
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _select(String id) async {
    try {
      final session = await widget.apiService.fetchSimulationSession(id);
      if (mounted) {
        setState(() {
          _selected = session;
          _personId = session.personId;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    final personId = _personId;
    if (text.isEmpty || personId == null) return;
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      if (_selected == null || _selected!.personId != personId) {
        _selected = await widget.apiService.createSimulationSession(
          personId: personId,
          question: text,
        );
      } else {
        await widget.apiService.continueSimulationSession(
          sessionId: _selected!.id,
          content: text,
        );
        _selected =
            await widget.apiService.fetchSimulationSession(_selected!.id);
      }
      _controller.clear();
      _sessions = await widget.apiService.fetchSimulationSessions();
      if (mounted) setState(() {});
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  void _newSession() {
    setState(() {
      _selected = null;
      _controller.clear();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('关系推演工作区'),
        actions: [
          IconButton(
            onPressed: _selected == null ? null : _openStrategyTools,
            icon: const Icon(Icons.compare_arrows),
            tooltip: '方案比较与简报',
          ),
          IconButton(
            onPressed: _newSession,
            icon: const Icon(Icons.add_comment_outlined),
            tooltip: '新建推演',
          ),
          IconButton(
            onPressed: _load,
            icon: const Icon(Icons.refresh),
            tooltip: '刷新',
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 1050;
                final timeline = _Timeline(
                  session: _selected,
                  persons: _persons,
                  personId: _personId,
                  controller: _controller,
                  sending: _sending,
                  error: _error,
                  onPersonChanged: (value) => setState(() {
                    _personId = value;
                    if (_selected?.personId != value) _selected = null;
                  }),
                  onSend: _send,
                );
                if (!wide) {
                  return Column(
                    children: [
                      SizedBox(
                        height: 112,
                        child: _SessionList(
                          sessions: _sessions,
                          selectedId: _selected?.id,
                          horizontal: true,
                          onSelected: _select,
                        ),
                      ),
                      Expanded(child: timeline),
                    ],
                  );
                }
                return Row(
                  children: [
                    SizedBox(
                      width: 245,
                      child: _SessionList(
                        sessions: _sessions,
                        selectedId: _selected?.id,
                        onSelected: _select,
                      ),
                    ),
                    const VerticalDivider(width: 1),
                    Expanded(child: timeline),
                    const VerticalDivider(width: 1),
                    SizedBox(
                      width: 310,
                      child: _EvidencePanel(session: _selected),
                    ),
                  ],
                );
              },
            ),
    );
  }

  Future<void> _openStrategyTools() async {
    final session = _selected;
    if (session == null) return;
    final label = TextEditingController();
    final wording = TextEditingController();
    final timing = TextEditingController();
    final goal = TextEditingController(text: session.originalQuestion);
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('沟通方案工具'),
        content: SizedBox(
          width: 520,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: label,
                decoration: const InputDecoration(labelText: '方案名称'),
              ),
              TextField(
                controller: wording,
                maxLines: 3,
                decoration: const InputDecoration(labelText: '具体措辞'),
              ),
              TextField(
                controller: timing,
                decoration: const InputDecoration(labelText: '时机'),
              ),
              TextField(
                controller: goal,
                decoration: const InputDecoration(labelText: '目标'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () async {
              final comparison = await widget.apiService
                  .compareCommunicationScenarios(session.id);
              if (!dialogContext.mounted) return;
              await showDialog<void>(
                context: dialogContext,
                builder: (_) => AlertDialog(
                  title: const Text('方案比较'),
                  content: SizedBox(
                    width: 620,
                    child: SingleChildScrollView(
                      child: SelectableText(
                        (comparison['comparison'] as List<dynamic>? ?? [])
                            .map((item) {
                          final value = item as Map<String, dynamic>;
                          final probability =
                              (value['most_likely_probability'] as num?)
                                      ?.toDouble() ??
                                  0;
                          return '${value['label']}\n'
                              '可能反应：${value['most_likely_response']}\n'
                              '概率：${(probability * 100).round()}%\n'
                              '风险：${value['risks']}\n';
                        }).join('\n'),
                      ),
                    ),
                  ),
                ),
              );
            },
            child: const Text('比较已有方案'),
          ),
          TextButton(
            onPressed: () async {
              final report =
                  await widget.apiService.createStrategyReport(session.id);
              if (!dialogContext.mounted) return;
              ScaffoldMessenger.of(dialogContext).showSnackBar(
                SnackBar(content: Text('简报已生成：${report['id']}')),
              );
            },
            child: const Text('生成简报'),
          ),
          FilledButton(
            onPressed: () async {
              if (label.text.trim().isEmpty || wording.text.trim().isEmpty) {
                return;
              }
              await widget.apiService.createCommunicationScenario(
                sessionId: session.id,
                label: label.text.trim(),
                wording: wording.text.trim(),
                timing: timing.text.trim(),
                goal: goal.text.trim(),
              );
              if (dialogContext.mounted) Navigator.pop(dialogContext);
            },
            child: const Text('评估并保存'),
          ),
        ],
      ),
    );
    label.dispose();
    wording.dispose();
    timing.dispose();
    goal.dispose();
  }
}

class _SessionList extends StatelessWidget {
  const _SessionList({
    required this.sessions,
    required this.selectedId,
    required this.onSelected,
    this.horizontal = false,
  });

  final List<SimulationSession> sessions;
  final String? selectedId;
  final ValueChanged<String> onSelected;
  final bool horizontal;

  @override
  Widget build(BuildContext context) {
    if (sessions.isEmpty) {
      return const Center(child: Text('还没有推演会话'));
    }
    return ListView.builder(
      scrollDirection: horizontal ? Axis.horizontal : Axis.vertical,
      padding: const EdgeInsets.all(8),
      itemCount: sessions.length,
      itemBuilder: (context, index) {
        final item = sessions[index];
        return SizedBox(
          width: horizontal ? 220 : null,
          child: Card(
            color: item.id == selectedId
                ? Theme.of(context).colorScheme.secondaryContainer
                : null,
            child: ListTile(
              dense: true,
              leading: const Icon(Icons.forum_outlined),
              title: Text(
                item.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              subtitle: Text(item.status),
              onTap: () => onSelected(item.id),
            ),
          ),
        );
      },
    );
  }
}

class _Timeline extends StatelessWidget {
  const _Timeline({
    required this.session,
    required this.persons,
    required this.personId,
    required this.controller,
    required this.sending,
    required this.error,
    required this.onPersonChanged,
    required this.onSend,
  });

  final SimulationSession? session;
  final List<PersonSummary> persons;
  final String? personId;
  final TextEditingController controller;
  final bool sending;
  final String? error;
  final ValueChanged<String?> onPersonChanged;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: DropdownButtonFormField<String>(
            initialValue:
                persons.any((item) => item.id == personId) ? personId : null,
            decoration: const InputDecoration(
              labelText: '推演对象',
              border: OutlineInputBorder(),
              isDense: true,
            ),
            items: persons
                .map((item) => DropdownMenuItem(
                      value: item.id,
                      child: Text(item.name),
                    ))
                .toList(),
            onChanged: onPersonChanged,
          ),
        ),
        Expanded(
          child: session == null
              ? const Center(
                  child: Text('选择人物并描述一个场景，开始有证据的关系推演。'),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: session!.messages.length,
                  itemBuilder: (context, index) =>
                      _TimelineEntry(message: session!.messages[index]),
                ),
        ),
        if (error != null)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text(
              error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  controller: controller,
                  minLines: 2,
                  maxLines: 5,
                  decoration: InputDecoration(
                    hintText: session == null
                        ? '例如：我提出延期一天，他可能如何回应？'
                        : '继续追问，或改变措辞、时机和条件…',
                    border: const OutlineInputBorder(),
                  ),
                  onSubmitted: (_) => sending ? null : onSend(),
                ),
              ),
              const SizedBox(width: 10),
              FilledButton.icon(
                onPressed: sending ? null : onSend,
                icon: sending
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.auto_awesome),
                label: Text(sending ? '推演中' : '发送'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _TimelineEntry extends StatelessWidget {
  const _TimelineEntry({required this.message});

  final SimulationTimelineMessage message;

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 720),
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: isUser
              ? Theme.of(context).colorScheme.primaryContainer
              : Theme.of(context).colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
        ),
        child: isUser
            ? Text(message.content)
            : _ResultCard(result: message.result, fallback: message.content),
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  const _ResultCard({required this.result, required this.fallback});

  final SimulationResult? result;
  final String fallback;

  @override
  Widget build(BuildContext context) {
    final value = result;
    if (value == null) return Text(fallback);
    final confidence =
        (value.confidenceSummary['score'] as num?)?.toDouble() ?? 0;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('可能反应', style: Theme.of(context).textTheme.titleMedium),
            const Spacer(),
            Chip(label: Text('整体置信度 ${(confidence * 100).round()}%')),
          ],
        ),
        ...value.prediction.map(
          (item) => Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    SizedBox(
                      width: 52,
                      child: Text(
                        '${(item.probability * 100).round()}%',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                    ),
                    Expanded(child: Text(item.text)),
                    Chip(label: Text(item.evidenceStrength)),
                  ],
                ),
                if (item.supportingFactors.isNotEmpty)
                  Text(
                    '支持：${item.supportingFactors.join('；')}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                if (item.counterFactors.isNotEmpty)
                  Text(
                    '反向因素：${item.counterFactors.join('；')}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Text(value.disclaimer, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}

class _EvidencePanel extends StatelessWidget {
  const _EvidencePanel({required this.session});

  final SimulationSession? session;

  @override
  Widget build(BuildContext context) {
    final results = session?.messages
            .where((item) => item.result != null)
            .map((item) => item.result!)
            .toList() ??
        const <SimulationResult>[];
    final evidence =
        results.isEmpty ? const <SimulationEvidence>[] : results.last.evidence;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Text('本轮证据', style: Theme.of(context).textTheme.titleMedium),
        ),
        Expanded(
          child: evidence.isEmpty
              ? const Center(child: Text('选择一轮推演后查看引用'))
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  itemCount: evidence.length,
                  itemBuilder: (context, index) {
                    final item = evidence[index];
                    return Card(
                      child: ListTile(
                        leading: Icon(item.type == 'memory'
                            ? Icons.memory_outlined
                            : Icons.chat_bubble_outline),
                        title: Text(
                          item.excerpt,
                          maxLines: 4,
                          overflow: TextOverflow.ellipsis,
                        ),
                        subtitle: Text(
                          '${item.type} · 相关度 ${(item.relevance * 100).round()}%',
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}
