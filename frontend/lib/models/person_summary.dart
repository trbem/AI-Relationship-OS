class PersonSummary {
  const PersonSummary({
    required this.id,
    required this.userId,
    required this.name,
    required this.profileSummary,
    required this.confidence,
    required this.messageCount,
    required this.memoryCount,
  });

  final String id;
  final String userId;
  final String name;
  final String? profileSummary;
  final double? confidence;
  final int messageCount;
  final int memoryCount;

  factory PersonSummary.fromJson(Map<String, dynamic> json) {
    return PersonSummary(
      id: json['id'] as String? ?? '',
      userId: json['user_id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      profileSummary: json['profile_summary'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble(),
      messageCount: json['message_count'] as int? ?? 0,
      memoryCount: json['memory_count'] as int? ?? 0,
    );
  }
}
