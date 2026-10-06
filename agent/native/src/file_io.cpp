#include "../include/file_io.h"

#include <windows.h>
#include <cmath>

namespace {

inline double FileTimeToUnixTime(const FILETIME& ft) {
    ULARGE_INTEGER ull;
    ull.LowPart = ft.dwLowDateTime;
    ull.HighPart = ft.dwHighDateTime;
    if (ull.QuadPart == 0) return 0.0;
    const uint64_t EPOCH_BIAS = 116444736000000000ULL;
    if (ull.QuadPart < EPOCH_BIAS) return 0.0;
    return static_cast<double>(ull.QuadPart - EPOCH_BIAS) / 10000000.0;
}

// RAII Handle wrapper
struct ScopedHandle {
    HANDLE h;
    explicit ScopedHandle(HANDLE handle) : h(handle) {}
    ~ScopedHandle() {
        if (h != INVALID_HANDLE_VALUE && h != NULL) {
            CloseHandle(h);
        }
    }
    bool isValid() const { return h != INVALID_HANDLE_VALUE && h != NULL; }
};

} // namespace

int rv_file_inspect(const wchar_t* path, RVFileStat* out_stat) {
    if (!path || !out_stat) return -1;

    out_stat->status = RV_IO_SUCCESS;
    out_stat->size_bytes = 0;
    out_stat->modified_time = 0.0;
    out_stat->created_time = 0.0;
    out_stat->attributes = 0;
    out_stat->win32_error_code = 0;

    WIN32_FILE_ATTRIBUTE_DATA fad;
    if (!GetFileAttributesExW(path, GetFileExInfoStandard, &fad)) {
        DWORD err = GetLastError();
        out_stat->win32_error_code = err;
        if (err == ERROR_FILE_NOT_FOUND || err == ERROR_PATH_NOT_FOUND) {
            out_stat->status = RV_IO_NOT_FOUND;
        } else if (err == ERROR_ACCESS_DENIED) {
            out_stat->status = RV_IO_ACCESS_DENIED;
        } else if (err == ERROR_SHARING_VIOLATION || err == ERROR_LOCK_VIOLATION) {
            out_stat->status = RV_IO_LOCKED;
        } else {
            out_stat->status = RV_IO_READ_ERROR;
        }
        return out_stat->status;
    }

    ULARGE_INTEGER sz;
    sz.LowPart = fad.nFileSizeLow;
    sz.HighPart = fad.nFileSizeHigh;
    out_stat->size_bytes = sz.QuadPart;
    out_stat->modified_time = FileTimeToUnixTime(fad.ftLastWriteTime);
    out_stat->created_time = FileTimeToUnixTime(fad.ftCreationTime);
    out_stat->attributes = fad.dwFileAttributes;

    // Test read access with shared mode (FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE)
    HANDLE h = CreateFileW(
        path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        NULL
    );

    if (h == INVALID_HANDLE_VALUE) {
        DWORD err = GetLastError();
        out_stat->win32_error_code = err;
        if (err == ERROR_SHARING_VIOLATION || err == ERROR_LOCK_VIOLATION) {
            out_stat->status = RV_IO_LOCKED;
        } else if (err == ERROR_ACCESS_DENIED) {
            out_stat->status = RV_IO_ACCESS_DENIED;
        } else if (err == ERROR_FILE_NOT_FOUND || err == ERROR_PATH_NOT_FOUND) {
            out_stat->status = RV_IO_NOT_FOUND;
        } else {
            out_stat->status = RV_IO_READ_ERROR;
        }
        return out_stat->status;
    }

    CloseHandle(h);
    out_stat->status = RV_IO_SUCCESS;
    return RV_IO_SUCCESS;
}

int rv_file_read_chunk(
    const wchar_t* path,
    uint64_t offset,
    uint8_t* buffer,
    uint32_t buffer_len,
    uint32_t* bytes_read
) {
    if (!path || !buffer || !bytes_read) return RV_IO_READ_ERROR;
    *bytes_read = 0;

    HANDLE h = CreateFileW(
        path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN,
        NULL
    );

    if (h == INVALID_HANDLE_VALUE) {
        DWORD err = GetLastError();
        if (err == ERROR_SHARING_VIOLATION || err == ERROR_LOCK_VIOLATION) {
            return RV_IO_LOCKED;
        } else if (err == ERROR_ACCESS_DENIED) {
            return RV_IO_ACCESS_DENIED;
        } else if (err == ERROR_FILE_NOT_FOUND) {
            return RV_IO_NOT_FOUND;
        }
        return RV_IO_READ_ERROR;
    }

    ScopedHandle scoped(h);

    LARGE_INTEGER liOffset;
    liOffset.QuadPart = static_cast<LONGLONG>(offset);
    if (!SetFilePointerEx(h, liOffset, NULL, FILE_BEGIN)) {
        return RV_IO_READ_ERROR;
    }

    DWORD dwRead = 0;
    if (!ReadFile(h, buffer, buffer_len, &dwRead, NULL)) {
        return RV_IO_READ_ERROR;
    }

    *bytes_read = dwRead;
    return RV_IO_SUCCESS;
}

int rv_file_verify_consistency(
    const wchar_t* path,
    uint64_t expected_size,
    double expected_mtime
) {
    if (!path) return -1;

    WIN32_FILE_ATTRIBUTE_DATA fad;
    if (!GetFileAttributesExW(path, GetFileExInfoStandard, &fad)) {
        return -1;
    }

    ULARGE_INTEGER sz;
    sz.LowPart = fad.nFileSizeLow;
    sz.HighPart = fad.nFileSizeHigh;
    if (sz.QuadPart != expected_size) {
        return 0; // Modified size
    }

    double current_mtime = FileTimeToUnixTime(fad.ftLastWriteTime);
    if (std::fabs(current_mtime - expected_mtime) > 0.001) {
        return 0; // Modified timestamp
    }

    return 1; // Consistent
}
