#ifndef RETROVAULT_VSS_PROVIDER_H
#define RETROVAULT_VSS_PROVIDER_H

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
    RV_VSS_OK = 0,
    RV_VSS_NOT_ADMIN = 1,
    RV_VSS_SERVICE_UNAVAILABLE = 2,
    RV_VSS_TIMEOUT = 3,
    RV_VSS_FAILED = 4
} RVVSSResult;

/**
 * Checks if current process has Windows Administrator privileges.
 * Returns 1 if elevated, 0 otherwise.
 */
RV_EXPORT int rv_vss_is_admin(void);

/**
 * Resolves a file's path inside a shadow copy device.
 */
RV_EXPORT int rv_vss_resolve_path(
    const wchar_t* snapshot_device,
    const wchar_t* relative_path,
    wchar_t* out_mapped_path,
    int max_mapped_len
);

/**
 * Creates a genuine volume shadow copy snapshot.
 * Writes device path (e.g. \\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy1) and snapshot ID.
 */
RV_EXPORT int rv_vss_create_snapshot(
    const wchar_t* volume_letter,
    wchar_t* out_device,
    int max_device_len,
    wchar_t* out_id,
    int max_id_len,
    wchar_t* out_error,
    int max_error_len
);

/**
 * Deletes an active volume shadow copy snapshot.
 */
RV_EXPORT int rv_vss_delete_snapshot(
    const wchar_t* snapshot_id,
    wchar_t* out_error,
    int max_error_len
);

#ifdef __cplusplus
}
#endif

#endif // RETROVAULT_VSS_PROVIDER_H
