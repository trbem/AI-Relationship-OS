import 'package:flutter_test/flutter_test.dart';
import 'package:relationship_os/models/app_settings.dart';

void main() {
  test('parses and serializes web search settings', () {
    final settings = AppSettings.fromJson({
      'llm_api_key_configured': true,
      'web_search_api_key_configured': true,
      'web_search_base_url': 'https://api.openai.com/v1',
      'web_search_model': 'gpt-4.1-mini',
      'web_search_timeout_seconds': 45,
    });

    expect(settings.hasStoredApiKey, isTrue);
    expect(settings.hasStoredWebSearchApiKey, isTrue);
    expect(settings.webSearchBaseUrl, 'https://api.openai.com/v1');
    expect(settings.webSearchModel, 'gpt-4.1-mini');
    expect(settings.webSearchTimeoutSeconds, 45);

    final json = const AppSettings(
      webSearchApiKey: 'search-key',
      webSearchBaseUrl: 'https://example.test/v1',
      webSearchModel: 'search-model',
      webSearchTimeoutSeconds: 30,
    ).toJson();

    expect(json['web_search_api_key'], 'search-key');
    expect(json['web_search_base_url'], 'https://example.test/v1');
    expect(json['web_search_model'], 'search-model');
    expect(json['web_search_timeout_seconds'], 30);
  });
}
