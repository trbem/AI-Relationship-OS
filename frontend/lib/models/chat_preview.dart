class ChatPreviewMessage {
  const ChatPreviewMessage({
    required this.senderName,
    required this.content,
    this.sentAt,
  });

  final String senderName;
  final String content;
  final String? sentAt;

  factory ChatPreviewMessage.fromJson(Map<String, dynamic> json) {
    return ChatPreviewMessage(
      senderName: json['sender_name']?.toString() ?? '',
      content: json['content']?.toString() ?? '',
      sentAt: json['sent_at']?.toString(),
    );
  }
}

class ChatPreview {
  const ChatPreview({
    required this.filename,
    required this.format,
    required this.encoding,
    required this.inputType,
    required this.extractionMethod,
    required this.recognizedText,
    required this.importCandidates,
    required this.warnings,
    required this.messageCount,
    required this.senderNames,
    required this.sample,
  });

  final String filename;
  final String format;
  final String encoding;
  final String inputType;
  final String extractionMethod;
  final String recognizedText;
  final List<String> importCandidates;
  final List<String> warnings;
  final int messageCount;
  final List<String> senderNames;
  final List<ChatPreviewMessage> sample;

  factory ChatPreview.fromJson(Map<String, dynamic> json) {
    return ChatPreview(
      filename: json['filename']?.toString() ?? '',
      format: json['format']?.toString() ?? '',
      encoding: json['encoding']?.toString() ?? '',
      inputType: json['input_type']?.toString() ?? 'text',
      extractionMethod: json['extraction_method']?.toString() ?? 'decode',
      recognizedText: json['recognized_text']?.toString() ?? '',
      importCandidates: (json['import_candidates'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .toList(),
      warnings: (json['warnings'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .toList(),
      messageCount: (json['message_count'] as num?)?.toInt() ?? 0,
      senderNames: (json['sender_names'] as List<dynamic>? ?? [])
          .map((item) => item.toString())
          .toList(),
      sample: (json['sample'] as List<dynamic>? ?? [])
          .map(
            (item) => ChatPreviewMessage.fromJson(item as Map<String, dynamic>),
          )
          .toList(),
    );
  }
}
