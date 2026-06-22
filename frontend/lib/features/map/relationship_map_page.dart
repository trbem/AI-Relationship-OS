import 'package:flutter/material.dart';

import '../../models/relationship_graph.dart';
import '../../models/simulation_seed.dart';
import '../../services/api_service.dart';
import '../persons/person_detail_page.dart';
import 'topology_graph.dart';

class RelationshipMapPage extends StatefulWidget {
  const RelationshipMapPage({
    super.key,
    required this.apiService,
    required this.onOpenSimulation,
  });

  final ApiService apiService;
  final void Function(SimulationSeed seed) onOpenSimulation;

  @override
  State<RelationshipMapPage> createState() => _RelationshipMapPageState();
}

class _RelationshipMapPageState extends State<RelationshipMapPage> {
  RelationshipGraph? _graph;
  GraphNode? _selected;
  int _days = 30;
  bool _showEvents = false;
  bool _showLabels = true;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadGraph();
  }

  Future<void> _loadGraph() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final graph = _showEvents
          ? await widget.apiService.fetchKnowledgeGraph(days: _days)
          : await widget.apiService.fetchRelationshipGraph(days: _days);
      if (!mounted) return;
      setState(() {
        _graph = graph;
        if (_selected != null &&
            !graph.nodes.any((item) => item.id == _selected!.id)) {
          _selected = null;
        }
      });
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('关系拓扑'),
        actions: [
          IconButton(
            onPressed: _loadGraph,
            icon: const Icon(Icons.refresh),
            tooltip: '刷新',
          ),
        ],
      ),
      body: Column(
        children: [
          _Toolbar(
            days: _days,
            showEvents: _showEvents,
            showLabels: _showLabels,
            onDaysChanged: (value) {
              setState(() => _days = value);
              _loadGraph();
            },
            onEventsChanged: (value) {
              setState(() => _showEvents = value);
              _loadGraph();
            },
            onLabelsChanged: (value) => setState(() => _showLabels = value),
          ),
          if (_loading) const LinearProgressIndicator(),
          Expanded(child: _body()),
        ],
      ),
    );
  }

  Widget _body() {
    if (_error != null) {
      return Center(
        child: FilledButton.icon(
          onPressed: _loadGraph,
          icon: const Icon(Icons.refresh),
          label: Text(_error!),
        ),
      );
    }
    final graph = _graph;
    if (graph == null || graph.nodes.isEmpty) {
      return const Center(child: Text('暂无关系数据，请先导入聊天记录。'));
    }
    return LayoutBuilder(
      builder: (context, constraints) {
        final graphView = Stack(
          children: [
            Positioned.fill(
              child: TopologyGraph(
                graph: graph,
                selectedNodeId: _selected?.id,
                onNodeSelected: (node) => setState(() => _selected = node),
                showLabels: _showLabels,
              ),
            ),
            Positioned(
              left: 16,
              bottom: 16,
              child: _Legend(showEvents: _showEvents),
            ),
            Positioned(
              left: 16,
              top: 16,
              child: _InsightCard(insights: graph.insights),
            ),
          ],
        );
        if (constraints.maxWidth < 950) {
          return Stack(
            children: [
              graphView,
              if (_selected != null)
                Positioned(
                  right: 12,
                  top: 12,
                  bottom: 12,
                  width: 320,
                  child: _detail(_selected!),
                ),
            ],
          );
        }
        return Row(
          children: [
            Expanded(child: graphView),
            if (_selected != null) ...[
              const VerticalDivider(width: 1),
              SizedBox(width: 340, child: _detail(_selected!)),
            ],
          ],
        );
      },
    );
  }

  Widget _detail(GraphNode node) {
    return Material(
      elevation: 8,
      color: Theme.of(context).colorScheme.surface,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          ListTile(
            leading: CircleAvatar(
              child: Icon(node.type == 'event'
                  ? Icons.bolt
                  : node.type == 'group'
                      ? Icons.folder_open
                      : Icons.person_outline),
            ),
            title: Text(node.name),
            subtitle: Text('${node.type} · ${node.group}'),
            trailing: IconButton(
              onPressed: () => setState(() => _selected = null),
              icon: const Icon(Icons.close),
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (node.type == 'person') ...[
                  _Metric(
                    label: '关系评分',
                    value: '${node.relationshipScore.toStringAsFixed(0)} / 100',
                  ),
                  _Metric(
                    label: '互动次数',
                    value: node.interaction.toString(),
                  ),
                  _Metric(
                    label: '信任',
                    value: '${(node.trust * 100).round()}%',
                  ),
                  _Metric(
                    label: '近期状态',
                    value: node.recentActive ? '活跃' : '平稳',
                  ),
                  if (node.hint != null) ...[
                    const SizedBox(height: 12),
                    Text('沟通提示', style: Theme.of(context).textTheme.titleSmall),
                    Text(node.hint!),
                  ],
                  if (node.changeReasons.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Text('为什么变化',
                        style: Theme.of(context).textTheme.titleSmall),
                    ...node.changeReasons.map(
                      (item) => ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        leading: const Icon(Icons.insights_outlined, size: 18),
                        title: Text(item),
                      ),
                    ),
                  ],
                  if (node.scoreComponents.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Text('评分构成', style: Theme.of(context).textTheme.titleSmall),
                    ...node.scoreComponents.entries.map(
                      (entry) => Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(entry.key.replaceAll('_', ' ')),
                            ),
                            Text('${(entry.value * 100).round()}'),
                          ],
                        ),
                      ),
                    ),
                  ],
                ] else if (node.type == 'event') ...[
                  _Metric(label: '事件类型', value: node.group),
                  _Metric(
                    label: '影响强度',
                    value: '${node.relationshipScore.round()}%',
                  ),
                  if (node.occurredAt != null)
                    _Metric(label: '发生时间', value: node.occurredAt!),
                  if (node.summary != null) ...[
                    const SizedBox(height: 12),
                    Text('证据摘要', style: Theme.of(context).textTheme.titleSmall),
                    Text(node.summary!),
                  ],
                ] else
                  Text(node.hint ?? '关系分组节点'),
              ],
            ),
          ),
          if (node.type == 'person')
            Padding(
              padding: const EdgeInsets.all(12),
              child: Wrap(
                spacing: 8,
                children: [
                  OutlinedButton.icon(
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => PersonDetailPage(
                          apiService: widget.apiService,
                          personId: node.id,
                          onSimulate: () {
                            Navigator.of(context).pop();
                            widget.onOpenSimulation(
                              SimulationSeed(
                                personId: node.id,
                                personName: node.name,
                              ),
                            );
                          },
                        ),
                      ),
                    ),
                    icon: const Icon(Icons.person_search),
                    label: const Text('人物详情'),
                  ),
                  FilledButton.icon(
                    onPressed: () => widget.onOpenSimulation(
                      SimulationSeed(
                        personId: node.id,
                        personName: node.name,
                      ),
                    ),
                    icon: const Icon(Icons.psychology_outlined),
                    label: const Text('开始推演'),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _Toolbar extends StatelessWidget {
  const _Toolbar({
    required this.days,
    required this.showEvents,
    required this.showLabels,
    required this.onDaysChanged,
    required this.onEventsChanged,
    required this.onLabelsChanged,
  });

  final int days;
  final bool showEvents;
  final bool showLabels;
  final ValueChanged<int> onDaysChanged;
  final ValueChanged<bool> onEventsChanged;
  final ValueChanged<bool> onLabelsChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Row(
        children: [
          SegmentedButton<int>(
            segments: const [
              ButtonSegment(value: 7, label: Text('7 天')),
              ButtonSegment(value: 30, label: Text('30 天')),
              ButtonSegment(value: 90, label: Text('90 天')),
            ],
            selected: {days},
            onSelectionChanged: (value) => onDaysChanged(value.first),
          ),
          const Spacer(),
          FilterChip(
            selected: showEvents,
            onSelected: onEventsChanged,
            avatar: const Icon(Icons.bolt, size: 18),
            label: const Text('关系事件'),
          ),
          const SizedBox(width: 8),
          FilterChip(
            selected: showLabels,
            onSelected: onLabelsChanged,
            avatar: const Icon(Icons.label_outline, size: 18),
            label: const Text('标签'),
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

class _InsightCard extends StatelessWidget {
  const _InsightCard({required this.insights});
  final GraphInsights insights;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Wrap(
          spacing: 12,
          children: [
            Text('活跃 ${insights.activeCount}'),
            if (insights.strongestTie != null)
              Text('最强联系 ${insights.strongestTie}'),
            Text('压力关系 ${insights.stressCount}'),
          ],
        ),
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend({required this.showEvents});
  final bool showEvents;

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Wrap(
          spacing: 12,
          runSpacing: 8,
          children: [
            _item(const Color(0xFF1F2937), '我'),
            _item(const Color(0xFF7B2D8E), '分组'),
            _item(const Color(0xFF3B82F6), '联系人'),
            if (showEvents) _item(const Color(0xFFE9724C), '关系事件'),
          ],
        ),
      ),
    );
  }

  Widget _item(Color color, String label) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 5),
          Text(label),
        ],
      );
}
