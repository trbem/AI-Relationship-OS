class AppSettings {
  const AppSettings({
    this.mimoApiKey = '',
    this.provider = 'openai_compatible',
    this.baseUrl = '',
    this.model = 'mimo-v2.5',
    this.ollamaEnabled = true,
    this.ollamaBaseUrl = 'http://127.0.0.1:11434',
    this.timeoutSeconds = 120,
    this.temperature = 0.2,
    this.dataDirectory = '',
    this.hasStoredApiKey = false,
    this.restartRequired = false,
    this.activeModelProvider = 'openai_compatible',
    this.activeModel = '',
    this.activeModelLabel = '',
    this.fallbackModelLabel = '',
    this.remoteConfigured = false,
  });

  final String mimoApiKey;
  final String provider;
  final String baseUrl;
  final String model;
  final bool ollamaEnabled;
  final String ollamaBaseUrl;
  final int timeoutSeconds;
  final double temperature;
  final String dataDirectory;
  final bool hasStoredApiKey;
  final bool restartRequired;
  final String activeModelProvider;
  final String activeModel;
  final String activeModelLabel;
  final String fallbackModelLabel;
  final bool remoteConfigured;

  factory AppSettings.fromJson(Map<String, dynamic> json) {
    return AppSettings(
      provider: json['llm_provider']?.toString() ?? 'openai_compatible',
      baseUrl: json['llm_base_url']?.toString() ?? '',
      model: json['model']?.toString() ??
          json['llm_model']?.toString() ??
          json['completion_model']?.toString() ??
          'mimo-v2.5',
      ollamaEnabled: json['ollama_enabled'] as bool? ??
          json['llm_fallback_enabled'] as bool? ??
          true,
      ollamaBaseUrl:
          json['ollama_base_url']?.toString() ?? 'http://127.0.0.1:11434',
      timeoutSeconds: (json['timeout_seconds'] as num?)?.toInt() ??
          (json['llm_timeout_seconds'] as num?)?.toInt() ??
          120,
      temperature: (json['llm_temperature'] as num?)?.toDouble() ?? 0.2,
      dataDirectory: json['data_directory']?.toString() ?? '',
      hasStoredApiKey: json['has_api_key'] as bool? ??
          json['llm_api_key_configured'] as bool? ??
          false,
      restartRequired: json['restart_required'] as bool? ?? false,
      activeModelProvider:
          json['active_model_provider']?.toString() ?? 'openai_compatible',
      activeModel: json['active_model']?.toString() ?? '',
      activeModelLabel: json['active_model_label']?.toString() ?? '',
      fallbackModelLabel: json['fallback_model_label']?.toString() ?? '',
      remoteConfigured: json['remote_configured'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        if (mimoApiKey.isNotEmpty) 'llm_api_key': mimoApiKey,
        'llm_provider': provider,
        'llm_base_url': baseUrl,
        'llm_model': model,
        'completion_model': model,
        'llm_fallback_enabled': ollamaEnabled,
        'ollama_base_url': ollamaBaseUrl,
        'llm_timeout_seconds': timeoutSeconds,
        'llm_temperature': temperature,
        if (dataDirectory.isNotEmpty) 'data_directory': dataDirectory,
      };
}
