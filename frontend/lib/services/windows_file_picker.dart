import 'dart:convert';
import 'dart:io';

class SelectedFile {
  const SelectedFile({required this.path, required this.name});

  final String path;
  final String name;
}

class WindowsFilePicker {
  const WindowsFilePicker();

  Future<SelectedFile?> pickChatFile() async {
    final script = r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = '选择聊天记录'
$dialog.Filter = '可导入文件 (*.txt;*.csv;*.json;*.md;*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.pdf)|*.txt;*.csv;*.json;*.md;*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.pdf|所有文件 (*.*)|*.*'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  [Console]::OutputEncoding = [Text.Encoding]::UTF8
  [Console]::Write($dialog.FileName)
}
''';
    final result = await Process.run(
      'powershell.exe',
      [
        '-NoProfile',
        '-STA',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        script,
      ],
      stdoutEncoding: utf8,
      stderrEncoding: utf8,
    );
    if (result.exitCode != 0) {
      throw const FileSystemException('无法打开系统文件选择器');
    }
    final path = (result.stdout as String).trim();
    if (path.isEmpty) return null;
    return SelectedFile(path: path, name: File(path).uri.pathSegments.last);
  }

  Future<SelectedFile?> pickBackupFile() {
    return _pickFile(
      title: '选择 Relationship OS 备份',
      filter: 'ZIP 备份 (*.zip)|*.zip',
    );
  }

  Future<String?> pickDirectory() async {
    final script = r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '选择 Relationship OS 数据目录'
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  [Console]::OutputEncoding = [Text.Encoding]::UTF8
  [Console]::Write($dialog.SelectedPath)
}
''';
    final result = await _run(script);
    if (result.exitCode != 0) {
      throw const FileSystemException('无法打开系统目录选择器。');
    }
    final path = (result.stdout as String).trim();
    return path.isEmpty ? null : path;
  }

  Future<String?> pickSavePath({
    required String filename,
    required String filter,
  }) async {
    final script = r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.SaveFileDialog
$dialog.FileName = $env:RELATIONSHIP_DIALOG_FILENAME
$dialog.Filter = $env:RELATIONSHIP_DIALOG_FILTER
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  [Console]::OutputEncoding = [Text.Encoding]::UTF8
  [Console]::Write($dialog.FileName)
}
''';
    final result = await _run(
      script,
      {
        'RELATIONSHIP_DIALOG_FILENAME': filename,
        'RELATIONSHIP_DIALOG_FILTER': filter,
      },
    );
    if (result.exitCode != 0) {
      throw const FileSystemException('无法打开系统保存对话框。');
    }
    final path = (result.stdout as String).trim();
    return path.isEmpty ? null : path;
  }

  Future<SelectedFile?> _pickFile({
    required String title,
    required String filter,
  }) async {
    final script = r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = $env:RELATIONSHIP_DIALOG_TITLE
$dialog.Filter = $env:RELATIONSHIP_DIALOG_FILTER
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
  [Console]::OutputEncoding = [Text.Encoding]::UTF8
  [Console]::Write($dialog.FileName)
}
''';
    final result = await _run(
      script,
      {
        'RELATIONSHIP_DIALOG_TITLE': title,
        'RELATIONSHIP_DIALOG_FILTER': filter,
      },
    );
    if (result.exitCode != 0) {
      throw const FileSystemException('无法打开系统文件选择器。');
    }
    final path = (result.stdout as String).trim();
    if (path.isEmpty) return null;
    return SelectedFile(path: path, name: File(path).uri.pathSegments.last);
  }

  Future<ProcessResult> _run(
    String script, [
    Map<String, String> environment = const {},
  ]) {
    return Process.run(
      'powershell.exe',
      [
        '-NoProfile',
        '-STA',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        script,
      ],
      environment: {...Platform.environment, ...environment},
      stdoutEncoding: utf8,
      stderrEncoding: utf8,
    );
  }
}
