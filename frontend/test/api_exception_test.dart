import 'package:flutter_test/flutter_test.dart';
import 'package:relationship_os/services/api_service.dart';

void main() {
  test('authentication errors request a new login', () {
    const error = ApiException(
      type: ApiErrorType.authentication,
      statusCode: 401,
      message: '登录状态已失效，请重新登录。',
    );

    expect(error.requiresLogin, isTrue);
    expect(error.toString(), '登录状态已失效，请重新登录。');
  });
}
