import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import '../models/app_settings.dart';
import '../models/chat_message.dart';
import '../models/chat_preview.dart';
import '../models/import_task.dart';
import '../models/person_detail.dart';
import '../models/person_summary.dart';
import '../models/relationship_graph.dart';
import '../models/simulation_result.dart';
import '../models/simulation_session.dart';
import '../models/system_status.dart';

class AuthTokens {
  const AuthTokens({
    required this.accessToken,
    required this.userId,
    required this.email,
  });

  final String accessToken;
  final String userId;
  final String email;
}

enum ApiErrorType {
  authentication,
  connection,
  timeout,
  validation,
  invalidPassword,
  invalidFile,
  payloadTooLarge,
  incompatibleVersion,
  server,
  notFound,
  unknown,
}

class ApiException implements Exception {
  const ApiException({
    required this.type,
    required this.message,
    this.statusCode,
  });

  final ApiErrorType type;
  final String message;
  final int? statusCode;

  bool get requiresLogin => type == ApiErrorType.authentication;

  @override
  String toString() => message;
}

class ApiService {
  ApiService({
    required this.baseUrl,
    Duration timeout = const Duration(seconds: 120),
    HttpClient Function()? clientFactory,
  })  : _timeout = timeout,
        _clientFactory = clientFactory ?? HttpClient.new;

  final String baseUrl;
  final HttpClient Function() _clientFactory;
  Duration _timeout;
  String? _token;

  bool get hasToken => _token != null;

  void setToken(String token) => _token = token;

  void clearToken() => _token = null;

  void setTimeout(Duration timeout) => _timeout = timeout;

  Future<SystemStatus> fetchSystemStatus() async {
    final data = await _jsonRequest(
      'GET',
      '/api/system/status',
      authenticated: false,
    ) as Map<String, dynamic>;
    return SystemStatus.fromJson(data);
  }

  Future<AuthTokens> register({
    required String email,
    required String password,
  }) async {
    final data = await _jsonRequest(
      'POST',
      '/api/system/auth/register',
      body: {'email': email, 'password': password},
      authenticated: false,
    ) as Map<String, dynamic>;
    return _acceptTokens(data);
  }

  Future<AuthTokens> login({
    required String email,
    required String password,
  }) async {
    final data = await _jsonRequest(
      'POST',
      '/api/system/auth/login',
      body: {'email': email, 'password': password},
      authenticated: false,
    ) as Map<String, dynamic>;
    return _acceptTokens(data);
  }

  Future<void> validateSession() async {
    await _jsonRequest('GET', '/api/system/auth/me');
  }

  AuthTokens _acceptTokens(Map<String, dynamic> data) {
    final tokens = AuthTokens(
      accessToken: data['access_token'] as String,
      userId: data['user_id']?.toString() ?? '',
      email: data['email']?.toString() ?? '',
    );
    _token = tokens.accessToken;
    return tokens;
  }

  Future<ImportTask> createImportTask({
    required String filename,
    required Uint8List bytes,
    required String selfName,
  }) async {
    final boundary = 'relationship-os-${DateTime.now().microsecondsSinceEpoch}';
    final builder = BytesBuilder();

    void writeText(String value) => builder.add(utf8.encode(value));

    writeText('--$boundary\r\n');
    writeText('Content-Disposition: form-data; name="self_name"\r\n\r\n');
    writeText('$selfName\r\n');
    writeText('--$boundary\r\n');
    writeText(
      'Content-Disposition: form-data; name="file"; '
      'filename="${_escapeFilename(filename)}"\r\n',
    );
    writeText('Content-Type: application/octet-stream\r\n\r\n');
    builder.add(bytes);
    writeText('\r\n--$boundary--\r\n');

    final data = await _rawRequest(
      'POST',
      '/api/chat/import',
      contentType: 'multipart/form-data; boundary=$boundary',
      body: builder.takeBytes(),
    ) as Map<String, dynamic>;
    return ImportTask.fromJson(data);
  }

  Future<ChatPreview> previewChat({
    required String filename,
    required Uint8List bytes,
  }) async {
    final data = await _multipartFileRequest(
      '/api/chat/preview',
      filename: filename,
      bytes: bytes,
    );
    return ChatPreview.fromJson(data);
  }

  Future<ImportTask> fetchImportTask(String taskId) async {
    final data = await _jsonRequest(
      'GET',
      '/api/chat/imports/${Uri.encodeComponent(taskId)}',
    ) as Map<String, dynamic>;
    return ImportTask.fromJson(data);
  }

