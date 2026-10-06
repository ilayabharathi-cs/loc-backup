#include "../include/usn_provider.h"

#include <windows.h>
#include <winioctl.h>
#include <shlobj.h>
#include <string>
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

std::wstring GetVolumeDevicePath(const wchar_t* volume_path) {
    if (!volume_path) return L"";
    std::wstring vol = volume_path;
    // Strip trailing slashes
    while (!vol.empty() && (vol.back() == L'\\' || vol.back() == L'/')) {
        vol.pop_back();
    }
    // If e.g. "C:", return "\\\\.\\C:"
    return L"\\\\.\\" + vol;
}

std::wstring GetVolumeRootPath(const wchar_t* volume_path) {
    if (!volume_path) return L"";
    std::wstring vol = volume_path;
    while (!vol.empty() && (vol.back() == L'\\' || vol.back() == L'/')) {
        vol.pop_back();
    }
    return vol + L"\\";
}

} // namespace

int rv_usn_check_availability(const wchar_t* volume_path, wchar_t* out_reason, int max_reason_len) {
    if (!volume_path) return RV_USN_ERROR;

    if (!IsUserAnAdmin()) {
        if (out_reason && max_reason_len > 0) {
            wcsncpy(out_reason, L"USN Journal query requires Windows Administrator privileges", max_reason_len - 1);
            out_reason[max_reason_len - 1] = L'\0';
        }
        return RV_USN_NOT_ADMIN;
    }

    std::wstring root_path = GetVolumeRootPath(volume_path);
    wchar_t fs_name[32] = {0};
    if (!GetVolumeInformationW(
        root_path.c_str(),
        NULL, 0, NULL, NULL, NULL,
        fs_name, 32
    )) {
        if (out_reason && max_reason_len > 0) {
            wcsncpy(out_reason, L"Unable to query volume filesystem information", max_reason_len - 1);
            out_reason[max_reason_len - 1] = L'\0';
        }
        return RV_USN_ERROR;
    }

    if (wcscmp(fs_name, L"NTFS") != 0) {
        if (out_reason && max_reason_len > 0) {
            _snwprintf(out_reason, max_reason_len - 1, L"Volume filesystem '%s' does not support USN Journal (NTFS required)", fs_name);
            out_reason[max_reason_len - 1] = L'\0';
        }
        return RV_USN_NOT_NTFS;
    }

    if (out_reason && max_reason_len > 0) {
        wcsncpy(out_reason, L"USN Journal is available on NTFS volume", max_reason_len - 1);
        out_reason[max_reason_len - 1] = L'\0';
    }
    return RV_USN_OK;
}

int rv_usn_query_info(
    const wchar_t* volume_path,
    uint64_t* out_journal_id,
    uint64_t* out_next_usn
) {
    if (!volume_path || !out_journal_id || !out_next_usn) return RV_USN_ERROR;

    std::wstring dev_path = GetVolumeDevicePath(volume_path);
    HANDLE hVol = CreateFileW(
        dev_path.c_str(),
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_EXISTING,
        0,
        NULL
    );

    if (hVol == INVALID_HANDLE_VALUE) {
        DWORD err = GetLastError();
        if (err == ERROR_ACCESS_DENIED) return RV_USN_ACCESS_DENIED;
        return RV_USN_ERROR;
    }

    ScopedHandle scoped(hVol);

    USN_JOURNAL_DATA ujd;
    ZeroMemory(&ujd, sizeof(ujd));
    DWORD bytesReturned = 0;
    if (!DeviceIoControl(
        hVol,
        FSCTL_QUERY_USN_JOURNAL,
        NULL, 0,
        &ujd, sizeof(ujd),
        &bytesReturned,
        NULL
    )) {
        DWORD err = GetLastError();
        if (err == ERROR_JOURNAL_NOT_ACTIVE) return RV_USN_JOURNAL_NOT_ACTIVE;
        if (err == ERROR_ACCESS_DENIED) return RV_USN_ACCESS_DENIED;
        return RV_USN_ERROR;
    }

    *out_journal_id = ujd.UsnJournalID;
    *out_next_usn = static_cast<uint64_t>(ujd.NextUsn);
    return RV_USN_OK;
}

