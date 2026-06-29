import 'dart:async';

import 'package:flutter/material.dart';

import '../../models/relationship_graph.dart';
import '../../services/api_service.dart';
import '../map/topology_graph.dart';

class PersonaWorldsPage extends StatefulWidget {
  const PersonaWorldsPage({super.key, required this.apiService});

  final ApiService apiService;

  @override
  State<PersonaWorldsPage> createState() => _PersonaWorldsPageState();
}

class _PersonaWorldsPageState extends State<PersonaWorldsPage> {
  List<Map<String, dynamic>> _worlds = [];
  Map<String, dynamic>? _world;
  RelationshipGraph? _graph;
  GraphNode? _selectedNode;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadWorlds();
  }

  Future<void> _loadWorlds({String? selectId}) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final worlds = await widget.apiService.fetchPersonaWorlds();
      final id = selectId ??
          _world?['id']?.toString() ??
          (worlds.isEmpty ? null : worlds.first['id'].toString());
      if (!mounted) return;
      setState(() => _worlds = worlds);
      if (id != null) {
        await _selectWorld(id);
      } else {
        setState(() {
          _world = null;
          _graph = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _selectWorld(String id) async {
    final results = await Future.wait([
      widget.apiService.fetchPersonaWorld(id),
      widget.apiService.fetchWorldGraph(id),
    ]);
    if (!mounted) return;
    setState(() {
      _world = results[0] as Map<String, dynamic>;
      _graph = results[1] as RelationshipGraph;
      _selectedNode = null;
    });
  }

  List<Map<String, dynamic>> get _personas =>
      (_world?['personas'] as List<dynamic>? ?? const [])
          .cast<Map<String, dynamic>>();

  Map<String, dynamic>? get _selectedPersona {
    final id = _selectedNode?.id;
    if (id == null) return null;
    for (final item in _personas) {
      if (item['id'] == id) return item;
    }
    return null;
  }

  Future<void> _createWorld() async {
    final result = await _worldDialog();
    if (result == null) return;
    final created = await widget.apiService.createPersonaWorld(
      name: result.$1,
      theme: result.$2,
      background: result.$3,
    );
    await _loadWorlds(selectId: created['id'].toString());
  }

  Future<(String, String?, String?)?> _worldDialog() async {
    final name = TextEditingController();
    final theme = TextEditingController();
    final background = TextEditingController();
    return showDialog<(String, String?, String?)>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('新建角色世界'),
        content: SizedBox(
          width: 440,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: name,
                autofocus: true,
                decoration: const InputDecoration(labelText: '世界名称 *'),
              ),
              TextField(
                controller: theme,
                decoration: const InputDecoration(labelText: '主题'),
              ),
              TextField(
                controller: background,
                maxLines: 3,
                decoration: const InputDecoration(labelText: '世界背景'),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () {
              if (name.text.trim().isEmpty) return;
              Navigator.pop(
                context,
                (
                  name.text.trim(),
                  theme.text.trim().isEmpty ? null : theme.text.trim(),
                  background.text.trim().isEmpty
                      ? null
                      : background.text.trim(),
                ),
              );
            },
            child: const Text('创建'),
          ),
        ],
      ),
    );
  }

  Future<void> _editPersona([Map<String, dynamic>? persona]) async {
    final worldId = _world?['id']?.toString();
    if (worldId == null) return;
    final name = TextEditingController(text: persona?['name']?.toString());
    final summary =
        TextEditingController(text: persona?['summary']?.toString());
    final faction =
        TextEditingController(text: persona?['faction']?.toString());
    final traits = TextEditingController(
      text: (persona?['traits'] as List<dynamic>? ?? []).join('、'),
    );
    final motivations = TextEditingController(
      text: (persona?['motivations'] as List<dynamic>? ?? []).join('、'),
    );
    final background =
        TextEditingController(text: persona?['background']?.toString());
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(persona == null ? '添加自定义人物' : '编辑人物设定'),
        content: SizedBox(
          width: 520,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: name,
                  decoration: const InputDecoration(labelText: '姓名 *'),
                ),
                TextField(
                  controller: summary,
                  maxLines: 3,
                  decoration: const InputDecoration(labelText: '简介 *'),
                ),
                TextField(
                  controller: faction,
                  decoration: const InputDecoration(labelText: '阵营'),
                ),
                TextField(
                  controller: traits,
                  decoration: const InputDecoration(labelText: '性格（用顿号分隔）'),
                ),
                TextField(
                  controller: motivations,
                  decoration: const InputDecoration(labelText: '目标/动机（用顿号分隔）'),
                ),
                TextField(
                  controller: background,
                  maxLines: 3,
                  decoration: const InputDecoration(labelText: '背景经历'),
                ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () {
              if (name.text.trim().isEmpty || summary.text.trim().isEmpty) {
                return;
              }
              Navigator.pop(context, true);
            },
            child: const Text('保存'),
          ),
        ],
      ),
    );
    if (accepted != true) return;
    final split = (String value) => value
        .split(RegExp(r'[、,，]'))
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .toList();
    if (persona == null) {
      await widget.apiService.createWorldPersona(
        worldId: worldId,
        name: name.text.trim(),
        summary: summary.text.trim(),
        faction: faction.text.trim().isEmpty ? null : faction.text.trim(),
        traits: split(traits.text),
        motivations: split(motivations.text),
        background:
            background.text.trim().isEmpty ? null : background.text.trim(),
      );
    } else {
      await widget.apiService.updateWorldPersona(
        worldId: worldId,
        personaId: persona['id'].toString(),
        name: name.text.trim(),
        summary: summary.text.trim(),
        faction: faction.text.trim().isEmpty ? null : faction.text.trim(),
        traits: split(traits.text),
        motivations: split(motivations.text),
        background:
            background.text.trim().isEmpty ? null : background.text.trim(),
      );
    }
    await _selectWorld(worldId);
  }

  Future<void> _addRelationship() async {
    final worldId = _world?['id']?.toString();
    if (worldId == null || _personas.length < 2) return;
    String source = _personas.first['id'].toString();
    String target = _personas[1]['id'].toString();
    final type = TextEditingController(text: '合作');
    double strength = 0.6;
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('连接人物'),
          content: SizedBox(
            width: 450,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  initialValue: source,
                  decoration: const InputDecoration(labelText: '起点人物'),
                  items: _personas
                      .map((item) => DropdownMenuItem(
                            value: item['id'].toString(),
                            child: Text(item['name'].toString()),
                          ))
                      .toList(),
                  onChanged: (value) => source = value ?? source,
                ),
                DropdownButtonFormField<String>(
                  initialValue: target,
                  decoration: const InputDecoration(labelText: '终点人物'),
                  items: _personas
                      .map((item) => DropdownMenuItem(
                            value: item['id'].toString(),
                            child: Text(item['name'].toString()),
                          ))
                      .toList(),
                  onChanged: (value) => target = value ?? target,
                ),
                TextField(
                  controller: type,
                  decoration:
                      const InputDecoration(labelText: '关系类型（盟友、敌对、影响等）'),
                ),
                Row(
                  children: [
                    const Text('强度'),
                    Expanded(
                      child: Slider(
                        value: strength,
                        onChanged: (value) =>
                            setDialogState(() => strength = value),
                      ),
                    ),
                    Text('${(strength * 100).round()}%'),
                  ],
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed:
                  source == target ? null : () => Navigator.pop(context, true),
              child: const Text('连接'),
            ),
          ],
        ),
      ),
    );
    if (accepted != true) return;
    await widget.apiService.createWorldRelationship(
      worldId: worldId,
      sourcePersonaId: source,
      targetPersonaId: target,
      relationshipType: type.text.trim(),
      strength: strength,
    );
    await _selectWorld(worldId);
  }

  Future<void> _importCatalog() async {
    final worldId = _world?['id']?.toString();
    if (worldId == null) return;
    final catalog = await widget.apiService.fetchPersonaCatalog();
    if (!mounted || catalog.isEmpty) return;
    String templateId = catalog.first['id'].toString();
    double limit = 20;
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('精选人物图库'),
          content: SizedBox(
            width: 520,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  initialValue: templateId,
                  decoration: const InputDecoration(labelText: '世界版本'),
                  items: catalog
                      .map((item) => DropdownMenuItem(
                            value: item['id'].toString(),
                            child: Text(
                              '${item['name']} · ${item['persona_count']} 人',
                            ),
                          ))
                      .toList(),
                  onChanged: (value) =>
                      setDialogState(() => templateId = value ?? templateId),
                ),
                const SizedBox(height: 12),
                const Text('小说版与历史版是两个独立模板，不会混合实体或关系。'),
                Row(
                  children: [
                    const Text('导入数量'),
                    Expanded(
                      child: Slider(
                        value: limit,
                        min: 1,
                        max: 40,
                        divisions: 39,
                        label: limit.round().toString(),
                        onChanged: (value) =>
                            setDialogState(() => limit = value),
                      ),
                    ),
                    Text('${limit.round()} 人'),
                  ],
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('取消'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('导入'),
            ),
          ],
        ),
      ),
    );
    if (accepted != true) return;
    await widget.apiService.importPersonaCatalog(
      worldId: worldId,
      templateId: templateId,
      limit: limit.round(),
    );
    await _selectWorld(worldId);
  }

  Future<void> _searchOnlineV08() async {
    final currentWorldId = _world?['id']?.toString();
    var provider = 'free_web';
    try {
      final settings = await widget.apiService.fetchSettings();
      provider = settings.worldImportSearchProvider;
    } catch (_) {
      provider = 'free_web';
    }
    final query = TextEditingController();
    final newWorldName = TextEditingController(
      text: _world?['name']?.toString() ?? '',
    );
    double limit = 20;
    var language = 'zh';
    var importMode = currentWorldId == null ? 'create' : 'append';
    final request = await showDialog<
        ({
          String query,
          int limit,
          String mode,
          String name,
          String provider,
          String language,
        })>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('AI Web Import'),
          content: SizedBox(
            width: 520,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: query,
                  autofocus: true,
                  decoration: const InputDecoration(
                    labelText: 'Topic',
                    hintText: 'e.g. Greek mythology, Three Kingdoms',
                  ),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: language,
                  decoration: const InputDecoration(
                    labelText: 'Language',
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: 'zh',
                      child: Text('Chinese / 中文'),
                    ),
                    DropdownMenuItem(
                      value: 'auto',
                      child: Text('Auto detect'),
                    ),
                    DropdownMenuItem(
                      value: 'en',
                      child: Text('English'),
                    ),
                  ],
                  onChanged: (value) =>
                      setDialogState(() => language = value ?? 'zh'),
                ),
                const SizedBox(height: 8),
                Text(
                  language == 'zh'
                      ? 'Chinese mode translates and normalizes extracted profiles into Chinese.'
                      : language == 'en'
                          ? 'English mode keeps extracted profiles in English.'
                          : 'Auto mode chooses Chinese for Chinese queries and English otherwise.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: provider,
                  decoration: const InputDecoration(
                    labelText: 'Search provider',
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: 'free_web',
                      child: Text('Free web search + current AI model'),
                    ),
                    DropdownMenuItem(
                      value: 'openai_web_search',
                      child: Text('OpenAI native Web Search'),
                    ),
                  ],
                  onChanged: (value) =>
                      setDialogState(() => provider = value ?? 'free_web'),
                ),
                const SizedBox(height: 8),
                Text(
                  provider == 'free_web'
                      ? 'Searches public web pages first, then asks your current AI model to extract characters.'
                      : 'Uses OpenAI Responses API native web_search configuration.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    const Text('Limit'),
                    Expanded(
                      child: Slider(
                        value: limit,
                        min: 1,
                        max: 50,
                        divisions: 49,
                        label: limit.round().toString(),
                        onChanged: (value) =>
                            setDialogState(() => limit = value),
                      ),
                    ),
                    Text('${limit.round()}'),
                  ],
                ),
                RadioGroup<String>(
                  groupValue: importMode,
                  onChanged: (value) =>
                      setDialogState(() => importMode = value ?? importMode),
                  child: Column(
                    children: [
                      RadioListTile<String>(
                        value: 'append',
                        enabled: currentWorldId != null,
                        title: const Text('Append to current world'),
                      ),
                      const RadioListTile<String>(
                        value: 'create',
                        title: Text('Create a new world'),
                      ),
                    ],
                  ),
                ),
                if (importMode == 'create')
                  TextField(
                    controller: newWorldName,
                    decoration: const InputDecoration(
                      labelText: 'New world name',
                    ),
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                final trimmedQuery = query.text.trim();
                final trimmedName = newWorldName.text.trim();
                if (trimmedQuery.isEmpty) return;
                if (importMode == 'create' && trimmedName.isEmpty) return;
                Navigator.pop(
                  context,
                  (
                    query: trimmedQuery,
                    limit: limit.round().clamp(1, 50).toInt(),
                    mode: importMode,
                    name: trimmedName.isEmpty ? trimmedQuery : trimmedName,
                    provider: provider,
                    language: language,
                  ),
                );
              },
              child: const Text('Search'),
            ),
          ],
        ),
      ),
    );
    query.dispose();
    newWorldName.dispose();
    if (request == null) return;

    setState(() => _loading = true);
    try {
      var task = await widget.apiService.searchWorldImport(
        query: request.query,
        limit: request.limit,
        provider: request.provider,
        language: request.language,
      );
      task = await _pollWorldImportTask(task);
      task = await _resolveWorldImportDisambiguation(task);
      if (!mounted) return;
      if (task.isEmpty) return;

      var result = task['result'] as Map<String, dynamic>? ?? {};
      var candidates = (result['candidates'] as List<dynamic>? ?? [])
          .cast<Map<String, dynamic>>();
      var sourceFailures = (result['source_failures'] as List<dynamic>? ?? [])
          .cast<Map<String, dynamic>>();
      var errors = (result['errors'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .toList();
      final taskStatus = task['status']?.toString() ?? '';
      final canGenerateFallback =
          {'failed', 'preview', 'partial'}.contains(taskStatus);
      if (candidates.isEmpty && canGenerateFallback) {
        final useFallback = await _confirmGeneratedFallback(task);
        if (useFallback == true) {
          task = await widget.apiService.generateWorldImportFallback(
            taskId: task['id'].toString(),
            mode: 'generate_missing',
            targetCount: request.limit,
          );
          result = task['result'] as Map<String, dynamic>? ?? {};
          candidates = (result['candidates'] as List<dynamic>? ?? [])
              .cast<Map<String, dynamic>>();
          sourceFailures = (result['source_failures'] as List<dynamic>? ?? [])
              .cast<Map<String, dynamic>>();
          errors = (result['errors'] as List<dynamic>? ?? [])
              .map((item) => item.toString())
              .toList();
        }
      }
      final fallbackMode = result['fallback_mode']?.toString() ?? 'none';
      final generatedNotice = result['generated_notice']?.toString();
      final relationships = (result['relationships'] as List<dynamic>? ?? [])
          .cast<Map<String, dynamic>>();
      final selected = candidates.map((item) => item['id'].toString()).toSet();
      final selectedRelationships =
          List<int>.generate(relationships.length, (index) => index).toSet();

      final accepted = await showDialog<bool>(
        context: context,
        builder: (context) => StatefulBuilder(
          builder: (context, setDialogState) => AlertDialog(
            title: Text('Import preview · ${task['status']}'),
            content: SizedBox(
              width: 700,
              height: 500,
              child: candidates.isEmpty
                  ? _worldImportEmptyPreview(task, errors, sourceFailures)
                  : ListView(
                      children: [
                        if (fallbackMode == 'model_generated')
                          ListTile(
                            leading: const Icon(Icons.auto_awesome),
                            title: const Text('Model-generated fallback'),
                            subtitle: Text(
                              generatedNotice ??
                                  'Online sources were unavailable; candidates are not source-verified.',
                            ),
                          ),
                        if (errors.isNotEmpty)
                          ListTile(
                            leading: const Icon(Icons.error_outline),
                            title: const Text('Warnings / errors'),
                            subtitle: Text(errors.join('\n')),
                          ),
                        if (sourceFailures.isNotEmpty) ...[
                          const Divider(height: 12),
                          const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 16),
                            child: Text('Source failures'),
                          ),
                          ...sourceFailures.map(_sourceFailureTile),
                          const Divider(height: 12),
                        ],
                        if (relationships.isNotEmpty)
                          ExpansionTile(
                            leading: const Icon(Icons.hub_outlined),
                            title: Text(
                              'Relationships (${selectedRelationships.length}/${relationships.length})',
                            ),
                            children: [
                              for (var index = 0;
                                  index < relationships.length;
                                  index++)
                                CheckboxListTile(
                                  value: selectedRelationships.contains(index),
                                  title: Text(
                                    relationships[index]['type']?.toString() ??
                                        'relationship',
                                  ),
                                  subtitle: Text(
                                    '${relationships[index]['source']} → ${relationships[index]['target']}'
                                    '\n${relationships[index]['description'] ?? ''}',
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  onChanged: (checked) => setDialogState(() {
                                    checked == true
                                        ? selectedRelationships.add(index)
                                        : selectedRelationships.remove(index);
                                  }),
                                ),
                            ],
                          ),
                        ...candidates.map(
                          (item) => CheckboxListTile(
                            value: selected.contains(item['id'].toString()),
                            title: Text(item['name'].toString()),
                            subtitle: Text(
                              _candidateSubtitle(item),
                              maxLines: 4,
                              overflow: TextOverflow.ellipsis,
                            ),
                            secondary: Icon(
                              _candidateVerified(item)
                                  ? Icons.verified_outlined
                                  : Icons.info_outline,
                            ),
                            onChanged: (checked) => setDialogState(() {
                              final id = item['id'].toString();
                              checked == true
                                  ? selected.add(id)
                                  : selected.remove(id);
                            }),
                          ),
                        ),
                      ],
                    ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: () async {
                  await widget.apiService.discardWorldImport(
                    taskId: task['id'].toString(),
                    reason: 'discarded from preview',
                  );
                  if (context.mounted) Navigator.pop(context, false);
                },
                child: const Text('Discard task'),
              ),
              FilledButton(
                onPressed: selected.isEmpty
                    ? null
                    : () => Navigator.pop(context, true),
                child: Text(
                  request.mode == 'create' ? 'Create & import' : 'Append',
                ),
              ),
            ],
          ),
        ),
      );
      if (accepted == true) {
        var targetWorldId = currentWorldId;
        if (request.mode == 'create') {
          final created = await widget.apiService.createPersonaWorld(
            name: request.name,
            theme: request.query,
            background: 'Imported with AI Web Import.',
          );
          targetWorldId = created['id'].toString();
        }
        if (targetWorldId == null) return;
        await widget.apiService.confirmWorldImport(
          taskId: task['id'].toString(),
          worldId: targetWorldId,
          candidateIds: selected.toList(),
          relationshipIndexes: selectedRelationships.toList()..sort(),
        );
        await _loadWorlds(selectId: targetWorldId);
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<Map<String, dynamic>> _pollWorldImportTask(
    Map<String, dynamic> task,
  ) async {
    var current = task;
    for (var attempt = 0; attempt < 60; attempt++) {
      final status = current['status']?.toString() ?? '';
      if (!{
        'queued',
        'pending',
        'running',
        'searching',
        'extracting',
      }.contains(status)) {
        return current;
      }
      await Future<void>.delayed(const Duration(seconds: 1));
      if (!mounted) return current;
      current = await widget.apiService.fetchWorldImportTask(
        current['id'].toString(),
      );
    }
    return current;
  }

  Future<Map<String, dynamic>> _resolveWorldImportDisambiguation(
    Map<String, dynamic> task,
  ) async {
    var current = task;
    while (mounted && current['status']?.toString() == 'needs_disambiguation') {
      final result = current['result'] as Map<String, dynamic>? ?? {};
      final options = (result['disambiguation_options'] as List<dynamic>? ?? [])
          .cast<Map<String, dynamic>>();
      final candidates = (result['candidates'] as List<dynamic>? ?? [])
          .cast<Map<String, dynamic>>();
      if (options.length == 1 && candidates.isNotEmpty) {
        current = await widget.apiService.resolveWorldImport(
          taskId: current['id'].toString(),
          selectedOptionId: options.first['id'].toString(),
        );
        current = await _pollWorldImportTask(current);
        continue;
      }
      final selectedOptionId = await _chooseWorldImportDisambiguation(
        current,
        options,
      );
      if (!mounted) return {};
      if (selectedOptionId == null || selectedOptionId.isEmpty) {
        return {};
      }
      current = await widget.apiService.resolveWorldImport(
        taskId: current['id'].toString(),
        selectedOptionId: selectedOptionId,
      );
      current = await _pollWorldImportTask(current);
    }
    return current;
  }

  Future<String?> _chooseWorldImportDisambiguation(
    Map<String, dynamic> task,
    List<Map<String, dynamic>> options,
  ) {
    var selectedId =
        options.isNotEmpty ? options.first['id']?.toString() : null;
    final result = task['result'] as Map<String, dynamic>? ?? {};
    final candidateCount =
        (result['candidates'] as List<dynamic>? ?? const []).length;
    return showDialog<String?>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text('Choose work version (${options.length})'),
          content: SizedBox(
            width: 680,
            height: 460,
            child: options.isEmpty
                ? const Text(
                    'The search result is ambiguous, but no work options were returned.',
                  )
                : RadioGroup<String>(
                    groupValue: selectedId,
                    onChanged: (value) =>
                        setDialogState(() => selectedId = value),
                    child: ListView(
                      children: [
                        Text(
                          '"${task['query'] ?? ''}" may refer to multiple versions. Already found $candidateCount candidate(s); choose one to continue. Cancel keeps the task and will not generate unverified candidates.',
                        ),
                        const SizedBox(height: 12),
                        for (final option in options)
                          RadioListTile<String>(
                            value: option['id']?.toString() ?? '',
                            title: Text(
                              option['title']?.toString() ?? 'Untitled work',
                            ),
                            subtitle: _disambiguationSubtitle(option),
                            secondary: const Icon(Icons.manage_search),
                          ),
                      ],
                    ),
                  ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel, keep task'),
            ),
            FilledButton(
              onPressed: selectedId == null || selectedId!.isEmpty
                  ? null
                  : () => Navigator.pop(context, selectedId),
              child: const Text('Continue'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _disambiguationSubtitle(Map<String, dynamic> option) {
    final parts = [
      if ((option['author']?.toString() ?? '').isNotEmpty)
        'Author/version: ${option['author']}',
      if ((option['medium']?.toString() ?? '').isNotEmpty)
        'Medium: ${option['medium']}',
      if ((option['reason']?.toString() ?? '').isNotEmpty)
        'Reason: ${option['reason']}',
    ];
    final sources = (option['sources'] as List<dynamic>? ?? [])
        .cast<Map<String, dynamic>>()
        .map((source) => source['url']?.toString() ?? '')
        .where((url) => url.isNotEmpty)
        .take(3)
        .toList();
    return Text(
      [
        ...parts,
        if (sources.isNotEmpty) 'Sources: ${sources.join('\n')}',
      ].join('\n'),
      maxLines: 8,
      overflow: TextOverflow.ellipsis,
    );
  }

  Future<bool?> _confirmGeneratedFallback(Map<String, dynamic> task) {
    final error = task['error']?.toString();
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('No verified characters found'),
        content: Text(
          [
            if (error != null && error.isNotEmpty) error,
            'You can retry later, or explicitly generate unverified AI candidates.',
            'Generated candidates will be marked generated/unverified and will not include fake URLs.',
          ].join('\n\n'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep failure'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Generate unverified candidates'),
          ),
        ],
      ),
    );
  }

  Widget _worldImportEmptyPreview(
    Map<String, dynamic> task,
    List<String> errors,
    List<Map<String, dynamic>> sourceFailures,
  ) {
    final status = task['status']?.toString() ?? '';
    final hasSourceFailures = sourceFailures.isNotEmpty;
    final message = task['error']?.toString();
    final summary = message != null && message.isNotEmpty
        ? message
        : hasSourceFailures
            ? 'Found web pages, but no character information could be extracted.'
            : status == 'failed'
                ? 'No relevant work was found. Try a more specific title or retry later.'
                : 'No importable candidates found.';
    return ListView(
      children: [
        ListTile(
          leading: const Icon(Icons.info_outline),
          title: Text(
            status == 'failed' ? 'Import failed' : 'No importable characters',
          ),
          subtitle: Text(summary),
        ),
        if (errors.isNotEmpty) ...[
          const Divider(height: 16),
          ExpansionTile(
            leading: const Icon(Icons.error_outline),
            title: const Text('Error details'),
            children: [
              ListTile(subtitle: Text(errors.join('\n'))),
            ],
          ),
        ],
        if (sourceFailures.isNotEmpty) ...[
          const Divider(height: 16),
          const Text('Source failures'),
          ...sourceFailures.map(_sourceFailureTile),
        ],
      ],
    );
  }

  Widget _sourceFailureTile(Map<String, dynamic> item) {
    return ListTile(
      dense: true,
      leading: const Icon(Icons.link_off),
      title: Text(
        '${item['source'] ?? 'unknown'} · ${item['stage'] ?? 'unknown'}',
      ),
      subtitle: Text('status: ${item['status']?.toString() ?? 'n/a'}'),
    );
  }

  bool _candidateVerified(Map<String, dynamic> item) {
    final verified = item['verified'] ?? item['source_verified'];
    if (verified is bool) return verified;
    final status = (item['verification_status'] ??
            item['validation_status'] ??
            item['status'] ??
            '')
        .toString()
        .toLowerCase();
    final sources = item['sources'] as List<dynamic>? ?? const [];
    return sources.isNotEmpty ||
        status == 'verified' ||
        status == 'source_verified';
  }

  String _candidateSubtitle(Map<String, dynamic> item) {
    final sources = item['sources'] as List<dynamic>? ?? const [];
    final sourceLabels = sources
        .cast<Map<String, dynamic>>()
        .map((source) =>
            source['title'] ?? source['source_type'] ?? source['url'])
        .map((value) => value.toString())
        .where((value) => value.trim().isNotEmpty)
        .take(2)
        .join(', ');
    final status = _candidateVerified(item) ? 'verified' : 'unverified';
    return [
      '${item['source_type'] ?? 'source'} · $status · ${sources.length} source(s)',
      if (sourceLabels.isNotEmpty) sourceLabels,
      if ((item['faction'] ?? '').toString().isNotEmpty)
        'Faction: ${item['faction']}',
      item['summary']?.toString() ?? '',
    ].where((line) => line.trim().isNotEmpty).join('\n');
  }

  Future<void> _simulate() async {
    final worldId = _world?['id']?.toString();
    if (worldId == null || _personas.isEmpty) return;
    final selected = <String>{};
    final scenario = TextEditingController();
    final scenarioFocus = FocusNode();
    double rounds = 3;
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) {
          void useTemplate(String value) {
            scenario.text = value;
            scenario.selection = TextSelection.collapsed(
              offset: scenario.text.length,
            );
            scenarioFocus.requestFocus();
            setDialogState(() {});
          }

          final templates = {
            '刘备先亡': '如果刘备死在关羽前面，蜀汉内部和三国格局可能怎样变化？',
            '孙刘破裂': '如果孙刘联盟提前破裂，曹操会怎样调整战略？',
            '战役失败': '如果关键战役失败，各阵营会如何重新结盟？',
          };

          return AlertDialog(
            title: const Text('角色沙盘推演'),
            content: SizedBox(
              width: 620,
              height: 560,
              child: Column(
                children: [
                  const ListTile(
                    leading: Icon(Icons.science_outlined),
                    title: Text('基于人物设定的角色沙盘'),
                    subtitle: Text('不使用现实聊天证据，也不声称预测真实行为。'),
                  ),
                  TextField(
                    controller: scenario,
                    focusNode: scenarioFocus,
                    autofocus: true,
                    minLines: 3,
                    maxLines: 4,
                    textInputAction: TextInputAction.newline,
                    decoration: const InputDecoration(
                      labelText: '场景设定',
                      hintText: '例如：如果刘备死在关羽前面，蜀汉局势会怎样？',
                      helperText: '推演结果会尽量使用你输入场景的语言回复。',
                      border: OutlineInputBorder(),
                      filled: true,
                    ),
                    onTap: () => scenarioFocus.requestFocus(),
                    onChanged: (_) => setDialogState(() {}),
                  ),
                  const SizedBox(height: 8),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Wrap(
                      spacing: 8,
                      runSpacing: 4,
                      children: [
                        for (final template in templates.entries)
                          ActionChip(
                            label: Text(template.key),
                            onPressed: () => useTemplate(template.value),
                          ),
                      ],
                    ),
                  ),
                  Row(
                    children: [
                      const Text('轮次'),
                      Expanded(
                        child: Slider(
                          value: rounds,
                          min: 1,
                          max: 5,
                          divisions: 4,
                          onChanged: (value) =>
                              setDialogState(() => rounds = value),
                        ),
                      ),
                      Text('${rounds.round()}'),
                    ],
                  ),
                  const Align(
                    alignment: Alignment.centerLeft,
                    child: Text('选择人物（最多 8 人）'),
                  ),
                  Expanded(
                    child: ListView(
                      children: _personas
                          .map(
                            (item) => CheckboxListTile(
                              value: selected.contains(item['id'].toString()),
                              title: Text(item['name'].toString()),
                              subtitle:
                                  Text(item['faction']?.toString() ?? '未分组'),
                              onChanged: (checked) => setDialogState(() {
                                final id = item['id'].toString();
                                if (checked == true && selected.length < 8) {
                                  selected.add(id);
                                } else {
                                  selected.remove(id);
                                }
                              }),
                            ),
                          )
                          .toList(),
                    ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('取消'),
              ),
              FilledButton(
                onPressed: selected.isEmpty || scenario.text.trim().isEmpty
                    ? null
                    : () => Navigator.pop(context, true),
                child: const Text('运行'),
              ),
            ],
          );
        },
      ),
    );
    scenarioFocus.dispose();
    if (accepted != true) return;
    final result = await widget.apiService.runWorldSimulation(
      worldId: worldId,
      scenario: scenario.text.trim(),
      participantIds: selected.toList(),
      rounds: rounds.round(),
    );
    if (!mounted) return;
    await _showSimulationResultV2(result);
  }

  Future<void> _openSimulations() async {
    final worldId = _world?['id']?.toString();
    if (worldId == null) return;
    final items = await widget.apiService.fetchWorldSimulations(worldId);
    if (!mounted) return;
    final selected = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('历史沙盘'),
        content: SizedBox(
          width: 520,
          height: 420,
          child: items.isEmpty
              ? const Center(child: Text('还没有保存的沙盘推演'))
              : ListView(
                  children: items
                      .map(
                        (item) => ListTile(
                          leading: const Icon(Icons.history),
                          title: Text(item['title']?.toString() ?? ''),
                          subtitle: Text(
                            '${item['round_count']} 轮 · ${item['status']}',
                          ),
                          onTap: () => Navigator.pop(context, item),
                        ),
                      )
                      .toList(),
                ),
        ),
      ),
    );
    if (selected != null && mounted) {
      await _showSimulationResultV2(selected);
    }
  }

  // ignore: unused_element
  Future<void> _showSimulationResult(Map<String, dynamic> result) async {
    final values = result['rounds'] as List<dynamic>? ?? [];
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(result['title'].toString()),
        content: SizedBox(
          width: 720,
          height: 520,
          child: ListView(
            children: [
              ListTile(
                leading: const Icon(Icons.info_outline),
                title: Text(result['disclaimer'].toString()),
                subtitle: Text(
                  '设定完整度 ${(100 * (result['setting_completeness'] as num)).round()}% · '
                  '来源覆盖率 ${(100 * (result['source_coverage'] as num)).round()}%',
                ),
              ),
              ...values.map((raw) {
                final round = raw as Map<String, dynamic>;
                final people = round['people'] as List<dynamic>? ?? [];
                return Card(
                  child: ExpansionTile(
                    initiallyExpanded: round['round'] == 1,
                    title: Text('第 ${round['round']} 轮'),
                    children: people.map(
                      (rawPerson) {
                        final person = rawPerson as Map<String, dynamic>;
                        return ListTile(
                          title: Text(person['name'].toString()),
                          subtitle: Text(
                            '${person['state']}\n${person['possible_action']}',
                          ),
                        );
                      },
                    ).toList(),
                  ),
                );
              }),
            ],
          ),
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('关闭'),
          ),
        ],
      ),
    );
  }

  Future<void> _showSimulationResultV2(Map<String, dynamic> result) async {
    final rounds = result['rounds'] as List<dynamic>? ?? const [];
    List<String> stringList(Map<String, dynamic> value, String key) =>
        (value[key] as List<dynamic>? ?? const [])
            .map((item) => item.toString())
            .where((item) => item.trim().isNotEmpty)
            .toList();

    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(result['title']?.toString() ?? '角色沙盘推演'),
        content: SizedBox(
          width: 760,
          height: 560,
          child: ListView(
            children: [
              ListTile(
                leading: const Icon(Icons.auto_awesome),
                title: Text(result['disclaimer']?.toString() ?? ''),
                subtitle: Text(
                  '设定完整度 ${(((result['setting_completeness'] as num?)?.toDouble() ?? 0) * 100).round()}% · '
                  '来源覆盖率 ${(((result['source_coverage'] as num?)?.toDouble() ?? 0) * 100).round()}% · '
                  '${result['fallback'] == true ? '规则降级' : '模型推演'}',
                ),
              ),
              if (result['fallback'] == true)
                const Card(
                  color: Color(0xFFFFF7ED),
                  child: ListTile(
                    leading: Icon(Icons.info_outline),
                    title: Text('当前为规则降级结果'),
                    subtitle: Text(
                      '模型服务不可用或返回格式不可解析，系统只根据人物设定和关系做保守沙盘。配置可用模型后，推演会更具体。',
                    ),
                  ),
                ),
              ...rounds.map((rawRound) {
                final round = rawRound as Map<String, dynamic>;
                final people = round['people'] as List<dynamic>? ?? const [];
                final turningPoints = stringList(round, 'turning_points');
                final uncertainties = stringList(round, 'uncertainties');
                return Card(
                  color: const Color(0xFFF8FAFF),
                  child: ExpansionTile(
                    initiallyExpanded: round['round'] == 1,
                    title: Text('第 ${round['round']} 轮'),
                    subtitle: Text(round['summary']?.toString() ?? ''),
                    children: [
                      if (turningPoints.isNotEmpty)
                        ListTile(
                          dense: true,
                          leading: const Icon(Icons.bolt_outlined),
                          title: const Text('关键转折'),
                          subtitle: Text(turningPoints.join('\n')),
                        ),
                      ...people.map((rawPerson) {
                        final person = rawPerson as Map<String, dynamic>;
                        final action = person['likely_action'] ??
                            person['possible_action'] ??
                            '';
                        final confidence =
                            ((person['confidence'] as num?)?.toDouble() ?? 0) *
                                100;
                        return ListTile(
                          title: Text(
                            '${person['name']} · ${person['state'] ?? ''}',
                          ),
                          subtitle: Text(
                            [
                              if (action.toString().isNotEmpty) '行动：$action',
                              if ((person['reasoning'] ?? '')
                                  .toString()
                                  .isNotEmpty)
                                '依据：${person['reasoning']}',
                              if ((person['risk'] ?? '').toString().isNotEmpty)
                                '风险：${person['risk']}',
                            ].join('\n'),
                          ),
                          trailing: Text('${confidence.round()}%'),
                        );
                      }),
                      if (uncertainties.isNotEmpty)
                        ListTile(
                          dense: true,
                          leading: const Icon(Icons.help_outline),
                          title: const Text('不确定性'),
                          subtitle: Text(uncertainties.join('\n')),
                        ),
                    ],
                  ),
                );
              }),
            ],
          ),
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('关闭'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('角色世界'),
        actions: [
          IconButton(
            onPressed: _loadWorlds,
            icon: const Icon(Icons.refresh),
            tooltip: '刷新',
          ),
        ],
      ),
      body: Column(
        children: [
          if (_loading) const LinearProgressIndicator(),
          Expanded(
            child: Row(
              children: [
                SizedBox(width: 250, child: _worldList()),
                const VerticalDivider(width: 1),
                Expanded(child: _workspace()),
                if (_selectedPersona != null) ...[
                  const VerticalDivider(width: 1),
                  SizedBox(
                      width: 320, child: _personaDetail(_selectedPersona!)),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _worldList() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: FilledButton.icon(
            onPressed: _createWorld,
            icon: const Icon(Icons.add),
            label: const Text('新建世界'),
          ),
        ),
        Expanded(
          child: _worlds.isEmpty
              ? const Center(child: Text('创建一个独立的角色世界'))
              : ListView(
                  children: _worlds
                      .map(
                        (item) => ListTile(
                          selected: item['id'] == _world?['id'],
                          leading: const Icon(Icons.public),
                          title: Text(item['name'].toString()),
                          subtitle: Text(
                            '${item['persona_count']} 人 · '
                            '${item['relationship_count']} 条关系',
                          ),
                          onTap: () => _selectWorld(item['id'].toString()),
                        ),
                      )
                      .toList(),
                ),
        ),
      ],
    );
  }

  Widget _workspace() {
    if (_error != null) return Center(child: Text(_error!));
    if (_world == null) {
      return const Center(child: Text('角色世界与现实联系人、聊天和证据完全隔离。'));
    }
    return Column(
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 6,
          children: [
            TextButton.icon(
              onPressed: () => _editPersona(),
              icon: const Icon(Icons.person_add_alt),
              label: const Text('添加人物'),
            ),
            TextButton.icon(
              onPressed: _personas.length < 2 ? null : _addRelationship,
              icon: const Icon(Icons.link),
              label: const Text('连接人物'),
            ),
            TextButton.icon(
              onPressed: _importCatalog,
              icon: const Icon(Icons.auto_stories),
              label: const Text('精选图库'),
            ),
            TextButton.icon(
              onPressed: _searchOnlineV08,
              icon: const Icon(Icons.travel_explore),
              label: const Text('联网搜索'),
            ),
            FilledButton.icon(
              onPressed: _personas.isEmpty ? null : _simulate,
              icon: const Icon(Icons.play_arrow),
              label: const Text('角色沙盘'),
            ),
            TextButton.icon(
              onPressed: _openSimulations,
              icon: const Icon(Icons.history),
              label: const Text('历史沙盘'),
            ),
          ],
        ),
        const Divider(height: 1),
        Expanded(
          child: _graph == null || _graph!.nodes.isEmpty
              ? const Center(child: Text('添加人物或从精选图库导入后，这里会出现拓扑图。'))
              : TopologyGraph(
                  graph: _graph!,
                  selectedNodeId: _selectedNode?.id,
                  onNodeSelected: (node) =>
                      setState(() => _selectedNode = node),
                  showLabels: true,
                ),
        ),
      ],
    );
  }

  Widget _personaDetail(Map<String, dynamic> persona) {
    final completeness =
        ((persona['setting_completeness'] as num?)?.toDouble() ?? 0) * 100;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Row(
          children: [
            const CircleAvatar(child: Icon(Icons.person_outline)),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                persona['name'].toString(),
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            IconButton(
              onPressed: () => _editPersona(persona),
              icon: const Icon(Icons.edit_outlined),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Chip(label: Text(persona['faction']?.toString() ?? '未分组')),
        Text('设定完整度 ${completeness.round()}%'),
        LinearProgressIndicator(value: completeness / 100),
        const SizedBox(height: 16),
        Text(persona['summary'].toString()),
        const SizedBox(height: 12),
        Text('来源：${persona['source_type']}'),
        const SizedBox(height: 20),
        OutlinedButton.icon(
          onPressed: () async {
            final worldId = _world!['id'].toString();
            await widget.apiService.deleteWorldPersona(
              worldId,
              persona['id'].toString(),
            );
            await _selectWorld(worldId);
          },
          icon: const Icon(Icons.delete_outline),
          label: const Text('删除人物'),
        ),
      ],
    );
  }
}