  Future<ImportTask> retryImportTask(String taskId) async {
    final data = await _jsonRequest(
      'POST',
      '/api/chat/imports/${Uri.encodeComponent(taskId)}/retry',
    ) as Map<String, dynamic>;
    return ImportTask.fromJson(data);
  }

  Future<AppSettings> fetchSettings() async {
    final data = await _jsonRequest(
      'GET',
      '/api/system/settings',
    ) as Map<String, dynamic>;
    return AppSettings.fromJson(data);
  }

  Future<AppSettings> updateSettings(AppSettings settings) async {
    final data = await _jsonRequest(
      'PUT',
      '/api/system/settings',
      body: settings.toJson(),
    ) as Map<String, dynamic>;
    setTimeout(Duration(seconds: settings.timeoutSeconds));
    return AppSettings.fromJson(data);
  }

  Future<Map<String, dynamic>> testAiConnection(AppSettings settings) async {
    return await _jsonRequest(
      'POST',
      '/api/system/ai/test-connection',
      body: settings.toJson(),
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> testWebSearchConnection(
    AppSettings settings,
  ) async {
    return await _jsonRequest(
      'POST',
      '/api/system/ai/test-web-search',
      body: settings.toJson(),
    ) as Map<String, dynamic>;
  }

  Future<List<PersonSummary>> fetchPersons() async {
    final data = await _jsonRequest('GET', '/api/person') as List<dynamic>;
    return data
        .map((item) => PersonSummary.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<List<ChatMessage>> fetchMessages(String personId) async {
    final data = await _jsonRequest(
      'GET',
      '/api/chat/messages?person_id=${Uri.encodeQueryComponent(personId)}',
    ) as List<dynamic>;
    return data
        .map((item) => ChatMessage.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<void> deleteMessage(String messageId) async {
    await _jsonRequest(
      'DELETE',
      '/api/chat/messages/${Uri.encodeComponent(messageId)}',
    );
  }

  Future<void> mergePersons({
    required String sourcePersonId,
    required String targetPersonId,
  }) async {
    await _jsonRequest(
      'POST',
      '/api/person/merge',
      body: {
        'source_person_id': sourcePersonId,
        'target_person_id': targetPersonId,
      },
    );
  }

  Future<Uint8List> downloadBackup({required String password}) {
    return _download(
      '/api/data/backup',
      method: 'POST',
      jsonBody: {'password': password},
    );
  }

  Future<Uint8List> downloadExport() {
    return _download('/api/data/export');
  }

  Future<void> restoreBackup({
    required String filename,
    required Uint8List bytes,
    String? password,
  }) async {
    await _multipartFileRequest(
      '/api/data/restore',
      filename: filename,
      bytes: bytes,
      fields: {
        if (password != null) 'password': password,
      },
    );
  }

  Future<PersonDetail> fetchPersonDetail(String personId) async {
    final data = await _jsonRequest(
      'GET',
      '/api/person/$personId',
    ) as Map<String, dynamic>;
    return PersonDetail.fromJson(data);
  }

  Future<Map<String, dynamic>> generatePersona(String personId) async {
    return await _jsonRequest(
      'POST',
      '/api/person/generate',
      body: {'contact_id': personId},
    ) as Map<String, dynamic>;
  }

  Future<RelationshipGraph> fetchRelationshipGraph({int? days}) async {
    final query = days == null ? '' : '?days=$days';
    final data = await _jsonRequest(
      'GET',
      '/api/graph/relationship-map$query',
    ) as Map<String, dynamic>;
    return RelationshipGraph.fromJson(data);
  }

  Future<SimulationResult> simulate({
    required String personId,
    required String question,
  }) async {
    final data = await _jsonRequest(
      'POST',
      '/api/simulate',
      body: {'person_id': personId, 'question': question},
    ) as Map<String, dynamic>;
    return SimulationResult.fromJson(data);
  }

  Future<List<SimulationSession>> fetchSimulationSessions() async {
    final data =
        await _jsonRequest('GET', '/api/simulate/sessions') as List<dynamic>;
    return data
        .map((item) => SimulationSession.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<SimulationSession> fetchSimulationSession(String sessionId) async {
    final data = await _jsonRequest(
      'GET',
      '/api/simulate/sessions/${Uri.encodeComponent(sessionId)}',
    ) as Map<String, dynamic>;
    return SimulationSession.fromJson(data);
  }

  Future<SimulationSession> createSimulationSession({
    required String personId,
    required String question,
    String? title,
  }) async {
    final data = await _jsonRequest(
      'POST',
      '/api/simulate/sessions',
      body: {
        'person_id': personId,
        'question': question,
        if (title != null) 'title': title,
      },
    ) as Map<String, dynamic>;
    return SimulationSession.fromJson(data);
  }

  Future<SimulationTimelineMessage> continueSimulationSession({
    required String sessionId,
    required String content,
  }) async {
    final data = await _jsonRequest(
      'POST',
      '/api/simulate/sessions/${Uri.encodeComponent(sessionId)}/messages',
      body: {'content': content},
    ) as Map<String, dynamic>;
    return SimulationTimelineMessage.fromJson(data);
  }

  Future<void> deleteSimulationSession(String sessionId) async {
    await _jsonRequest(
      'DELETE',
      '/api/simulate/sessions/${Uri.encodeComponent(sessionId)}',
    );
  }

  Future<RelationshipGraph> fetchKnowledgeGraph({
    int days = 30,
    String? personId,
  }) async {
    final parameters = <String>[
      'days=$days',
      if (personId != null) 'person_id=${Uri.encodeQueryComponent(personId)}',
    ];
    final data = await _jsonRequest(
      'GET',
      '/api/graph/knowledge-map?${parameters.join('&')}',
    ) as Map<String, dynamic>;
    return RelationshipGraph.fromJson(data);
  }

  Future<Map<String, dynamic>> createCommunicationScenario({
    required String sessionId,
    required String label,
    required String wording,
    String? timing,
    String? channel,
    String? goal,
  }) async {
    return await _jsonRequest(
      'POST',
      '/api/simulate/sessions/${Uri.encodeComponent(sessionId)}/scenarios',
      body: {
        'label': label,
        'wording': wording,
        if (timing != null) 'timing': timing,
        if (channel != null) 'channel': channel,
        if (goal != null) 'goal': goal,
      },
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> compareCommunicationScenarios(
      String sessionId) async {
    return await _jsonRequest(
      'POST',
      '/api/simulate/sessions/${Uri.encodeComponent(sessionId)}/compare',
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createStrategyReport(String sessionId) async {
    return await _jsonRequest(
      'POST',
      '/api/reports',
      body: {'session_id': sessionId},
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createGroupSimulation({
    required String primaryPersonId,
    required List<String> participantIds,
    required String title,
    required String goal,
    int rounds = 3,
  }) async {
    return await _jsonRequest(
      'POST',
      '/api/group-simulations',
      body: {
        'primary_person_id': primaryPersonId,
        'participant_ids': participantIds,
        'title': title,
        'goal': goal,
        'rounds': rounds,
      },
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> runGroupSimulation(String simulationId) async {
    return await _jsonRequest(
      'POST',
      '/api/group-simulations/${Uri.encodeComponent(simulationId)}/run',
    ) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> fetchPersonaWorlds() async {
    final data = await _jsonRequest('GET', '/api/worlds') as List<dynamic>;
    return data.cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> fetchPersonaWorld(String worldId) async {
    return await _jsonRequest(
      'GET',
      '/api/worlds/${Uri.encodeComponent(worldId)}',
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createPersonaWorld({
    required String name,
    String? theme,
    String? background,
  }) async {
    return await _jsonRequest(
      'POST',
      '/api/worlds',
      body: {
        'name': name,
        if (theme != null) 'theme': theme,
        if (background != null) 'world_background': background,
      },
    ) as Map<String, dynamic>;
  }

  Future<void> deletePersonaWorld(String worldId) async {
    await _jsonRequest(
      'DELETE',
      '/api/worlds/${Uri.encodeComponent(worldId)}',
    );
  }

  Future<Map<String, dynamic>> createWorldPersona({
    required String worldId,
    required String name,
    required String summary,
    String? faction,
    List<String> traits = const [],
    List<String> motivations = const [],
    String? background,
  }) async {
    return await _jsonRequest(
      'POST',
      '/api/worlds/${Uri.encodeComponent(worldId)}/personas',
      body: {
        'name': name,
        'summary': summary,
        'traits': traits,
        'motivations': motivations,
        if (faction != null) 'faction': faction,
        if (background != null) 'background': background,
      },
    ) as Map<String, dynamic>;
  }

  Future<void> deleteWorldPersona(String worldId, String personaId) async {
    await _jsonRequest(
      'DELETE',
      '/api/worlds/${Uri.encodeComponent(worldId)}/personas/'
          '${Uri.encodeComponent(personaId)}',
    );
  }

  Future<Map<String, dynamic>> updateWorldPersona({
    required String worldId,
    required String personaId,
    required String name,
    required String summary,
    String? faction,
    List<String> traits = const [],
    List<String> motivations = const [],
    String? background,
  }) async {
    return await _jsonRequest(
      'PATCH',
      '/api/worlds/${Uri.encodeComponent(worldId)}/personas/'
          '${Uri.encodeComponent(personaId)}',
      body: {
        'name': name,
        'summary': summary,
        'traits': traits,
        'motivations': motivations,
        'faction': faction,
        'background': background,
      },
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createWorldRelationship({
    required String worldId,
    required String sourcePersonaId,
    required String targetPersonaId,
    required String relationshipType,
    double strength = 0.5,
  }) async {
    return await _jsonRequest(
      'POST',
      '/api/worlds/${Uri.encodeComponent(worldId)}/relationships',
      body: {
        'source_persona_id': sourcePersonaId,
        'target_persona_id': targetPersonaId,
        'relationship_type': relationshipType,
        'strength': strength,
      },
    ) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> fetchPersonaCatalog() async {
    final data =
        await _jsonRequest('GET', '/api/persona-catalog') as List<dynamic>;
    return data.cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> importPersonaCatalog({
    required String worldId,
    required String templateId,
    int limit = 20,
    List<String> factions = const [],
    List<String> corePersonaKeys = const [],
  }) async {
    return await _jsonRequest(
      'POST',
      '/api/worlds/${Uri.encodeComponent(worldId)}/import/catalog',
      body: {
        'template_id': templateId,
        'limit': limit,
        'factions': factions,
        'core_persona_keys': corePersonaKeys,
      },
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> searchWorldImport({
    required String query,
    int limit = 20,
    String provider = 'free_web',
  }) async {
    return await _jsonRequest(
      'POST',
      '/api/world-imports/search',
      body: {'query': query, 'limit': limit, 'provider': provider},
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchWorldImportTask(String taskId) async {
    return await _jsonRequest(
      'GET',
      '/api/world-imports/${Uri.encodeComponent(taskId)}',
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> resolveWorldImport({
    required String taskId,
    required String selectedOptionId,
  }) async {
    return await _jsonRequest(
      'POST',
      '/api/world-imports/${Uri.encodeComponent(taskId)}/resolve',
      body: {'selected_option_id': selectedOptionId},
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> generateWorldImportFallback({
    required String taskId,
    String mode = 'generate_missing',
    int? targetCount,
  }) async {
    return await _jsonRequest(
      'POST',
      '/api/world-imports/${Uri.encodeComponent(taskId)}/generate-fallback',
      body: {
        'mode': mode,
        if (targetCount != null) 'target_count': targetCount,
      },
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> confirmWorldImport({
    required String taskId,
    required String worldId,
    required List<String> candidateIds,
    List<int> relationshipIndexes = const [],
    String destination = 'append',
  }) async {
    return await _jsonRequest(
      'POST',
      '/api/world-imports/${Uri.encodeComponent(taskId)}/confirm',
      body: {
        'world_id': worldId,
        'destination': destination,
        'candidate_ids': candidateIds,
        'relationship_indexes': relationshipIndexes,
      },
    ) as Map<String, dynamic>;
  }

  Future<RelationshipGraph> fetchWorldGraph(String worldId) async {
    final data = await _jsonRequest(
      'GET',
      '/api/worlds/${Uri.encodeComponent(worldId)}/graph',
    ) as Map<String, dynamic>;
    return RelationshipGraph.fromJson(data);
  }

  Future<Map<String, dynamic>> runWorldSimulation({
    required String worldId,
    required String scenario,
    required List<String> participantIds,
    int rounds = 3,
  }) async {
    return await _jsonRequest(
      'POST',
      '/api/worlds/${Uri.encodeComponent(worldId)}/simulations',
      body: {
        'title': scenario.length > 60 ? scenario.substring(0, 60) : scenario,
        'scenario': scenario,
        'participant_ids': participantIds,
        'rounds': rounds,
      },
    ) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> fetchWorldSimulations(
      String worldId) async {
    final data = await _jsonRequest(
      'GET',
      '/api/worlds/${Uri.encodeComponent(worldId)}/simulations',
    ) as List<dynamic>;
    return data.cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> fetchWorldSimulation({
    required String worldId,
    required String simulationId,
  }) async {
    return await _jsonRequest(
      'GET',
      '/api/worlds/${Uri.encodeComponent(worldId)}/simulations/${Uri.encodeComponent(simulationId)}',
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> fetchWorldSimulationRound({
    required String worldId,
    required String simulationId,
    required int roundNumber,
  }) async {
    return await _jsonRequest(
      'GET',
      '/api/worlds/${Uri.encodeComponent(worldId)}/simulations/'
          '${Uri.encodeComponent(simulationId)}/rounds/$roundNumber',
    ) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> discardWorldImport({
    required String taskId,
    String? reason,
  }) async {
    return await _jsonRequest(
      'POST',
      '/api/world-imports/${Uri.encodeComponent(taskId)}/discard',
      body: {
        if (reason != null && reason.isNotEmpty) 'reason': reason,
      },
    ) as Map<String, dynamic>;
  }

  Future<dynamic> _jsonRequest(
    String method,
    String path, {
    Map<String, dynamic>? body,
    bool authenticated = true,
  }) {
    return _rawRequest(
      method,
      path,
      contentType: 'application/json; charset=utf-8',
      body: body == null ? null : utf8.encode(jsonEncode(body)),
      authenticated: authenticated,
    );
  }

  Future<dynamic> _rawRequest(
    String method,
    String path, {
    String? contentType,
    List<int>? body,
    bool authenticated = true,
  }) async {
    final client = _clientFactory()..connectionTimeout = _timeout;
    try {
      final request = await client
          .openUrl(method, Uri.parse('$baseUrl$path'))
          .timeout(_timeout);
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      if (contentType != null) {
        request.headers.set(HttpHeaders.contentTypeHeader, contentType);
      }
      if (authenticated) {
        final token = _token;
        if (token == null) {
          throw const ApiException(
            type: ApiErrorType.authentication,
            statusCode: 401,
            message: '登录状态已失效，请重新登录。',
          );
        }
        request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      }
      if (body != null) request.add(body);

      final response = await request.close().timeout(_timeout);
      final responseText =
          await response.transform(utf8.decoder).join().timeout(_timeout);
      dynamic data;
      try {
        data = responseText.isEmpty
            ? <String, dynamic>{}
            : jsonDecode(responseText);
      } on FormatException {
        data = responseText;
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw _responseException(response.statusCode, data, responseText);
      }
      return data;
    } on ApiException {
      rethrow;
    } on TimeoutException {
      throw const ApiException(
        type: ApiErrorType.timeout,
        statusCode: 408,
        message: '请求超时。请检查服务状态，或在设置中延长超时时间。',
      );
    } on SocketException {
      throw const ApiException(
        type: ApiErrorType.connection,
        statusCode: 503,
        message: '无法连接本地服务，请稍候重试。',
      );
    } on HandshakeException {
      throw const ApiException(
        type: ApiErrorType.connection,
        message: '安全连接失败，请检查系统时间和网络设置。',
      );
    } on FormatException {
      throw const ApiException(
        type: ApiErrorType.server,
        message: '服务返回了无法识别的数据。',
      );
    } catch (_) {
      throw const ApiException(
        type: ApiErrorType.unknown,
        message: '发生未知错误，请重试。',
      );
    } finally {
      client.close(force: true);
    }
  }

  Future<Map<String, dynamic>> _multipartFileRequest(
    String path, {
    required String filename,
    required Uint8List bytes,
    Map<String, String> fields = const {},
  }) async {
    final boundary = 'relationship-os-${DateTime.now().microsecondsSinceEpoch}';
    final builder = BytesBuilder();
    void writeText(String value) => builder.add(utf8.encode(value));
    for (final entry in fields.entries) {
      writeText('--$boundary\r\n');
      writeText(
        'Content-Disposition: form-data; name="${_escapeFormName(entry.key)}"'
        '\r\n\r\n',
      );
      writeText('${entry.value}\r\n');
    }
    writeText('--$boundary\r\n');
    writeText(
      'Content-Disposition: form-data; name="file"; '
      'filename="${_escapeFilename(filename)}"\r\n',
    );
    writeText('Content-Type: application/octet-stream\r\n\r\n');
    builder.add(bytes);
    writeText('\r\n--$boundary--\r\n');
    final data = await _rawRequest(
      'POST',
      path,
      contentType: 'multipart/form-data; boundary=$boundary',
      body: builder.takeBytes(),
    );
    return data as Map<String, dynamic>;
  }

  Future<Uint8List> _download(
    String path, {
    String method = 'GET',
    Map<String, dynamic>? jsonBody,
  }) async {
    final client = _clientFactory()..connectionTimeout = _timeout;
    try {
      final request = await client
          .openUrl(method, Uri.parse('$baseUrl$path'))
          .timeout(_timeout);
      final token = _token;
      if (token == null) {
        throw const ApiException(
          type: ApiErrorType.authentication,
          statusCode: 401,
          message: '登录状态已失效，请重新登录。',
        );
      }
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      if (jsonBody != null) {
        request.headers.contentType = ContentType.json;
        request.add(utf8.encode(jsonEncode(jsonBody)));
      }
      final response = await request.close().timeout(_timeout);
      final bytes = await response.fold<BytesBuilder>(
        BytesBuilder(),
        (builder, chunk) => builder..add(chunk),
      );
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final responseText = utf8.decode(bytes.toBytes(), allowMalformed: true);
        dynamic data;
        try {
          data = jsonDecode(responseText);
        } on FormatException {
          data = responseText;
        }
        throw _responseException(response.statusCode, data, responseText);
      }
      return bytes.takeBytes();
    } on TimeoutException {
      throw const ApiException(
        type: ApiErrorType.timeout,
        statusCode: 408,
        message: '下载超时，请稍后重试。',
      );
    } on SocketException {
      throw const ApiException(
        type: ApiErrorType.connection,
        statusCode: 503,
        message: '网络连接失败，无法连接本地服务。',
      );
    } on HandshakeException {
      throw const ApiException(
        type: ApiErrorType.connection,
        message: '网络安全连接失败，请检查系统时间和网络设置。',
      );
    } finally {
      client.close(force: true);
    }
  }

  ApiException _responseException(
    int statusCode,
    dynamic data,
    String responseText,
  ) {
    final rawDetail = data is Map<String, dynamic>
        ? data['detail'] ?? data['message'] ?? responseText
        : responseText;
    final rawDetailText = rawDetail.toString();
    final normalized = rawDetailText.toLowerCase();
    final type = _backupErrorType(statusCode, normalized);
    final detail = _localizedDetail(statusCode, rawDetailText, type: type);
    return ApiException(type: type, statusCode: statusCode, message: detail);
  }

  ApiErrorType _backupErrorType(int statusCode, String detail) {
    if (statusCode == 413) return ApiErrorType.payloadTooLarge;
    if (statusCode == 426 ||
        detail.contains('version') ||
        detail.contains('版本')) {
      return ApiErrorType.incompatibleVersion;
    }
    if (detail.contains('password') ||
        detail.contains('passphrase') ||
        detail.contains('密码')) {
      return ApiErrorType.invalidPassword;
    }
    if (detail.contains('backup') ||
        detail.contains('archive') ||
        detail.contains('zip') ||
        detail.contains('file') ||
        detail.contains('备份') ||
        detail.contains('文件')) {
      return ApiErrorType.invalidFile;
    }
    return switch (statusCode) {
      400 || 409 || 422 => ApiErrorType.validation,
      401 || 403 => ApiErrorType.authentication,
      404 => ApiErrorType.notFound,
      >= 500 => ApiErrorType.server,
      _ => ApiErrorType.unknown,
    };
  }

  String _localizedDetail(
    int statusCode,
    String detail, {
    required ApiErrorType type,
  }) {
    final normalized = detail.toLowerCase();
    if (type == ApiErrorType.invalidPassword) return '备份密码无效，请重新输入。';
    if (type == ApiErrorType.invalidFile) return '备份文件无效或已损坏。';
    if (type == ApiErrorType.payloadTooLarge) return '备份文件过大，无法处理。';
    if (type == ApiErrorType.incompatibleVersion) {
      return '备份版本不兼容，请升级应用或选择其他备份。';
    }
    if (statusCode == 401 || statusCode == 403) {
      return '账号或密码错误，或者登录状态已失效。';
    }
    if (normalized.contains('email already registered')) {
      return '该邮箱已注册，请直接登录。';
    }
    if (normalized.contains('no valid chat messages')) {
      return '文件中没有识别到有效聊天消息，请检查格式和发送者名称。';
    }
    if (statusCode >= 500) {
      return '本地服务暂时不可用，请稍候重试。';
    }
    return detail.isEmpty ? '请求失败，请检查输入后重试。' : detail;
  }

  String _escapeFilename(String filename) {
    return filename
        .replaceAll('"', '')
        .replaceAll('\r', '')
        .replaceAll('\n', '');
  }

  String _escapeFormName(String name) => _escapeFilename(name);
}
