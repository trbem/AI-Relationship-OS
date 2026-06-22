import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:relationship_os/features/settings/settings_page.dart';
import 'package:relationship_os/models/app_settings.dart';
import 'package:relationship_os/services/api_service.dart';
import 'package:relationship_os/services/windows_file_picker.dart';

void main() {
  group('encrypted backup widgets', () {
    testWidgets('requires a 10 character matching backup password',
        (tester) async {
      final picker = _FakeFilePicker();
      await tester.pumpWidget(_settingsApp(picker));
      await tester.pumpAndSettle();
      await tester.dragUntilVisible(
        find.text('创建备份'),
        find.byType(ListView),
        const Offset(0, -500),
      );
      await tester.tap(find.text('创建备份'));
      await tester.pumpAndSettle();

      expect(find.text('密码仅用于本次备份，不会被记录或保存。'), findsOneWidget);
      final dialogFields = find.descendant(
        of: find.byType(AlertDialog),
        matching: find.byType(TextField),
      );
      await tester.enterText(dialogFields.at(0), 'short');
      await tester.enterText(dialogFields.at(1), 'short');
      await tester.tap(find.text('继续'));
      await tester.pump();
      expect(find.text('密码至少需要 10 个字符。'), findsOneWidget);

      await tester.enterText(dialogFields.at(0), 'long-password');
      await tester.enterText(dialogFields.at(1), 'different-one');
      await tester.tap(find.text('继续'));
      await tester.pump();
      expect(find.text('两次输入的密码不一致。'), findsOneWidget);
    });

    testWidgets('prompts for rosbackup password and warns for legacy zip',
        (tester) async {
      final picker = _FakeFilePicker(
        selected: const SelectedFile(path: 'ignored', name: 'backup.rosbackup'),
      );
      await tester.pumpWidget(_settingsApp(picker));
      await tester.pumpAndSettle();
      await tester.dragUntilVisible(
        find.text('恢复备份'),
        find.byType(ListView),
        const Offset(0, -500),
      );
      await tester.tap(find.text('恢复备份'));
      await tester.pumpAndSettle();
      expect(find.text('备份密码'), findsOneWidget);
      await tester.tap(find.text('取消'));
      await tester.pumpAndSettle();

      picker.selected =
          const SelectedFile(path: 'ignored', name: 'legacy-backup.zip');
      await tester.dragUntilVisible(
        find.text('恢复备份'),
        find.byType(ListView),
        const Offset(0, -500),
      );
      await tester.tap(find.text('恢复备份'));
      await tester.pumpAndSettle();
      expect(find.text('警告：这是旧版未加密 ZIP 备份。'), findsOneWidget);
    });
  });
}

Widget _settingsApp(WindowsFilePicker picker) => MaterialApp(
      home: SettingsPage(
        apiService: _FakeApiService(),
        filePicker: picker,
        onLogout: () async {},
      ),
    );

class _FakeApiService extends ApiService {
  _FakeApiService() : super(baseUrl: 'http://unused');

  @override
  Future<AppSettings> fetchSettings() async => const AppSettings(
        baseUrl: 'http://unused',
        model: 'test-model',
        timeoutSeconds: 120,
      );
}

class _FakeFilePicker extends WindowsFilePicker {
  _FakeFilePicker({this.selected});

  SelectedFile? selected;

  @override
  Future<SelectedFile?> pickBackupFile() async => selected;

  @override
  Future<String?> pickSavePath({
    required String filename,
    required String filter,
  }) async =>
      null;
}
