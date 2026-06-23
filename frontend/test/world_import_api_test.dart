import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:relationship_os/services/api_service.dart';

void main() {
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
}
