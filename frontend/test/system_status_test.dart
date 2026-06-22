import 'package:flutter_test/flutter_test.dart';
import 'package:relationship_os/models/system_status.dart';

void main() {
  test('parses nested service states and allows startup', () {
    final status = SystemStatus.fromJson({
      'backend': {'status': 'ok'},
      'database': {'ready': true},
      'ai': {'status': 'configured', 'message': 'MiMo'},
      'initialized': true,
      'version': '1.0.0',
    });

    expect(status.backendReady, isTrue);
    expect(status.databaseReady, isTrue);
    expect(status.aiReady, isTrue);
    expect(status.canContinue, isTrue);
    expect(status.version, '1.0.0');
  });

  test('AI configuration is optional for local startup', () {
    final status = SystemStatus.fromJson({
      'backend': 'ok',
      'database': 'ready',
      'ai': 'unconfigured',
      'initialized': true,
    });

    expect(status.aiReady, isFalse);
    expect(status.canContinue, isTrue);
  });
}
