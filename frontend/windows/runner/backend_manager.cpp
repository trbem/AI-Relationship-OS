#include "backend_manager.h"

#include <winhttp.h>

#include <chrono>
#include <filesystem>
#include <sstream>
#include <thread>
#include <vector>

namespace {

constexpr wchar_t kBackendHost[] = L"127.0.0.1";
constexpr INTERNET_PORT kBackendPort = 8000;
constexpr wchar_t kHealthPath[] = L"/health";

std::wstring FormatWindowsError(DWORD error) {
  wchar_t* buffer = nullptr;
  const DWORD size = FormatMessageW(
      FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
          FORMAT_MESSAGE_IGNORE_INSERTS,
      nullptr, error, MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
      reinterpret_cast<wchar_t*>(&buffer), 0, nullptr);
  std::wstring message =
      size > 0 && buffer != nullptr ? std::wstring(buffer, size)
                                    : L"Windows error " + std::to_wstring(error);
  if (buffer != nullptr) {
    LocalFree(buffer);
  }
  return message;
}

}  // namespace

BackendManager::BackendManager() = default;

BackendManager::~BackendManager() {
  Stop();
}

bool BackendManager::EnsureRunning(DWORD timeout_ms,
                                   std::wstring* error_message) {
  if (IsHealthy()) {
    return true;
  }

  if (!Start(error_message)) {
    return false;
  }

  const auto deadline = std::chrono::steady_clock::now() +
                        std::chrono::milliseconds(timeout_ms);
  while (std::chrono::steady_clock::now() < deadline) {
    if (IsHealthy()) {
      return true;
    }

    if (WaitForSingleObject(process_handle_, 0) == WAIT_OBJECT_0) {
      DWORD exit_code = 0;
      GetExitCodeProcess(process_handle_, &exit_code);
      if (error_message != nullptr) {
        *error_message = L"后端进程提前退出，退出码：" +
                         std::to_wstring(exit_code) +
                         L"。请检查 %LOCALAPPDATA%\\RelationshipOS\\logs。";
      }
      return false;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(250));
  }

  if (error_message != nullptr) {
    *error_message =
        L"后端启动超时。请确认 8000 端口未被占用，并检查本地日志。";
  }
  return false;
}

void BackendManager::Stop() {
  if (job_handle_ != nullptr) {
    TerminateJobObject(job_handle_, 0);
    CloseHandle(job_handle_);
    job_handle_ = nullptr;
  }
  if (process_handle_ != nullptr) {
    CloseHandle(process_handle_);
    process_handle_ = nullptr;
  }
}

bool BackendManager::IsHealthy() const {
  HINTERNET session = WinHttpOpen(
      L"RelationshipOS/1.0", WINHTTP_ACCESS_TYPE_NO_PROXY,
      WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
  if (session == nullptr) {
    return false;
  }

  WinHttpSetTimeouts(session, 1000, 1000, 1000, 1000);
  HINTERNET connection =
      WinHttpConnect(session, kBackendHost, kBackendPort, 0);
  HINTERNET request = connection == nullptr
                          ? nullptr
                          : WinHttpOpenRequest(
                                connection, L"GET", kHealthPath, nullptr,
                                WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES,
                                WINHTTP_FLAG_ESCAPE_DISABLE);

  bool healthy = false;
  if (request != nullptr &&
      WinHttpSendRequest(request, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
                         WINHTTP_NO_REQUEST_DATA, 0, 0, 0) &&
      WinHttpReceiveResponse(request, nullptr)) {
    DWORD status_code = 0;
    DWORD status_size = sizeof(status_code);
    if (WinHttpQueryHeaders(
            request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
            WINHTTP_HEADER_NAME_BY_INDEX, &status_code, &status_size,
            WINHTTP_NO_HEADER_INDEX)) {
      healthy = status_code >= 200 && status_code < 300;
    }
  }

  if (request != nullptr) {
    WinHttpCloseHandle(request);
  }
  if (connection != nullptr) {
    WinHttpCloseHandle(connection);
  }
  WinHttpCloseHandle(session);
  return healthy;
}

bool BackendManager::Start(std::wstring* error_message) {
  const std::wstring backend_path = GetBackendPath();
  if (!std::filesystem::exists(backend_path)) {
    if (error_message != nullptr) {
      *error_message =
          L"未找到后端程序：\n" + backend_path +
          L"\n\n请重新安装 Relationship OS，或检查安装目录是否完整。";
    }
    return false;
  }

  job_handle_ = CreateJobObjectW(nullptr, nullptr);
  if (job_handle_ == nullptr) {
    if (error_message != nullptr) {
      *error_message = L"无法创建后端进程组：" +
                       FormatWindowsError(GetLastError());
    }
    return false;
  }

  JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
  limits.BasicLimitInformation.LimitFlags =
      JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
  if (!SetInformationJobObject(job_handle_,
                               JobObjectExtendedLimitInformation, &limits,
                               sizeof(limits))) {
    if (error_message != nullptr) {
      *error_message = L"无法配置后端进程组：" +
                       FormatWindowsError(GetLastError());
    }
    Stop();
    return false;
  }

  const std::filesystem::path backend_directory =
      std::filesystem::path(backend_path).parent_path();
  std::wstring command_line = L"\"" + backend_path + L"\"";
  std::vector<wchar_t> mutable_command(command_line.begin(),
                                       command_line.end());
  mutable_command.push_back(L'\0');

  STARTUPINFOW startup_info{};
  startup_info.cb = sizeof(startup_info);
  PROCESS_INFORMATION process_info{};
  const DWORD creation_flags =
      CREATE_NO_WINDOW | CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT;
  if (!CreateProcessW(
          backend_path.c_str(), mutable_command.data(), nullptr, nullptr, FALSE,
          creation_flags, nullptr, backend_directory.c_str(), &startup_info,
          &process_info)) {
    if (error_message != nullptr) {
      *error_message =
          L"无法启动后端：" + FormatWindowsError(GetLastError());
    }
    Stop();
    return false;
  }

  if (!AssignProcessToJobObject(job_handle_, process_info.hProcess)) {
    const DWORD error = GetLastError();
    TerminateProcess(process_info.hProcess, error);
    CloseHandle(process_info.hThread);
    CloseHandle(process_info.hProcess);
    if (error_message != nullptr) {
      *error_message =
          L"无法管理后端进程：" + FormatWindowsError(error);
    }
    Stop();
    return false;
  }

  process_handle_ = process_info.hProcess;
  ResumeThread(process_info.hThread);
  CloseHandle(process_info.hThread);
  return true;
}

std::wstring BackendManager::GetBackendPath() const {
  std::vector<wchar_t> path(MAX_PATH);
  DWORD length = 0;
  while (true) {
    length = GetModuleFileNameW(nullptr, path.data(),
                                static_cast<DWORD>(path.size()));
    if (length == 0) {
      return L"backend\\relationship_os_backend.exe";
    }
    if (length < path.size() - 1) {
      break;
    }
    path.resize(path.size() * 2);
  }

  const std::filesystem::path executable(path.data());
  return (executable.parent_path() / L"backend" /
          L"relationship_os_backend.exe")
      .wstring();
}
