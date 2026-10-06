#ifndef RETROVAULT_FILE_IO_H
#define RETROVAULT_FILE_IO_H

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

typedef enum {
    RV_IO_SUCCESS = 0,
    RV_IO_LOCKED = 1,
    RV_IO_ACCESS_DENIED = 2,
    RV_IO_NOT_FOUND = 3,
    RV_IO_READ_ERROR = 4,
    RV_IO_MODIFIED_DURING_READ = 5
} RVIOResult;

typedef struct {
    int status;                // RVIOResult
    uint64_t size_bytes;
    double modified_time;
    double created_time;
    uint32_t attributes;
    uint32_t win32_error_code;
} RVFileStat;

/**
 * Inspects a file's state, size, timestamps, and accessibility with Win32 sharing flags.
 */
RV_EXPORT int rv_file_inspect(const wchar_t* path, RVFileStat* out_stat);

/**
 * Reads a bounded chunk of bytes from a file starting at offset.
 * Opens handle with FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE.
 * 
 * @param path Path to file.
 * @param offset Byte offset to start reading from.
 * @param buffer Output buffer pre-allocated by caller.
 * @param buffer_len Maximum bytes to read into buffer.
 * @param bytes_read Pointer receiving actual bytes read.
 * @return RVIOResult code.
 */
RV_EXPORT int rv_file_read_chunk(
    const wchar_t* path,
    uint64_t offset,
    uint8_t* buffer,
    uint32_t buffer_len,
    uint32_t* bytes_read
);

/**
 * Verifies if file size and mtime have remained unchanged compared to expected values.
 * Returns 1 if consistent, 0 if modified, -1 on error.
 */
RV_EXPORT int rv_file_verify_consistency(
    const wchar_t* path,
    uint64_t expected_size,
    double expected_mtime
);

#ifdef __cplusplus
}
#endif

#endif // RETROVAULT_FILE_IO_H
