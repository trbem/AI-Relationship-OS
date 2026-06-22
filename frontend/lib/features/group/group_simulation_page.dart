import 'package:flutter/material.dart';

import '../../models/person_summary.dart';
import '../../services/api_service.dart';

class GroupSimulationPage extends StatefulWidget {
  const GroupSimulationPage({super.key, required this.apiService});
  final ApiService apiService;

  @override
  State<GroupSimulationPage> createState() => _GroupSimulationPageState();
}

class _GroupSimulationPageState extends State<GroupSimulationPage> {
  final _goal = TextEditingController();
  List<PersonSummary> _persons = [];
  final Set<String> _selected = {};
  String? _primary;
  Map<String, dynamic>? _result;
  bool _running = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final persons = await widget.apiService.fetchPersons();
      if (!mounted) return;
      setState(() {
        _persons = persons;
        if (persons.isNotEmpty) {
          _primary ??= persons.first.id;
          _selected.add(persons.first.id);
        }
      });
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _run() async {
    if (_primary == null || _selected.isEmpty || _goal.text.trim().isEmpty) {
      return;
    }
    setState(() {
      _running = true;
      _error = null;
    });
    try {
      final title = _goal.text.trim();
      final created = await widget.apiService.createGroupSimulation(
        primaryPersonId: _primary!,
        participantIds: _selected.toList(),
        title: title.length > 60 ? title.substring(0, 60) : title,
        goal: title,
      );
      final result =
          await widget.apiService.runGroupSimulation(created['id'].toString());
      if (mounted) setState(() => _result = result);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  @override
  void dispose() {
    _goal.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final rounds = _result?['rounds'] as List<dynamic>? ?? const [];
    return Scaffold(
      appBar: AppBar(title: const Text('小组影响推演')),
      body: Row(
        children: [
          SizedBox(
            width: 330,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                DropdownButtonFormField<String>(
                  initialValue: _primary,
                  decoration: const InputDecoration(
                    labelText: '主要对象',
                    border: OutlineInputBorder(),
                  ),
                  items: _persons
                      .map((item) => DropdownMenuItem(
                            value: item.id,
                            child: Text(item.name),
                          ))
                      .toList(),
                  onChanged: (value) => setState(() {
                    _primary = value;
                    if (value != null) _selected.add(value);
                  }),
                ),
                const SizedBox(height: 16),
                Text('参与人物（最多 8 人）',
                    style: Theme.of(context).textTheme.titleSmall),
                ..._persons.map(
                  (person) => CheckboxListTile(
                    value: _selected.contains(person.id),
                    title: Text(person.name),
                    onChanged: (checked) => setState(() {
                      if (checked == true && _selected.length < 8) {
                        _selected.add(person.id);
                      } else if (person.id != _primary) {
                        _selected.remove(person.id);
                      }
                    }),
                  ),
                ),
                TextField(
                  controller: _goal,
                  maxLines: 4,
                  decoration: const InputDecoration(
                    labelText: '场景目标',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: _running ? null : _run,
                  icon: const Icon(Icons.play_arrow),
                  label: Text(_running ? '运行中' : '运行 3 轮推演'),
                ),
                if (_error != null)
                  Text(
                    _error!,
                    style:
                        TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
              ],
            ),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: rounds.isEmpty
                ? const Center(
                    child: Text('选择家庭或团队成员，观察有限轮次中的影响变化。'),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: rounds.length,
                    itemBuilder: (context, index) {
                      final round = rounds[index] as Map<String, dynamic>;
                      final people = round['people'] as List<dynamic>? ?? [];
                      return Card(
                        child: ExpansionTile(
                          initiallyExpanded: index == 0,
                          title: Text(
                            '第 ${round['round']} 轮 · 共识 ${round['consensus']}',
                          ),
                          subtitle: const Text('模拟状态不会写回真实关系'),
                          children: people.map((item) {
                            final person = item as Map<String, dynamic>;
                            final confidence =
                                (person['confidence'] as num?)?.toDouble() ?? 0;
                            return ListTile(
                              leading: Icon(person['high_uncertainty'] == true
                                  ? Icons.help_outline
                                  : Icons.person_outline),
                              title: Text(person['name'].toString()),
                              subtitle: Text(
                                '状态 ${person['stance']} · '
                                '置信度 ${(confidence * 100).round()}%',
                              ),
                            );
                          }).toList(),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
