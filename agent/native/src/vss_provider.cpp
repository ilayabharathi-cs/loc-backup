#include "../include/vss_provider.h"

#include <windows.h>
#include <shlobj.h>
#include <string>
#include <regex>
#include <vector>

namespace {

struct ScopedHandle {
    HANDLE h;
    explicit ScopedHandle(HANDLE handle) : h(handle) {}
    ~ScopedHandle() {
        if (h != INVALID_HANDLE_VALUE && h != NULL) {
            CloseHandle(h);
        }
    }
};

// Execute process safely without shell (cmd.exe) and capture output with timeout
bool ExecuteProcessCapture(
    const std::wstring& cmdline,
    DWORD timeout_ms,
    std::wstring& out_stdout,
    DWORD& out_exit_code
) {
    out_stdout.clear();
    out_exit_code = 1;

    HANDLE hReadPipe = NULL;
    HANDLE hWritePipe = NULL;
    SECURITY_ATTRIBUTES sa = {0};
    sa.nLength = sizeof(sa);
    sa.bInheritHandle = TRUE;

    if (!CreatePipe(&hReadPipe, &hWritePipe, &sa, 0)) {
        return false;
    }
    SetHandleInformation(hReadPipe, HANDLE_FLAG_INHERIT, 0);

    ScopedHandle scopedRead(hReadPipe);
    ScopedHandle scopedWrite(hWritePipe);

    STARTUPINFOW si = {0};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
    si.hStdOutput = hWritePipe;
    si.hStdError = hWritePipe;
    si.wShowWindow = SW_HIDE;

    PROCESS_INFORMATION pi = {0};
    std::vector<wchar_t> cmd_buf(cmdline.begin(), cmdline.end());
    cmd_buf.push_back(L'\0');

    if (!CreateProcessW(
        NULL,
        cmd_buf.data(),
        NULL,
        NULL,
        TRUE,
        CREATE_NO_WINDOW,
        NULL,
        NULL,
        &si,
        &pi
    )) {
        return false;
    }

    ScopedHandle procScoped(pi.hProcess);
    ScopedHandle threadScoped(pi.hThread);

    // Close write end in parent process so ReadFile terminates on child exit
    CloseHandle(scopedWrite.h);
    scopedWrite.h = INVALID_HANDLE_VALUE;

    DWORD waitRes = WaitForSingleObject(pi.hProcess, timeout_ms);
    if (waitRes == WAIT_TIMEOUT) {
        TerminateProcess(pi.hProcess, 1);
        return false;
    }

    GetExitCodeProcess(pi.hProcess, &out_exit_code);

    // Read pipe output
    std::string raw_out;
    char buffer[4096];
    DWORD bytesRead = 0;
    while (ReadFile(scopedRead.h, buffer, sizeof(buffer) - 1, &bytesRead, NULL) && bytesRead > 0) {
        buffer[bytesRead] = '\0';
        raw_out.append(buffer, bytesRead);
    }

    // Convert to wide string
    if (!raw_out.empty()) {
        int wlen = MultiByteToWideChar(CP_OEMCP, 0, raw_out.c_str(), -1, NULL, 0);
        if (wlen > 0) {
            std::vector<wchar_t> wbuf(wlen);
            MultiByteToWideChar(CP_OEMCP, 0, raw_out.c_str(), -1, wbuf.data(), wlen);
            out_stdout = wbuf.data();
        }
    }

    return true;
}

} // namespace

int rv_vss_is_admin(void) {
    return IsUserAnAdmin() ? 1 : 0;
}

int rv_vss_resolve_path(
    const wchar_t* snapshot_device,
    const wchar_t* relative_path,
    wchar_t* out_mapped_path,
    int max_mapped_len
) {
    if (!snapshot_device || !relative_path || !out_mapped_path || max_mapped_len <= 0) {
        return -1;
    }

    std::wstring dev = snapshot_device;
    while (!dev.empty() && (dev.back() == L'\\' || dev.back() == L'/')) {
        dev.pop_back();
    }

    std::wstring rel = relative_path;
    size_t start = 0;
    while (start < rel.size() && (rel[start] == L'\\' || rel[start] == L'/')) {
        start++;
    }
    std::wstring clean_rel = rel.substr(start);

    std::wstring full = dev + L"\\" + clean_rel;
    wcsncpy(out_mapped_path, full.c_str(), max_mapped_len - 1);
    out_mapped_path[max_mapped_len - 1] = L'\0';
    return 0;
}

