class MemoryItem {
  const MemoryItem({
    required this.id,
    required this.event,
    required this.emotion,
    required this.importance,
    required this.sourceMessageIds,
    required this.timestamp,
  });

  final String id;
  final String event;
  final String emotion;
  final double importance;
  final String? sourceMessageIds;
  final String? timestamp;

  factory MemoryItem.fromJson(Map<String, dynamic> json) {
    return MemoryItem(
      id: json['id'] as String? ?? '',
      event: json['event'] as String? ?? '',
      emotion: json['emotion'] as String? ?? '',
      importance: (json['importance'] as num?)?.toDouble() ?? 0,
      sourceMessageIds: json['source_message_ids'] as String?,
      timestamp: json['timestamp'] as String?,
    );
  }
}
