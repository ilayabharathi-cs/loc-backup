"""RetroVault Performance Benchmark: Python Baseline vs Hybrid Native Upgrade.

Runs side-by-side on the exact same dataset and system:
- Small files (3,000 files)
- Deep nested directory tree (2,000 files across 10 levels)
- Large files (5 x 10 MB)
- Incompressible random files

Measures:
- File scan time & scan rate (files/sec)
- Metadata extraction time
- Hashing throughput (MB/s)
- Compression throughput (MB/s)
- Zero-change detection time
- Incremental change detection time
- Peak RAM & Idle RAM
"""

import os
import sys
import time
import json
import psutil
import hashlib
import zstandard as zstd

sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("agent"))

from agent.src.backup.scanner import FileScanner
from agent.native.python.native_bridge import get_native_bridge
from agent.src.backup.hashing import calculate_file_sha256
from agent.src.backup.change_detector import ChangeDetector
from agent.src.windows.locked_files import LockedFileHandler


def run_comparative_benchmark(dataset_dir: str):
    print("=" * 70)
    print("RETROVAULT HYBRID PERFORMANCE BENCHMARK")
    print("=" * 70)
    
    bridge = get_native_bridge()
    print(f"Native C/C++ Engine Available: {bridge.is_available}")
    if not bridge.is_available:
        print(f"ERROR: Native engine not available: {bridge.init_error}")
        return

    proc = psutil.Process(os.getpid())
    idle_ram_mb = proc.memory_info().rss / (1024 * 1024)

    # ----------------------------------------------------
    # TEST 1: DIRECTORY SCANNING (5,000+ files)
    # ----------------------------------------------------
    print("\n[Benchmark 1] Recursive File Discovery & Metadata Scanning...")
    
    # Python Baseline Scanner
    py_scanner = FileScanner(include_paths=[dataset_dir], use_native=False)
    t0 = time.perf_counter()
    py_files = py_scanner.scan()
    py_scan_time = time.perf_counter() - t0
    py_rate = len(py_files) / py_scan_time if py_scan_time > 0 else 0

    # Hybrid Native Scanner
    native_scanner = FileScanner(include_paths=[dataset_dir], use_native=True)
    t0 = time.perf_counter()
    native_files = native_scanner.scan()
    native_scan_time = time.perf_counter() - t0
    native_rate = len(native_files) / native_scan_time if native_scan_time > 0 else 0

    scan_speedup = (py_scan_time / native_scan_time) if native_scan_time > 0 else 1.0

    print(f"  Python Scan: {len(py_files)} files in {py_scan_time:.4f}s ({py_rate:.1f} files/s)")
    print(f"  Native Scan: {len(native_files)} files in {native_scan_time:.4f}s ({native_rate:.1f} files/s)")
    print(f"  >>> File Scan Acceleration: {scan_speedup:.2f}x faster")
    assert len(py_files) == len(native_files), f"Count mismatch: {len(py_files)} vs {len(native_files)}"

    # ----------------------------------------------------
    # TEST 2: HASHING THROUGHPUT
    # ----------------------------------------------------
    print("\n[Benchmark 2] SHA-256 Hashing Throughput (10 MB payload)...")
    large_sample = os.path.join(dataset_dir, "large_files", "data_blob_0.bin")
    t0 = time.perf_counter()
    hash_large, total_bytes = calculate_file_sha256(large_sample)
    hash_time = time.perf_counter() - t0
    hash_throughput = (total_bytes / (1024 * 1024)) / hash_time if hash_time > 0 else 0
    print(f"  SHA-256 Throughput: {hash_throughput:.1f} MB/s (Completed in {hash_time:.4f}s)")

    # ----------------------------------------------------
    # TEST 3: COMPRESSION THROUGHPUT (Zstandard)
    # ----------------------------------------------------
    print("\n[Benchmark 3] Zstandard Compression (Native C zstd)...")
    cctx = zstd.ZstdCompressor(level=3)
    comp_sample_path = os.path.join(dataset_dir, "many_small", "file_0000.txt")
    with open(comp_sample_path, "rb") as f:
        sample_bytes = f.read() * 1000  # ~800 KB
    t0 = time.perf_counter()
    compressed = cctx.compress(sample_bytes)
    comp_time = time.perf_counter() - t0
    comp_throughput = (len(sample_bytes) / (1024 * 1024)) / comp_time if comp_time > 0 else 0
    print(f"  Zstd Throughput: {comp_throughput:.1f} MB/s (Ratio: {len(sample_bytes)/len(compressed):.2f}x)")

    # ----------------------------------------------------
    # TEST 4: CHANGE DETECTION & ZERO-CHANGE RUN
    # ----------------------------------------------------
    print("\n[Benchmark 4] Incremental & Zero-Change Decision Engine...")
    detector = ChangeDetector(mode="metadata")
    manifest = [
        {
            "id": idx,
            "original_path": f.original_path,
            "relative_path": f.relative_path,
            "size_bytes": f.size_bytes,
            "modified_time": f.modified_time,
            "sha256": "dummy_sha256",
            "storage_object": f"obj_{idx}",
            "change_type": "FULL",
            "upload_status": "completed"
        }
        for idx, f in enumerate(native_files)
    ]
    
    # Zero-change
    t0 = time.perf_counter()
    res_zero = detector.detect_changes(native_files, manifest)
    zero_time = time.perf_counter() - t0
    print(f"  Zero-Change Evaluation: {len(res_zero.unchanged_files)} files evaluated in {zero_time:.4f}s")

    # Incremental (5% modifications)
    import copy
    mod_files = copy.deepcopy(native_files)
    for i in range(0, len(mod_files), 20):
        mod_files[i].modified_time += 15.0
    t0 = time.perf_counter()
    res_inc = detector.detect_changes(mod_files, manifest)
    inc_time = time.perf_counter() - t0
    print(f"  Incremental Evaluation: {len(res_inc.modified_files)} modified, {len(res_inc.unchanged_files)} unchanged in {inc_time:.4f}s")

    # ----------------------------------------------------
    # TEST 5: FILE INSPECTION & CONSISTENCY CHECK
    # ----------------------------------------------------
    print("\n[Benchmark 5] Native Win32 File Inspection & Consistency Verification...")
    handler = LockedFileHandler()
    t0 = time.perf_counter()
    sample_files = native_files[:500]
    for sf in sample_files:
        inspection = handler.inspect_file(sf.original_path, sf.relative_path)
    inspect_500_time = time.perf_counter() - t0
    print(f"  Inspected 500 files in {inspect_500_time:.4f}s ({500/inspect_500_time:.1f} files/s)")

    peak_ram_mb = proc.memory_info().rss / (1024 * 1024)

    benchmark_summary = {
        "dataset_files": len(native_files),
        "dataset_mb": round(sum(f.size_bytes for f in native_files) / (1024 * 1024), 2),
        "python_scan_time_s": round(py_scan_time, 4),
        "python_scan_rate_files_s": round(py_rate, 1),
        "native_scan_time_s": round(native_scan_time, 4),
        "native_scan_rate_files_s": round(native_rate, 1),
        "scan_acceleration_factor": round(scan_speedup, 2),
        "hash_throughput_mb_s": round(hash_throughput, 1),
        "compression_throughput_mb_s": round(comp_throughput, 1),
        "zero_change_duration_s": round(zero_time, 4),
        "incremental_duration_s": round(inc_time, 4),
        "idle_ram_mb": round(idle_ram_mb, 2),
        "peak_ram_mb": round(peak_ram_mb, 2)
    }

    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY RESULTS:")
    print(json.dumps(benchmark_summary, indent=2))
    print("=" * 70)

    with open("benchmark_comparison.json", "w") as f:
        json.dump(benchmark_summary, f, indent=2)


if __name__ == "__main__":
    bench_dir = os.path.abspath("temp_benchmark_dataset")
    run_comparative_benchmark(bench_dir)