int rv_usn_read_changes(
    const wchar_t* volume_path,
    uint64_t since_usn,
    RVUSNRecordCallback callback,
    void* user_data,
    uint64_t* out_highest_usn
) {
    if (!volume_path || !callback || !out_highest_usn) return RV_USN_ERROR;
    *out_highest_usn = since_usn;

    uint64_t journal_id = 0;
    uint64_t next_usn = 0;
    int info_res = rv_usn_query_info(volume_path, &journal_id, &next_usn);
    if (info_res != RV_USN_OK) {
        return info_res;
    }

    std::wstring dev_path = GetVolumeDevicePath(volume_path);
    HANDLE hVol = CreateFileW(
        dev_path.c_str(),
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        OPEN_EXISTING,
        0,
        NULL
    );

    if (hVol == INVALID_HANDLE_VALUE) {
        return RV_USN_ACCESS_DENIED;
    }

    ScopedHandle scoped(hVol);

    READ_USN_JOURNAL_DATA rujd;
    ZeroMemory(&rujd, sizeof(rujd));
    rujd.StartUsn = static_cast<USN>(since_usn);
    rujd.ReasonMask = 0xFFFFFFFF; // All reasons
    rujd.ReturnOnlyOnClose = 0;
    rujd.Timeout = 0;
    rujd.BytesToWaitFor = 0;
    rujd.UsnJournalID = journal_id;

    const DWORD BUF_SIZE = 64 * 1024;
    std::vector<uint8_t> buffer(BUF_SIZE);
    wchar_t name_buf[1024];

    uint64_t highest_seen = since_usn;

    while (true) {
        DWORD bytesReturned = 0;
        if (!DeviceIoControl(
            hVol,
            FSCTL_READ_USN_JOURNAL,
            &rujd, sizeof(rujd),
            buffer.data(), BUF_SIZE,
            &bytesReturned,
            NULL
        )) {
            DWORD err = GetLastError();
            if (err == ERROR_HANDLE_EOF || err == ERROR_WRITE_PROTECT) {
                break;
            }
            if (err == ERROR_JOURNAL_ENTRY_DELETED) {
                return RV_USN_JOURNAL_TRUNCATED;
            }
            break;
        }

        if (bytesReturned <= sizeof(USN)) {
            break;
        }

        // First 8 bytes is the next start USN
        USN next_start = *reinterpret_cast<USN*>(buffer.data());
        uint8_t* pCurrent = buffer.data() + sizeof(USN);
        uint8_t* pEnd = buffer.data() + bytesReturned;

        int record_count = 0;
        while (pCurrent < pEnd) {
            USN_RECORD* record = reinterpret_cast<USN_RECORD*>(pCurrent);
            if (record->RecordLength == 0) break;

            int chars = record->FileNameLength / sizeof(wchar_t);
            int copy_len = (chars < 1023) ? chars : 1023;
            const wchar_t* pName = reinterpret_cast<const wchar_t*>(pCurrent + record->FileNameOffset);
            wcsncpy(name_buf, pName, copy_len);
            name_buf[copy_len] = L'\0';

            uint64_t rec_usn = static_cast<uint64_t>(record->Usn);
            if (rec_usn > highest_seen) {
                highest_seen = rec_usn;
            }

            callback(
                record->FileReferenceNumber,
                record->ParentFileReferenceNumber,
                rec_usn,
                record->Reason,
                name_buf,
                user_data
            );

            record_count++;
            pCurrent += record->RecordLength;
        }

        if (next_start <= rujd.StartUsn || record_count == 0) {
            break;
        }
        rujd.StartUsn = next_start;
    }

    *out_highest_usn = highest_seen;
    return RV_USN_OK;
}
