import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:relationship_os/services/api_service.dart';

void main() {
  test('searchWorldImport posts provider and language', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final api = ApiService(baseUrl: 'http://127.0.0.1:${server.port}')
      ..setToken('test-token');

    try {
      final requestFuture = server.first;
      final searchFuture = api.searchWorldImport(
        query: '三国演义',
        limit: 20,
        provider: 'free_web',
        language: 'zh',
      );
      final request = await requestFuture;
      expect(request.method, 'POST');
      expect(request.uri.path, '/api/world-imports/search');
      expect(
        request.headers.value(HttpHeaders.authorizationHeader),
        'Bearer test-token',
      );
      expect(jsonDecode(await utf8.decoder.bind(request).join()), {
        'query': '三国演义',
        'limit': 20,
        'provider': 'free_web',
        'language': 'zh',
      });
      request.response
        ..statusCode = HttpStatus.accepted
        ..headers.contentType = ContentType.json
        ..write(jsonEncode({'id': 'task-1', 'status': 'queued'}));
      await request.response.close();

      expect(await searchFuture, {'id': 'task-1', 'status': 'queued'});
    } finally {
      await server.close(force: true);
    }
  });

  test('resolveWorldImport posts selected disambiguation option', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final api = ApiService(baseUrl: 'http://127.0.0.1:${server.port}')
      ..setToken('test-token');

    try {
      final requestFuture = server.first;
      final resolveFuture = api.resolveWorldImport(
        taskId: 'task/with space',
        selectedOptionId: 'sanguoyanyi-novel',
      );
      final request = await requestFuture;
      expect(request.method, 'POST');
      expect(
        request.uri.path,
        '/api/world-imports/task%2Fwith%20space/resolve',
      );
      expect(
        request.headers.value(HttpHeaders.authorizationHeader),
        'Bearer test-token',
      );
      expect(jsonDecode(await utf8.decoder.bind(request).join()), {
        'selected_option_id': 'sanguoyanyi-novel',
      });
      request.response
        ..statusCode = HttpStatus.accepted
        ..headers.contentType = ContentType.json
        ..write(jsonEncode({'id': 'task/with space', 'status': 'queued'}));
      await request.response.close();

      expect(
          await resolveFuture, {'id': 'task/with space', 'status': 'queued'});
    } finally {
      await server.close(force: true);
    }
  });

  test('cancelWorldImport posts cancel request', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final api = ApiService(baseUrl: 'http://127.0.0.1:${server.port}')
      ..setToken('test-token');

    try {
      final requestFuture = server.first;
      final cancelFuture = api.cancelWorldImport(taskId: 'task-1');
      final request = await requestFuture;
      expect(request.method, 'POST');
      expect(request.uri.path, '/api/world-imports/task-1/cancel');
      expect(
        request.headers.value(HttpHeaders.authorizationHeader),
        'Bearer test-token',
      );
      request.response
        ..statusCode = HttpStatus.ok
        ..headers.contentType = ContentType.json
        ..write(jsonEncode({'id': 'task-1', 'status': 'discarded'}));
      await request.response.close();

      expect(await cancelFuture, {'id': 'task-1', 'status': 'discarded'});
    } finally {
      await server.close(force: true);
    }
  });

  test('retryWorldImport posts retry request', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final api = ApiService(baseUrl: 'http://127.0.0.1:${server.port}')
      ..setToken('test-token');

    try {
      final requestFuture = server.first;
      final retryFuture = api.retryWorldImport(taskId: 'task-1');
      final request = await requestFuture;
      expect(request.method, 'POST');
      expect(request.uri.path, '/api/world-imports/task-1/retry');
      expect(
        request.headers.value(HttpHeaders.authorizationHeader),
        'Bearer test-token',
      );
      request.response
        ..statusCode = HttpStatus.accepted
        ..headers.contentType = ContentType.json
        ..write(jsonEncode({'id': 'task-1', 'status': 'queued'}));
      await request.response.close();

      expect(await retryFuture, {'id': 'task-1', 'status': 'queued'});
    } finally {
      await server.close(force: true);
    }
  });
}
