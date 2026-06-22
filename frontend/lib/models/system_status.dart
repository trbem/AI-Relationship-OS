class SystemStatus {
  const SystemStatus({
    required this.backendReady,
    required this.databaseReady,
    required this.aiReady,
    required this.initialized,
    required this.version,
    this.aiMessage,
  });

  final bool backendReady;
  final bool databaseReady;
  final bool aiReady;
  final bool initialized;
  final String version;
  final String? aiMessage;

  bool get canContinue => backendReady && databaseReady && initialized;

  factory SystemStatus.fromJson(Map<String, dynamic> json) {
    bool ready(dynamic value, {bool fallback = false}) {
      if (value is bool) return value;
      if (value is String) {
        return const {'ok', 'ready', 'healthy', 'configured', 'true'}
            .contains(value.toLowerCase());
      }
      if (value is Map<String, dynamic>) {
        return ready(value['ready'] ?? value['status'], fallback: fallback);
      }
      return fallback;
    }

    return SystemStatus(
      backendReady: ready(json['backend'], fallback: true),
      databaseReady: ready(json['database'] ?? json['db']),
      aiReady: ready(json['ai'] ?? json['llm']),
      initialized: ready(json['initialized'], fallback: true),
      version: json['version']?.toString() ?? '未知',
      aiMessage: json['ai_message']?.toString() ??
          (json['ai'] is Map
              ? (json['ai'] as Map)['message']?.toString()
              : null),
    );
  }
}
