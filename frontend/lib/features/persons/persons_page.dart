import 'package:flutter/material.dart';

import '../../models/person_summary.dart';
import '../../models/simulation_seed.dart';
import '../../services/api_service.dart';
import 'person_detail_page.dart';

class PersonsPage extends StatefulWidget {
  const PersonsPage({
    super.key,
    required this.apiService,
    required this.onOpenSimulation,
  });

  final ApiService apiService;
  final void Function(SimulationSeed seed) onOpenSimulation;

  @override
  State<PersonsPage> createState() => _PersonsPageState();
}

class _PersonsPageState extends State<PersonsPage> {
  List<PersonSummary> _persons = [];
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadPersons();
  }

  Future<void> _loadPersons() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final persons = await widget.apiService.fetchPersons();
      if (mounted) setState(() => _persons = persons);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _mergePerson(PersonSummary source) async {
    final targets = _persons.where((person) => person.id != source.id).toList();
    if (targets.isEmpty) return;
    String targetId = targets.first.id;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text('合并联系人“${source.name}”'),
          content: DropdownButtonFormField<String>(
            initialValue: targetId,
            decoration: const InputDecoration(
              labelText: '合并到',
              border: OutlineInputBorder(),
            ),
            items: targets
                .map(
                  (person) => DropdownMenuItem(
                    value: person.id,
                    child: Text(person.name),
                  ),
                )
                .toList(),
            onChanged: (value) {
              if (value != null) {
                setDialogState(() => targetId = value);
              }
            },
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('确认合并'),
            ),
          ],
        ),
      ),
    );
    if (confirmed != true) return;
    try {
      await widget.apiService.mergePersons(
        sourcePersonId: source.id,
        targetPersonId: targetId,
      );
      await _loadPersons();
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('人物'),
        actions: [
          IconButton(
            onPressed: _loadPersons,
            icon: const Icon(Icons.refresh),
            tooltip: '刷新',
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _ErrorView(message: _error!, onRetry: _loadPersons)
              : _persons.isEmpty
                  ? const Center(child: Text('暂无人物，请先导入聊天记录。'))
                  : RefreshIndicator(
                      onRefresh: _loadPersons,
                      child: ListView.builder(
                        padding: const EdgeInsets.all(8),
                        itemCount: _persons.length,
                        itemBuilder: (context, index) {
                          final person = _persons[index];
                          return Card(
                            child: ListTile(
                              leading: CircleAvatar(
                                child: Text(
                                  person.name.isEmpty ? '?' : person.name[0],
                                ),
                              ),
                              title: Text(person.name),
                              subtitle: Text(
                                '${person.messageCount} 条消息 · '
                                '${person.memoryCount} 条记忆',
                              ),
                              trailing: PopupMenuButton<String>(
                                onSelected: (value) {
                                  if (value == 'merge') _mergePerson(person);
                                },
                                itemBuilder: (context) => [
                                  if (_persons.length > 1)
                                    const PopupMenuItem(
                                      value: 'merge',
                                      child: Text('合并联系人'),
                                    ),
                                ],
                              ),
                              onTap: () => Navigator.of(context).push(
                                MaterialPageRoute(
                                  builder: (_) => PersonDetailPage(
                                    apiService: widget.apiService,
                                    personId: person.id,
                                    onSimulate: () {
                                      Navigator.of(context).pop();
                                      widget.onOpenSimulation(
                                        SimulationSeed(
                                          personId: person.id,
                                          personName: person.name,
                                        ),
                                      );
                                    },
                                  ),
                                ),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(message,
                style: TextStyle(color: Theme.of(context).colorScheme.error)),
            const SizedBox(height: 12),
            FilledButton(onPressed: onRetry, child: const Text('重试')),
          ],
        ),
      ),
    );
  }
}
