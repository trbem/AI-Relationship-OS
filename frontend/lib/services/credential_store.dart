import 'dart:convert';
import 'dart:io';

abstract interface class CredentialStore {
  Future<String?> readToken();
  Future<void> writeToken(String token);
  Future<void> clearToken();
}

class WindowsCredentialStore implements CredentialStore {
  WindowsCredentialStore({String target = 'RelationshipOS/session'})
      : _target = target;

  final String _target;

  @override
  Future<String?> readToken() async {
    final result = await _run('read');
    if (result.exitCode != 0) {
      throw FileSystemException(
        '无法读取 Windows 登录凭据。',
        (result.stderr as String).trim(),
      );
    }
    final value = (result.stdout as String).trim();
    return value.isEmpty ? null : value;
  }

  @override
  Future<void> writeToken(String token) async {
    final result = await _run('write', base64Encode(utf8.encode(token)));
    if (result.exitCode != 0) {
      throw const FileSystemException('无法保存 Windows 登录凭据。');
    }
  }

  @override
  Future<void> clearToken() async {
    await _run('delete');
  }

  Future<ProcessResult> _run(String action, [String value = '']) {
    return Process.run(
      'powershell.exe',
      [
        '-NoProfile',
        '-NonInteractive',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        _script,
      ],
      environment: {
        ...Platform.environment,
        'RELATIONSHIP_CRED_ACTION': action,
        'RELATIONSHIP_CRED_TARGET': _target,
        'RELATIONSHIP_CRED_VALUE': value,
      },
      stdoutEncoding: systemEncoding,
      stderrEncoding: systemEncoding,
    );
  }

  static const _script = r'''
& {
$ErrorActionPreference = 'Stop'
$action = $env:RELATIONSHIP_CRED_ACTION
$target = $env:RELATIONSHIP_CRED_TARGET
$value = $env:RELATIONSHIP_CRED_VALUE
Add-Type @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class RelationshipCredential {
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
  public struct CREDENTIAL {
    public UInt32 Flags, Type;
    public string TargetName, Comment;
    public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
    public UInt32 CredentialBlobSize;
    public IntPtr CredentialBlob;
    public UInt32 Persist, AttributeCount;
    public IntPtr Attributes;
    public string TargetAlias, UserName;
  }
  [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  static extern bool CredWrite(ref CREDENTIAL credential, UInt32 flags);
  [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  static extern bool CredRead(string target, UInt32 type, UInt32 flags, out IntPtr credential);
  [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
  static extern bool CredDelete(string target, UInt32 type, UInt32 flags);
  [DllImport("advapi32.dll")]
  static extern void CredFree(IntPtr buffer);
  public static void Write(string target, string secret) {
    byte[] bytes = Encoding.UTF8.GetBytes(secret);
    IntPtr blob = Marshal.AllocCoTaskMem(bytes.Length);
    Marshal.Copy(bytes, 0, blob, bytes.Length);
    try {
      var c = new CREDENTIAL { Type=1, TargetName=target, CredentialBlobSize=(UInt32)bytes.Length,
        CredentialBlob=blob, Persist=2, UserName=Environment.UserName };
      if (!CredWrite(ref c, 0)) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
    } finally { Marshal.FreeCoTaskMem(blob); }
  }
  public static string Read(string target) {
    IntPtr ptr;
    if (!CredRead(target, 1, 0, out ptr)) return "";
    try {
      var c = (CREDENTIAL)Marshal.PtrToStructure(ptr, typeof(CREDENTIAL));
      byte[] bytes = new byte[c.CredentialBlobSize];
      Marshal.Copy(c.CredentialBlob, bytes, 0, bytes.Length);
      return Encoding.UTF8.GetString(bytes);
    } finally { CredFree(ptr); }
  }
  public static void Delete(string target) { CredDelete(target, 1, 0); }
}
'@
switch ($action) {
  'write' { [RelationshipCredential]::Write($target, [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($value))) }
  'read' { [Console]::OutputEncoding=[Text.Encoding]::UTF8; [Console]::Write([RelationshipCredential]::Read($target)) }
  'delete' { [RelationshipCredential]::Delete($target) }
}
}
''';
}
