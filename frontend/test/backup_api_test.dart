import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:relationship_os/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('encrypted backup service', () {
    late HttpServer server;
    late ApiService api;

    setUp(() async {
      server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      api = ApiService(baseUrl: 'http://127.0.0.1:${server.port}')
        ..setToken('test-token');
    });

    tearDown(() => server.close(force: true));

    test('POSTs password and downloads binary backup', () async {
      final requestFuture = server.first;
      final downloadFuture = api.downloadBackup(password: 'long-password');
      final request = await requestFuture;
      expect(request.method, 'POST');
      expect(request.uri.path, '/api/data/backup');
      expect(request.headers.value(HttpHeaders.authorizationHeader),
          'Bearer test-token');
      expect(jsonDecode(await utf8.decoder.bind(request).join()), {
        'password': 'long-password',
      });
      request.response
        ..statusCode = HttpStatus.ok
        ..add([0, 1, 2, 255]);
      await request.response.close();
      expect(await downloadFuture, Uint8List.fromList([0, 1, 2, 255]));
    });

    test('adds password as a multipart restore field', () async {
      final requestFuture = server.first;
      final restoreFuture = api.restoreBackup(
        filename: 'backup.rosbackup',
        bytes: Uint8List.fromList([1, 2, 3]),
        password: 'restore-secret',
      );
      final request = await requestFuture;
      final body = latin1.decode(await request.fold<List<int>>(
        <int>[],
        (bytes, chunk) => bytes..addAll(chunk),
      ));
      expect(request.uri.path, '/api/data/restore');
      expect(body.contains('name="password"'), isTrue);
      expect(body.contains('restore-secret'), isTrue);
      expect(body.contains('filename="backup.rosbackup"'), isTrue);
      request.response
        ..statusCode = HttpStatus.ok
        ..write('{}');
      await request.response.close();
      await restoreFuture;
    });

    test('distinguishes backup errors', () async {
      final responses = <(int, String)>[
        (400, 'invalid password'),
        (400, 'invalid backup file'),
        (413, 'too large'),
        (426, 'unsupported version'),
      ];
      var responseIndex = 0;
      final subscription = server.listen((request) async {
        final (status, detail) = responses[responseIndex++];
        await utf8.decoder.bind(request).join();
        request.response
          ..statusCode = status
          ..headers.contentType = ContentType.json
          ..write(jsonEncode({'detail': detail}));
        await request.response.close();
      });

      Future<ApiException> requestError() async {
        final call = api.downloadBackup(password: 'long-password');
        try {
          await call;
        } on ApiException catch (error) {
          return error;
        }
        throw StateError('request should have failed');
      }

      try {
        expect((await requestError()).type, ApiErrorType.invalidPassword);
        expect((await requestError()).type, ApiErrorType.invalidFile);
        expect((await requestError()).type, ApiErrorType.payloadTooLarge);
        expect((await requestError()).type, ApiErrorType.incompatibleVersion);
      } finally {
        await subscription.cancel();
      }
    });
  });
}
