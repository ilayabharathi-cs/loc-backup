"""Agent-side Shannon entropy sampler for RetroVault V8.

Samples files during scan phase to compute entropy and detect anomalous files before upload.
"""

import math
import os
from typing import Dict, Any, Optional


class AgentEntropySampler:
    """Computes Shannon entropy for agent files using lightweight 3-block sampling."""

    SAMPLE_BLOCK_SIZE = 65536  # 64 KB

    @staticmethod
    def calculate_entropy(data: bytes) -> float:
        if not data:
            return 0.0
        counts = [0] * 256
        for b in data:
            counts[b] += 1
        total = len(data)
        entropy = 0.0
        for c in counts:
            if c > 0:
                p = c / total
                entropy -= p * math.log2(p)
        return round(entropy, 4)

    @classmethod
    def sample_file(cls, filepath: str) -> Optional[float]:
        """Calculates entropy of a file using 3-block sampling (header, mid, tail)."""
        if not os.path.isfile(filepath):
            return None

        try:
            size = os.path.getsize(filepath)
            if size == 0:
                return 0.0

            with open(filepath, "rb") as f:
                if size <= cls.SAMPLE_BLOCK_SIZE * 3:
                    data = f.read()
                    return cls.calculate_entropy(data)

                # Header
                header = f.read(cls.SAMPLE_BLOCK_SIZE)
                # Middle
                mid_offset = (size - cls.SAMPLE_BLOCK_SIZE) // 2
                f.seek(mid_offset)
                middle = f.read(cls.SAMPLE_BLOCK_SIZE)
                # Tail
                f.seek(size - cls.SAMPLE_BLOCK_SIZE)
                tail = f.read(cls.SAMPLE_BLOCK_SIZE)

                return cls.calculate_entropy(header + middle + tail)
        except Exception:
            return None
