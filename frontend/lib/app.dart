import 'package:flutter/material.dart';

import 'features/auth/auth_page.dart';
import 'features/home/home_page.dart';
import 'features/startup/startup_page.dart';
import 'services/api_service.dart';
import 'services/credential_store.dart';

enum _AppStage { starting, authentication, home }

class RelationshipOsApp extends StatefulWidget {
  const RelationshipOsApp({super.key});

  @override
  State<RelationshipOsApp> createState() => _RelationshipOsAppState();
}

class _RelationshipOsAppState extends State<RelationshipOsApp> {
  late final ApiService _apiService;
  late final CredentialStore _credentialStore;
  _AppStage _stage = _AppStage.starting;

  @override
  void initState() {
    super.initState();
    _apiService = ApiService(baseUrl: 'http://127.0.0.1:8000');
    _credentialStore = WindowsCredentialStore();
  }

  Future<void> _continueAfterStatus() async {
    final token = await _credentialStore.readToken();
    if (token == null) {
      if (mounted) setState(() => _stage = _AppStage.authentication);
      return;
    }
    _apiService.setToken(token);
    try {
      await _apiService.validateSession();
      if (mounted) setState(() => _stage = _AppStage.home);
    } on ApiException catch (error) {
      if (error.requiresLogin) {
        _apiService.clearToken();
        await _credentialStore.clearToken();
      }
      if (mounted) setState(() => _stage = _AppStage.authentication);
    }
  }

  Future<void> _authenticated(AuthTokens tokens) async {
    try {
      await _credentialStore.writeToken(tokens.accessToken);
    } catch (_) {
      // 登录仍然有效；安全存储失败时仅不支持下次自动恢复。
    }
    if (mounted) setState(() => _stage = _AppStage.home);
  }

  Future<void> _logout() async {
    _apiService.clearToken();
    await _credentialStore.clearToken();
    if (mounted) setState(() => _stage = _AppStage.authentication);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Relationship OS',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6750A4)),
        useMaterial3: true,
      ),
      home: switch (_stage) {
        _AppStage.starting => StartupPage(
            apiService: _apiService,
            onReady: _continueAfterStatus,
          ),
        _AppStage.authentication => AuthPage(
            apiService: _apiService,
            onAuthenticated: _authenticated,
          ),
        _AppStage.home => HomePage(
            apiService: _apiService,
            onLogout: _logout,
          ),
      },
    );
  }
}
