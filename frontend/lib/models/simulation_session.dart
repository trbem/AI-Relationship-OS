import 'simulation_result.dart';

class SimulationTimelineMessage {
  const SimulationTimelineMessage({
    required this.id,
    required this.role,
    required this.kind,
    required this.content,
    required this.createdAt,
    this.result,
  });

  final String id;
  final String role;
  final String kind;
  final String content;
  final String createdAt;
  final SimulationResult? result;

  factory SimulationTimelineMessage.fromJson(Map<String, dynamic> json) {
    final payload = json['payload'];
    return SimulationTimelineMessage(
      id: json['id']?.toString() ?? '',
      role: json['role']?.toString() ?? '',
      kind: json['kind']?.toString() ?? '',
      content: json['content']?.toString() ?? '',
      createdAt: json['created_at']?.toString() ?? '',
      result: payload is Map<String, dynamic>
          ? SimulationResult.fromJson(payload)
          : null,
    );
  }
}

class SimulationSession {
  const SimulationSession({
    required this.id,
    required this.personId,
    required this.title,
    required this.originalQuestion,
    required this.status,
    required this.updatedAt,
    required this.messages,
  });

  final String id;
  final String personId;
  final String title;
  final String originalQuestion;
  final String status;
  final String updatedAt;
  final List<SimulationTimelineMessage> messages;

  factory SimulationSession.fromJson(Map<String, dynamic> json) {
    return SimulationSession(
      id: json['id']?.toString() ?? '',
      personId: json['person_id']?.toString() ?? '',
      title: json['title']?.toString() ?? '',
      originalQuestion: json['original_question']?.toString() ?? '',
      status: json['status']?.toString() ?? 'active',
      updatedAt: json['updated_at']?.toString() ?? '',
      messages: (json['messages'] as List<dynamic>? ?? [])
          .map((item) =>
              SimulationTimelineMessage.fromJson(item as Map<String, dynamic>))
          .toList(),
    );
  }
}
