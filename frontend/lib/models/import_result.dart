class ImportResult {
  const ImportResult({
    required this.status,
    required this.contacts,
    required this.messages,
    required this.importId,
  });

  final String status;
  final int contacts;
  final int messages;
  final String importId;

  factory ImportResult.fromJson(Map<String, dynamic> json) {
    return ImportResult(
      status: json['status'] as String? ?? 'success',
      contacts: json['contacts'] as int? ?? 0,
      messages: json['messages'] as int? ?? 0,
      importId: json['import_id'] as String? ?? '',
    );
  }
}
