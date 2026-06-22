class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.personId,
    required this.senderName,
    required this.direction,
    required this.content,
    this.sentAt,
  });

  final String id;
  final String? personId;
  final String senderName;
  final String direction;
  final String content;
  final String? sentAt;

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id']?.toString() ?? '',
      personId: json['person_id']?.toString(),
      senderName: json['sender_name']?.toString() ?? '',
      direction: json['direction']?.toString() ?? '',
      content: json['content']?.toString() ?? '',
      sentAt: json['sent_at']?.toString(),
    );
  }
}
