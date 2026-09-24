"""Entropy analysis service for ransomware detection in RetroVault V8.

Uses Shannon entropy over sampled blocks (header, middle, tail) with extension-aware baselines.
"""

import math
from typing import Dict, Any, List, Optional


class EntropyAnalyzer:
    """Calculates Shannon entropy and evaluates against extension-aware baselines."""

    # Baseline expected entropy for common file extensions (0.0 to 8.0)
    EXTENSION_BASELINES: Dict[str, float] = {
        # Plain text and source code (low entropy)
        ".txt": 4.5,
        ".log": 4.3,
        ".csv": 4.8,
        ".json": 5.0,
        ".xml": 4.9,
        ".html": 5.0,
        ".css": 5.1,
        ".js": 5.3,
        ".py": 5.2,
        ".sql": 4.8,
        ".md": 4.7,
        # Office / Documents (unencrypted)
        ".docx": 7.6,  # zip container
        ".xlsx": 7.6,  # zip container
        ".pptx": 7.6,
        ".pdf": 7.7,
        # Already compressed/encrypted formats (naturally high entropy)
        ".zip": 7.9,
        ".gz": 7.9,
        ".tar": 6.5,
        ".7z": 7.95,
        ".zst": 7.95,
        ".jpg": 7.8,
        ".jpeg": 7.8,
        ".png": 7.8,
        ".mp4": 7.9,
        ".mp3": 7.8,
        # Executables / Binaries
        ".exe": 6.8,
        ".dll": 6.7,
        ".bin": 6.5,
    }

    SUSPICIOUS_RANSOM_EXTENSIONS: set = {
        ".locked", ".crypto", ".crypt", ".enc", ".locky", ".cerber",
        ".wannacry", ".wncry", ".ryuk", ".revil", ".sodinokibi",
        ".darkside", ".blackmatter", ".conti", ".hive", ".blackcat",
        ".alphv", ".lockbit", ".phobos", ".dharma", ".makop",
        ".crypted", ".encrypted", ".vault", ".mole", ".odin", ".zepto"
    }

    @staticmethod
    def calculate_shannon_entropy(data: bytes) -> float:
        """Calculates Shannon entropy in bits per byte [0.0 - 8.0]."""
        if not data:
            return 0.0

        byte_counts = [0] * 256
        for b in data:
            byte_counts[b] += 1

        total_bytes = len(data)
        entropy = 0.0
        for count in byte_counts:
            if count > 0:
                p = count / total_bytes
                entropy -= p * math.log2(p)

        return round(entropy, 4)

    @classmethod
    def sample_and_calculate_entropy(cls, file_bytes: bytes, sample_block_size: int = 65536) -> Dict[str, Any]:
        """Calculates entropy using 3-block sampling (header, middle, tail) for large files."""
        total_len = len(file_bytes)
        if total_len == 0:
            return {
                "overall_entropy": 0.0,
                "header_entropy": 0.0,
                "middle_entropy": 0.0,
                "tail_entropy": 0.0,
                "sampled_bytes": 0,
                "total_bytes": 0,
            }

        if total_len <= sample_block_size * 3:
            # File is small enough to compute directly
            ent = cls.calculate_shannon_entropy(file_bytes)
            return {
                "overall_entropy": ent,
                "header_entropy": ent,
                "middle_entropy": ent,
                "tail_entropy": ent,
                "sampled_bytes": total_len,
                "total_bytes": total_len,
            }

        # Sample header, middle, tail
        header_chunk = file_bytes[:sample_block_size]
        mid_start = (total_len - sample_block_size) // 2
        middle_chunk = file_bytes[mid_start : mid_start + sample_block_size]
        tail_chunk = file_bytes[-sample_block_size:]

        h_ent = cls.calculate_shannon_entropy(header_chunk)
        m_ent = cls.calculate_shannon_entropy(middle_chunk)
        t_ent = cls.calculate_shannon_entropy(tail_chunk)
        combined_sample = header_chunk + middle_chunk + tail_chunk
        overall = cls.calculate_shannon_entropy(combined_sample)

        return {
            "overall_entropy": overall,
            "header_entropy": h_ent,
            "middle_entropy": m_ent,
            "tail_entropy": t_ent,
            "sampled_bytes": len(combined_sample),
            "total_bytes": total_len,
        }

    @classmethod
    def evaluate_file_entropy(
        cls,
        filename: str,
        entropy: float,
        previous_entropy: Optional[float] = None,
        entropy_threshold: float = 7.4
    ) -> Dict[str, Any]:
        """Evaluates whether an entropy measurement is suspicious for the given file type."""
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()

        baseline = cls.EXTENSION_BASELINES.get(ext, 6.0)
        is_known_high_entropy = ext in {".zip", ".gz", ".7z", ".zst", ".jpg", ".jpeg", ".png", ".mp4", ".mp3", ".pdf", ".docx", ".xlsx", ".pptx"}
        is_suspicious_extension = ext in cls.SUSPICIOUS_RANSOM_EXTENSIONS

        # If previous entropy exists, compute delta
        entropy_delta = round(entropy - previous_entropy, 4) if previous_entropy is not None else 0.0

        # Anomaly determination
        is_suspicious = False
        reasons: List[str] = []

        if is_suspicious_extension:
            is_suspicious = True
            reasons.append(f"Suspicious ransomware extension detected: '{ext}'")

        if not is_known_high_entropy and entropy >= entropy_threshold:
            is_suspicious = True
            reasons.append(f"High entropy {entropy} exceeds threshold {entropy_threshold} for type '{ext or 'unknown'}' (baseline: {baseline})")

        if previous_entropy is not None and (entropy - previous_entropy) > 2.0 and not is_known_high_entropy:
            is_suspicious = True
            reasons.append(f"Drastic entropy increase from {previous_entropy} to {entropy} (delta: +{entropy_delta})")

        return {
            "filename": filename,
            "extension": ext,
            "measured_entropy": entropy,
            "baseline_entropy": baseline,
            "entropy_delta": entropy_delta,
            "is_suspicious": is_suspicious,
            "reasons": reasons,
        }
