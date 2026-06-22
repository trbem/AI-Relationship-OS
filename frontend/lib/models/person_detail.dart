import 'memory_item.dart';

class PersonDetail {
  const PersonDetail({
    required this.id,
    required this.userId,
    required this.name,
    required this.profileSummary,
    required this.confidence,
    required this.messages,
    required this.memories,
    required this.vectorRefs,
  });

  final String id;
  final String userId;
  final String name;
  final String? profileSummary;
  final double? confidence;
  final List<String> messages;
  final List<MemoryItem> memories;
  final List<String> vectorRefs;

  factory PersonDetail.fromJson(Map<String, dynamic> json) {
    return PersonDetail(
      id: json['id'] as String? ?? '',
      userId: json['user_id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      profileSummary: json['profile_summary'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble(),
      messages: (json['messages'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .toList(),
      memories: (json['memories'] as List<dynamic>? ?? [])
          .map((item) => MemoryItem.fromJson(item as Map<String, dynamic>))
          .toList(),
      vectorRefs: (json['vector_refs'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .toList(),
    );
  }
}
