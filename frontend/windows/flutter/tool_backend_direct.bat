@echo off
setlocal

cd /d "%PROJECT_DIR%"
if errorlevel 1 exit /b %ERRORLEVEL%

set "BUILD_MODE=%~2"
if /I "%BUILD_MODE%"=="Debug" set "BUILD_MODE=debug"
if /I "%BUILD_MODE%"=="Profile" set "BUILD_MODE=profile"
if /I "%BUILD_MODE%"=="Release" set "BUILD_MODE=release"

"%FLUTTER_ROOT%\bin\cache\dart-sdk\bin\dart.exe" ^
  "%FLUTTER_ROOT%\bin\cache\flutter_tools.snapshot" assemble ^
  --no-version-check ^
  --output="%PROJECT_DIR%\build" ^
  "-dTargetPlatform=%~1" ^
  "-dTrackWidgetCreation=%TRACK_WIDGET_CREATION%" ^
  "-dBuildMode=%BUILD_MODE%" ^
  "-dTargetFile=lib/main.dart" ^
  "-dTreeShakeIcons=%TREE_SHAKE_ICONS%" ^
  "-dDartObfuscation=%DART_OBFUSCATION%" ^
  "--DartDefines=%DART_DEFINES%" ^
  "%BUILD_MODE%_bundle_%~1_assets"

exit /b %ERRORLEVEL%
