"""RetroVault Performance Benchmark Suite.
Measures baseline Python implementation vs Hybrid Native implementation:
- Startup time
- Idle CPU & Idle RAM
- File scan time (small files, nested tree, large files)
- Metadata extraction time
- Hashing time
- Compression time
- Incremental change detection time
- Zero-change detection time
"""

import os
import sys
import time
import json
import shutil
import tempfile
import psutil
import hashlib

# Ensure paths
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath("agent"))

from agent.src.backup.scanner import FileScanner
from agent.src.backup.models import DiscoveredFile
from agent.src.backup.hashing import calculate_file_sha256
from agent.src.backup.change_detector import ChangeDetector
import zstandard as zstd


def generate_benchmark_dataset(base_dir: str):
    """Generate reproducible benchmark files."""
    print("Generating benchmark dataset in:", base_dir)
    os.makedirs(base_dir, exist_ok=True)
    
    # 1. Many small files (3,000 small text/code files)
    small_dir = os.path.join(base_dir, "many_small")
    os.makedirs(small_dir, exist_ok=True)
    sample_content = b"RetroVault Backup Benchmark Content Line " * 20  # ~820 bytes
    for i in range(3000):
        with open(os.path.join(small_dir, f"file_{i:04d}.txt"), "wb") as f:
            f.write(sample_content + f" index {i}\n".encode())
            
    # 2. Deep nested folder tree (2,000 files across 10 directory levels)
    nested_dir = os.path.join(base_dir, "nested_dirs")
    curr = nested_dir
    for depth in range(10):
        curr = os.path.join(curr, f"level_{depth}")
        os.makedirs(curr, exist_ok=True)
        for i in range(200):
            with open(os.path.join(curr, f"nested_doc_{i:03d}.log"), "wb") as f:
                f.write(b"Log entry data timestamp 2026-10-06\n" * 15)

    # 3. Medium & Large binary files (5 x 10 MB = 50 MB)
    large_dir = os.path.join(base_dir, "large_files")
    os.makedirs(large_dir, exist_ok=True)
    chunk_1mb = os.urandom(1024 * 1024)
    for i in range(5):
        with open(os.path.join(large_dir, f"data_blob_{i}.bin"), "wb") as f:
            for _ in range(10):
                f.write(chunk_1mb)

    # 4. Incompressible random files (10 MB random)
    incomp_dir = os.path.join(base_dir, "incompressible")
    os.makedirs(incomp_dir, exist_ok=True)
    with open(os.path.join(incomp_dir, "random.dat"), "wb") as f:
        f.write(os.urandom(5 * 1024 * 1024))

    print("Dataset generation complete.")


def run_benchmark(dataset_dir: str, label: str = "Python Baseline") -> dict:
    proc = psutil.Process(os.getpid())
    
    # Idle metrics
    idle_cpu = proc.cpu_percent(interval=0.2)
    idle_ram_mb = proc.memory_info().rss / (1024 * 1024)
    
    # 1. Startup measurement
    t0 = time.perf_counter()
    # Simulate agent module initialization
    import agent.src.config
    import agent.src.backup.backup_engine
    startup_time = (time.perf_counter() - t0) * 1000  # ms

    # 2. File Scan Benchmark
    scanner = FileScanner(include_paths=[dataset_dir])
    
    t0 = time.perf_counter()
    files = scanner.scan()
    scan_duration = time.perf_counter() - t0
    
    file_count = len(files)
    total_bytes = sum(f.size_bytes for f in files)
    
    # 3. Hashing Benchmark (Sample of 100 small files + 1 large 10MB file)
    large_sample = os.path.join(dataset_dir, "large_files", "data_blob_0.bin")
    t0 = time.perf_counter()
    hash_large, _ = calculate_file_sha256(large_sample)
    hash_large_time = time.perf_counter() - t0
    
    # 4. Compression Benchmark (Zstd level 3 on compressible vs incompressible)
    cctx = zstd.ZstdCompressor(level=3)
    comp_sample_path = os.path.join(dataset_dir, "many_small", "file_0000.txt")
    with open(comp_sample_path, "rb") as f:
        sample_bytes = f.read() * 500  # ~400 KB
    t0 = time.perf_counter()
    compressed = cctx.compress(sample_bytes)
    comp_time = (time.perf_counter() - t0) * 1000  # ms
    
    # 5. Incremental Change Detection Benchmark
    detector = ChangeDetector(mode="metadata")
    # Baseline manifest representation
    manifest = [
        {
            "id": idx,
            "original_path": f.original_path,
            "relative_path": f.relative_path,
            "size_bytes": f.size_bytes,
            "modified_time": f.modified_time,
            "sha256": "dummyhash",
            "storage_object": f"obj_{idx}",
            "change_type": "FULL",
            "upload_status": "completed"
        }
        for idx, f in enumerate(files)
    ]
    
    # Zero-change run
    t0 = time.perf_counter()
    res_zero = detector.detect_changes(files, manifest)
    zero_change_time = time.perf_counter() - t0
    
    # Incremental with 5% modified files
    import copy
    mod_files = copy.deepcopy(files)
    for i in range(0, len(mod_files), 20):  # 5%
        mod_files[i].modified_time += 10.0
    t0 = time.perf_counter()
    res_inc = detector.detect_changes(mod_files, manifest)
    incremental_time = time.perf_counter() - t0

    peak_ram_mb = proc.memory_info().rss / (1024 * 1024)

    results = {
        "label": label,
        "files_scanned": file_count,
        "total_megabytes": round(total_bytes / (1024 * 1024), 2),
        "idle_cpu_percent": idle_cpu,
        "idle_ram_mb": round(idle_ram_mb, 2),
        "peak_ram_mb": round(peak_ram_mb, 2),
        "startup_ms": round(startup_time, 2),
        "scan_time_seconds": round(scan_duration, 4),
        "scan_rate_files_per_sec": round(file_count / scan_duration, 1) if scan_duration > 0 else 0,
        "hash_10mb_seconds": round(hash_large_time, 4),
        "hash_10mb_throughput_mb_s": round(10.0 / hash_large_time, 1) if hash_large_time > 0 else 0,
        "compression_400kb_ms": round(comp_time, 3),
        "zero_change_detection_seconds": round(zero_change_time, 4),
        "incremental_detection_seconds": round(incremental_time, 4),
        "new_count": len(res_inc.new_files),
        "modified_count": len(res_inc.modified_files),
        "unchanged_count": len(res_inc.unchanged_files),
    }
    return results


if __name__ == "__main__":
    bench_dir = os.path.abspath("temp_benchmark_dataset")
    if not os.path.exists(bench_dir):
        generate_benchmark_dataset(bench_dir)
        
    print("\n--- Running Python Baseline Benchmark ---")
    baseline = run_benchmark(bench_dir, "Python Baseline")
    print(json.dumps(baseline, indent=2))
    
    with open("benchmark_baseline.json", "w") as f:
        json.dump(baseline, f, indent=2)
    print("\nBaseline saved to benchmark_baseline.json")
