import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:relationship_os/services/credential_store.dart';

void main() {
  test(
    'stores the session in Windows Credential Manager',
    () async {
      final target =
          'RelationshipOS/test-${DateTime.now().microsecondsSinceEpoch}';
      final store = WindowsCredentialStore(target: target);
      addTearDown(store.clearToken);

      await store.writeToken('test-token');
      expect(await store.readToken(), 'test-token');
      await store.clearToken();
      expect(await store.readToken(), isNull);
    },
    skip: !Platform.isWindows,
  );
}
