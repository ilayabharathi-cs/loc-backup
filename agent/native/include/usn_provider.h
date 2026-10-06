#ifndef RETROVAULT_USN_PROVIDER_H
#define RETROVAULT_USN_PROVIDER_H

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
    RV_USN_OK = 0,
    RV_USN_NOT_ADMIN = 1,
    RV_USN_NOT_NTFS = 2,
    RV_USN_JOURNAL_NOT_ACTIVE = 3,
    RV_USN_ACCESS_DENIED = 4,
    RV_USN_JOURNAL_TRUNCATED = 5,
    RV_USN_ERROR = 6
} RVUSNResult;

typedef void (*RVUSNRecordCallback)(
    uint64_t file_ref_number,
    uint64_t parent_ref_number,
    uint64_t usn,
    uint32_t reason,
    const wchar_t* file_name,
    void* user_data
);

/**
 * Checks if target volume supports USN Journal and calling process has required privileges.
 */
RV_EXPORT int rv_usn_check_availability(const wchar_t* volume_path, wchar_t* out_reason, int max_reason_len);

/**
 * Queries current USN Journal info (Journal ID and Next USN).
 */
RV_EXPORT int rv_usn_query_info(
    const wchar_t* volume_path,
    uint64_t* out_journal_id,
    uint64_t* out_next_usn
);

/**
 * Reads changed records from USN Journal since given USN.
 * Passes each record to callback.
 */
RV_EXPORT int rv_usn_read_changes(
    const wchar_t* volume_path,
    uint64_t since_usn,
    RVUSNRecordCallback callback,
    void* user_data,
    uint64_t* out_highest_usn
);

#ifdef __cplusplus
}
#endif

#endif // RETROVAULT_USN_PROVIDER_H
