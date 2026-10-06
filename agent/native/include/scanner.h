#ifndef RETROVAULT_SCANNER_H
#define RETROVAULT_SCANNER_H

#include <stdint.h>
#include <wchar.h>

#ifdef _WIN32
  #define RV_EXPORT __declspec(dllexport)
#else
  #define RV_EXPORT
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define RV_MAX_PATH 1024
#define RV_BATCH_SIZE 512

typedef struct {
    wchar_t path[RV_MAX_PATH];
    uint64_t size_bytes;
    double modified_time;
    double created_time;
    uint32_t attributes;
    uint32_t is_directory;
} RVFileInfo;

typedef void (*RVScanCallback)(const RVFileInfo* items, int count, void* user_data);

/**
 * Recursively scans directory roots using high-performance Win32 FindFirstFileW/FindNextFileW.
 * 
 * @param roots Null-terminated array of wide-character root directory paths.
 * @param root_count Number of root paths.
 * @param excludes Null-terminated array of wide-character excluded path prefixes (lowercase).
 * @param exclude_count Number of excluded paths.
 * @param callback Callback receiving batched RVFileInfo items.
 * @param user_data Opaque pointer forwarded to callback.
 * @param cancel_flag Optional pointer to integer: if *cancel_flag != 0, scan stops immediately.
 * @return 0 on success, or Win32/internal error code on failure.
 */
RV_EXPORT int rv_scan_directory(
    const wchar_t** roots,
    int root_count,
    const wchar_t** excludes,
    int exclude_count,
    RVScanCallback callback,
    void* user_data,
    const int* cancel_flag
);

#ifdef __cplusplus
}
#endif

#endif // RETROVAULT_SCANNER_H
