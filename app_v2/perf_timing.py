"""
Performance timing helper untuk Indonesia BioDashboard.
Gunakan log_timing() untuk instrumentasi callback dan sub-fungsi AI.
"""

import time
from datetime import datetime

try:
    import psutil as _psutil
    _PROC = _psutil.Process()
    def _mem_mb() -> float:
        return _PROC.memory_info().rss / (1024 * 1024)
except Exception:
    def _mem_mb() -> float:
        return 0.0


def log_timing(function_name: str, t0: float, t1: float,
               additional_info: dict | None = None) -> float:
    """
    Cetak timing ke stdout dan kembalikan elapsed time dalam ms.

    Format: [HH:MM:SS.mmm] [FUNCTION_NAME] XXX.Xms | Memory: XXXX.XMB | {info}
    """
    elapsed_ms = (t1 - t0) * 1000
    ts = datetime.now().strftime("%H:%M:%S.") + f"{datetime.now().microsecond // 1000:03d}"
    mem = _mem_mb()
    info_str = f" | {additional_info}" if additional_info else ""
    print(f"[{ts}] [{function_name}] {elapsed_ms:.1f}ms | Memory: {mem:.1f}MB{info_str}",
          flush=True)
    return elapsed_ms