int rv_vss_create_snapshot(
    const wchar_t* volume_letter,
    wchar_t* out_device,
    int max_device_len,
    wchar_t* out_id,
    int max_id_len,
    wchar_t* out_error,
    int max_error_len
) {
    if (!volume_letter || !out_device || !out_id) return RV_VSS_FAILED;

    if (!IsUserAnAdmin()) {
        if (out_error && max_error_len > 0) {
            wcsncpy(out_error, L"VSS requires elevated Administrator privileges", max_error_len - 1);
            out_error[max_error_len - 1] = L'\0';
        }
        return RV_VSS_NOT_ADMIN;
    }

    std::wstring vol = volume_letter;
    while (!vol.empty() && (vol.back() == L'\\' || vol.back() == L'/')) {
        vol.pop_back();
    }
    if (vol.size() == 1) {
        vol += L":";
    }

    std::wstring cmd = L"vssadmin create shadow /for=" + vol + L"\\";
    std::wstring output;
    DWORD exit_code = 1;

    bool ok = ExecuteProcessCapture(cmd, 60000, output, exit_code);
    if (!ok) {
        if (out_error && max_error_len > 0) {
            wcsncpy(out_error, L"VSS creation timed out or failed to execute vssadmin", max_error_len - 1);
            out_error[max_error_len - 1] = L'\0';
        }
        return RV_VSS_TIMEOUT;
    }

    if (exit_code != 0) {
        if (out_error && max_error_len > 0) {
            _snwprintf(out_error, max_error_len - 1, L"vssadmin exited with code %lu: %s", exit_code, output.c_str());
            out_error[max_error_len - 1] = L'\0';
        }
        return RV_VSS_FAILED;
    }

    // Parse output for Shadow Copy Volume Name: \\?\GLOBALROOT\Device\HarddiskVolumeShadowCopyX
    std::wregex vol_regex(LR"(Shadow Copy Volume Name:\s*([^\r\n]+))", std::regex_constants::icase);
    std::wregex id_regex(LR"(Shadow Copy ID:\s*([^\r\n]+))", std::regex_constants::icase);

    std::wsmatch match;
    bool found_vol = false;
    if (std::regex_search(output, match, vol_regex) && match.size() > 1) {
        std::wstring dev = match[1].str();
        // trim whitespace
        size_t first = dev.find_first_not_of(L" \t\r\n");
        size_t last = dev.find_last_not_of(L" \t\r\n");
        if (first != std::wstring::npos && last != std::wstring::npos) {
            dev = dev.substr(first, last - first + 1);
        }
        wcsncpy(out_device, dev.c_str(), max_device_len - 1);
        out_device[max_device_len - 1] = L'\0';
        found_vol = true;
    }

    if (std::regex_search(output, match, id_regex) && match.size() > 1) {
        std::wstring sid = match[1].str();
        size_t first = sid.find_first_not_of(L" \t\r\n");
        size_t last = sid.find_last_not_of(L" \t\r\n");
        if (first != std::wstring::npos && last != std::wstring::npos) {
            sid = sid.substr(first, last - first + 1);
        }
        wcsncpy(out_id, sid.c_str(), max_id_len - 1);
        out_id[max_id_len - 1] = L'\0';
    }

    if (!found_vol) {
        if (out_error && max_error_len > 0) {
            wcsncpy(out_error, L"Failed to parse Shadow Copy Volume Name from vssadmin output", max_error_len - 1);
            out_error[max_error_len - 1] = L'\0';
        }
        return RV_VSS_FAILED;
    }

    return RV_VSS_OK;
}

int rv_vss_delete_snapshot(
    const wchar_t* snapshot_id,
    wchar_t* out_error,
    int max_error_len
) {
    if (!snapshot_id) return RV_VSS_FAILED;

    std::wstring sid = snapshot_id;
    std::wstring cmd = L"vssadmin delete shadows /shadow=" + sid + L" /quiet";
    std::wstring output;
    DWORD exit_code = 1;

    bool ok = ExecuteProcessCapture(cmd, 30000, output, exit_code);
    if (!ok || exit_code != 0) {
        if (out_error && max_error_len > 0) {
            _snwprintf(out_error, max_error_len - 1, L"vssadmin delete shadows failed with code %lu", exit_code);
            out_error[max_error_len - 1] = L'\0';
        }
        return RV_VSS_FAILED;
    }

    return RV_VSS_OK;
}
