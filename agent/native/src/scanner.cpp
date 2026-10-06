#include "../include/scanner.h"

#include <windows.h>
#include <string>
#include <vector>
#include <algorithm>

namespace {

// Converts Win32 FILETIME to Unix timestamp (seconds since 1970-01-01 UTC)
inline double FileTimeToUnixTime(const FILETIME& ft) {
    ULARGE_INTEGER ull;
    ull.LowPart = ft.dwLowDateTime;
    ull.HighPart = ft.dwHighDateTime;
    if (ull.QuadPart == 0) return 0.0;
    // Difference between 1601-01-01 and 1970-01-01 in 100-nanosecond intervals: 116444736000000000
    const uint64_t EPOCH_BIAS = 116444736000000000ULL;
    if (ull.QuadPart < EPOCH_BIAS) return 0.0;
    return static_cast<double>(ull.QuadPart - EPOCH_BIAS) / 10000000.0;
}

// Convert wide string to lowercase for case-insensitive path comparisons
std::wstring ToLower(const std::wstring& s) {
    std::wstring res = s;
    std::transform(res.begin(), res.end(), res.begin(), ::towlower);
    return res;
}

// Normalize path separators to standard backslash and remove trailing slash
std::wstring NormalizePath(const std::wstring& p) {
    std::wstring res = p;
    for (size_t i = 0; i < res.size(); ++i) {
        if (res[i] == L'/') {
            res[i] = L'\\';
        }
    }
    while (res.size() > 3 && res.back() == L'\\') {
        res.pop_back();
    }
    return res;
}

// Check if norm_lower_path matches any exclusion prefix
bool IsExcluded(const std::wstring& path_lower, const std::vector<std::wstring>& excludes) {
    for (const auto& exc : excludes) {
        if (path_lower == exc) return true;
        if (path_lower.rfind(exc, 0) == 0) {
            // Must match full directory component
            if (exc.back() == L'\\' || (path_lower.size() > exc.size() && path_lower[exc.size()] == L'\\')) {
                return true;
            }
        }
    }
    return false;
}

// Ensure path has \\?\ prefix for long paths (> 240 chars)
std::wstring MakeExtendedPath(const std::wstring& path) {
    if (path.length() >= 240 && path.rfind(L"\\\\?\\", 0) != 0) {
        return L"\\\\?\\" + path;
    }
    return path;
}

struct ScanContext {
    std::vector<std::wstring> excludes_lower;
    RVScanCallback callback;
    void* user_data;
    const int* cancel_flag;
    RVFileInfo batch[RV_BATCH_SIZE];
    int batch_count;
    uint64_t total_scanned;

    void FlushBatch() {
        if (batch_count > 0) {
            callback(batch, batch_count, user_data);
            batch_count = 0;
        }
    }

    void AddItem(const std::wstring& full_path, const WIN32_FIND_DATAW& fd) {
        RVFileInfo& info = batch[batch_count++];
        wcsncpy(info.path, full_path.c_str(), RV_MAX_PATH - 1);
        info.path[RV_MAX_PATH - 1] = L'\0';

        ULARGE_INTEGER sz;
        sz.LowPart = fd.nFileSizeLow;
        sz.HighPart = fd.nFileSizeHigh;
        info.size_bytes = sz.QuadPart;

        info.modified_time = FileTimeToUnixTime(fd.ftLastWriteTime);
        info.created_time = FileTimeToUnixTime(fd.ftCreationTime);
        info.attributes = fd.dwFileAttributes;
        info.is_directory = (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ? 1 : 0;

        total_scanned++;

        if (batch_count >= RV_BATCH_SIZE) {
            FlushBatch();
        }
    }
};

void ScanDirectoryRecursive(const std::wstring& dir_path, ScanContext& ctx, int depth) {
    if (ctx.cancel_flag && *(ctx.cancel_flag) != 0) {
        return;
    }
    if (depth > 64) {
        return; // Guard against stack overflow or cyclic loops
    }

    std::wstring search_pattern = MakeExtendedPath(dir_path) + L"\\*";
    WIN32_FIND_DATAW fd;
    HANDLE hFind = FindFirstFileExW(
        search_pattern.c_str(),
        FindExInfoBasic,
        &fd,
        FindExSearchNameMatch,
        NULL,
        FIND_FIRST_EX_LARGE_FETCH
    );

    if (hFind == INVALID_HANDLE_VALUE) {
        return;
    }

    std::vector<std::wstring> subdirs;

    do {
        if (ctx.cancel_flag && *(ctx.cancel_flag) != 0) {
            break;
        }

        // Skip . and ..
        if (wcscmp(fd.cFileName, L".") == 0 || wcscmp(fd.cFileName, L"..") == 0) {
            continue;
        }

        // Skip symlinks and junctions (reparse points) to prevent circular traversal
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) {
            continue;
        }

        std::wstring full_path = dir_path + L"\\" + fd.cFileName;
        std::wstring full_path_lower = ToLower(NormalizePath(full_path));

        if (IsExcluded(full_path_lower, ctx.excludes_lower)) {
            continue;
        }

        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            subdirs.push_back(full_path);
        } else {
            ctx.AddItem(full_path, fd);
        }
    } while (FindNextFileW(hFind, &fd));

    FindClose(hFind);

    // Recurse into subdirectories
    for (const auto& sub : subdirs) {
        if (ctx.cancel_flag && *(ctx.cancel_flag) != 0) break;
        ScanDirectoryRecursive(sub, ctx, depth + 1);
    }
}

} // namespace

int rv_scan_directory(
    const wchar_t** roots,
    int root_count,
    const wchar_t** excludes,
    int exclude_count,
    RVScanCallback callback,
    void* user_data,
    const int* cancel_flag
) {
    if (!roots || root_count <= 0 || !callback) {
        return -1;
    }

    ScanContext ctx;
    ctx.callback = callback;
    ctx.user_data = user_data;
    ctx.cancel_flag = cancel_flag;
    ctx.batch_count = 0;
    ctx.total_scanned = 0;

    for (int i = 0; i < exclude_count; ++i) {
        if (excludes[i]) {
            ctx.excludes_lower.push_back(ToLower(NormalizePath(excludes[i])));
        }
    }

    for (int i = 0; i < root_count; ++i) {
        if (!roots[i]) continue;
        if (ctx.cancel_flag && *(ctx.cancel_flag) != 0) break;

        std::wstring root_norm = NormalizePath(roots[i]);
        std::wstring root_lower = ToLower(root_norm);

        if (IsExcluded(root_lower, ctx.excludes_lower)) {
            continue;
        }

        DWORD attrs = GetFileAttributesW(MakeExtendedPath(root_norm).c_str());
        if (attrs == INVALID_FILE_ATTRIBUTES) {
            continue;
        }

        if (attrs & FILE_ATTRIBUTE_DIRECTORY) {
            ScanDirectoryRecursive(root_norm, ctx, 0);
        } else {
            // Single file root
            WIN32_FIND_DATAW fd;
            HANDLE hFind = FindFirstFileW(MakeExtendedPath(root_norm).c_str(), &fd);
            if (hFind != INVALID_HANDLE_VALUE) {
                ctx.AddItem(root_norm, fd);
                FindClose(hFind);
            }
        }
    }

    ctx.FlushBatch();
    return 0;
}
