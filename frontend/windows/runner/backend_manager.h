#ifndef RUNNER_BACKEND_MANAGER_H_
#define RUNNER_BACKEND_MANAGER_H_

#include <windows.h>

#include <string>

class BackendManager {
 public:
  BackendManager();
  ~BackendManager();

  BackendManager(const BackendManager&) = delete;
  BackendManager& operator=(const BackendManager&) = delete;

  // Ensures the local backend is healthy. If it is not already running, starts
  // the packaged backend and waits up to |timeout_ms| for /health.
  bool EnsureRunning(DWORD timeout_ms, std::wstring* error_message);

  // Stops only the backend process started by this instance.
  void Stop();

 private:
  bool IsHealthy() const;
  bool Start(std::wstring* error_message);
  std::wstring GetBackendPath() const;

  HANDLE job_handle_ = nullptr;
  HANDLE process_handle_ = nullptr;
};

#endif  // RUNNER_BACKEND_MANAGER_H_
