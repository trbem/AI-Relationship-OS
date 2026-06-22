class GraphNode {
  const GraphNode({
    required this.id,
    required this.name,
    required this.type,
    required this.group,
    required this.weight,
    required this.emotion,
    required this.intimacy,
    required this.interaction,
    required this.trust,
    required this.recentActive,
    required this.activeScore,
    required this.relationshipScore,
    required this.hint,
    required this.scoreComponents,
    required this.changeReasons,
    this.summary,
    this.occurredAt,
  });

  final String id;
  final String name;
  final String type;
  final String group;
  final double weight;
  final String emotion;
  final double intimacy;
  final int interaction;
  final double trust;
  final bool recentActive;
  final double activeScore;
  final double relationshipScore;
  final String? hint;
  final Map<String, double> scoreComponents;
  final List<String> changeReasons;
  final String? summary;
  final String? occurredAt;

  factory GraphNode.fromJson(Map<String, dynamic> json) {
    return GraphNode(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      type: json['type'] as String? ?? 'person',
      group: json['group'] as String? ?? '未分类',
      weight: (json['weight'] as num?)?.toDouble() ?? 0,
      emotion: json['emotion'] as String? ?? 'neutral',
      intimacy: (json['intimacy'] as num?)?.toDouble() ?? 0,
      interaction: (json['interaction'] as num?)?.toInt() ?? 0,
      trust: (json['trust'] as num?)?.toDouble() ?? 0,
      recentActive: json['recent_active'] as bool? ?? false,
      activeScore: (json['active_score'] as num?)?.toDouble() ?? 0,
      relationshipScore: (json['relationship_score'] as num?)?.toDouble() ?? 0,
      hint: json['hint'] as String?,
      scoreComponents:
          (json['score_components'] as Map<String, dynamic>? ?? const {})
              .map((key, value) => MapEntry(key, (value as num).toDouble())),
      changeReasons: (json['change_reasons'] as List<dynamic>? ?? const [])
          .map((item) => item.toString())
          .toList(),
      summary: json['summary']?.toString(),
      occurredAt: json['occurred_at']?.toString(),
    );
  }
}

class GraphLink {
  const GraphLink({
    required this.source,
    required this.target,
    required this.strength,
    required this.interaction,
    required this.emotion,
    required this.width,
    required this.relationType,
  });

  final String source;
  final String target;
  final double strength;
  final int interaction;
  final String emotion;
  final double width;
  final String relationType;

  factory GraphLink.fromJson(Map<String, dynamic> json) {
    return GraphLink(
      source: json['source'] as String? ?? '',
      target: json['target'] as String? ?? '',
      strength: (json['strength'] as num?)?.toDouble() ?? 0,
      interaction: (json['interaction'] as num?)?.toInt() ?? 0,
      emotion: json['emotion'] as String? ?? 'neutral',
      width: (json['width'] as num?)?.toDouble() ?? 1,
      relationType: json['relation_type']?.toString() ?? 'relationship',
    );
  }
}

class GraphInsights {
  const GraphInsights({
    required this.topChanges,
    required this.activeCount,
    required this.strongestTie,
    required this.stressCount,
  });

  final List<String> topChanges;
  final int activeCount;
  final String? strongestTie;
  final int stressCount;

  factory GraphInsights.fromJson(Map<String, dynamic> json) {
    return GraphInsights(
      topChanges: (json['top_changes'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .toList(),
      activeCount: (json['active_count'] as num?)?.toInt() ?? 0,
      strongestTie: json['strongest_tie'] as String?,
      stressCount: (json['stress_count'] as num?)?.toInt() ?? 0,
    );
  }
}

class RelationshipGraph {
  const RelationshipGraph({
    required this.nodes,
    required this.links,
    required this.insights,
  });

  final List<GraphNode> nodes;
  final List<GraphLink> links;
  final GraphInsights insights;

  factory RelationshipGraph.fromJson(Map<String, dynamic> json) {
    return RelationshipGraph(
      nodes: (json['nodes'] as List<dynamic>? ?? [])
          .map((item) => GraphNode.fromJson(item as Map<String, dynamic>))
          .toList(),
      links: (json['links'] as List<dynamic>? ?? [])
          .map((item) => GraphLink.fromJson(item as Map<String, dynamic>))
          .toList(),
      insights: GraphInsights.fromJson(
        json['insights'] as Map<String, dynamic>? ?? {},
      ),
    );
  }
}

class TimelineSnapshot {
  const TimelineSnapshot({
    required this.days,
    required this.label,
    required this.nodes,
  });

  final int days;
  final String label;
  final List<GraphNode> nodes;

  factory TimelineSnapshot.fromJson(Map<String, dynamic> json) {
    return TimelineSnapshot(
      days: (json['days'] as num?)?.toInt() ?? 0,
      label: json['label'] as String? ?? '',
      nodes: (json['nodes'] as List<dynamic>? ?? [])
          .map((item) => GraphNode.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
}

class RelationshipTimeline {
  const RelationshipTimeline({
    required this.series,
    required this.checkpoints,
  });

  final List<TimelineSnapshot> series;
  final List<int> checkpoints;

  factory RelationshipTimeline.fromJson(Map<String, dynamic> json) {
    return RelationshipTimeline(
      series: (json['series'] as List<dynamic>? ?? [])
          .map(
              (item) => TimelineSnapshot.fromJson(item as Map<String, dynamic>))
          .toList(),
      checkpoints: (json['checkpoints'] as List<dynamic>? ?? [])
          .map((item) => (item as num).toInt())
          .toList(),
    );
  }
}
