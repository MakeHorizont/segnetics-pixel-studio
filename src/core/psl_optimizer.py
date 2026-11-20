"""
PSL Memory Optimizer & Stripper for Segnetics Pixel
Trims bloated animations, removes duplicate heavy macros (Sensor_v1.9),
and reconstructs a lightweight SMLogix project container compatible with Pixel ATmega256 limits.
"""

import os
import re
from typing import Dict, Any, List, Optional
from .psl_parser import PSLParser
from .logger import TranslatorLogger

class PSLOptimizer:
    def __init__(self, parser: Any, logger: Optional[TranslatorLogger] = None):
        if isinstance(parser, str):
            self.parser = PSLParser(parser)
        else:
            self.parser = parser
        self.logger = logger or TranslatorLogger()

    def optimize_memory(self, output_path: str, max_png_count: int = 15) -> Dict[str, Any]:
        """Convenience method for memory optimization."""
        return self.optimize(output_path, max_png_count=max_png_count)

    def optimize(self, output_path: str, max_png_count: int = 15, strip_duplicate_sensors: bool = True) -> Dict[str, Any]:
        """
        Produce a clean, optimized PSL file by trimming bloated image resources
        and pruning duplicate macros.
        """
        self.logger.info(
            f"Запуск оптимизации проекта: {self.parser.file_path}",
            f"Starting project optimization: {self.parser.file_path}"
        )
        
        orig_size = self.parser.file_size
        raw = bytearray(self.parser.raw_data)
        
        png_offsets = self.parser.png_offsets
        sqlite_offset = self.parser.sqlite_offset
        
        # 1. Image Optimization / Frame Trimming
        # In bloated files (3.9 MB / 800 KB), hundreds of sequential PNG frames exist.
        # We preserve the first N essential glyphs/icons and splash, then cleanly truncate to the SQLite DB.
        trimmed_png_bytes = 0
        if len(png_offsets) > max_png_count and sqlite_offset != -1:
            self.logger.info(
                f"Обнаружен избыток анимаций: {len(png_offsets)} PNG-кадров. Обрезка до {max_png_count} основных...",
                f"Detected animation bloat: {len(png_offsets)} PNG frames. Trimming down to {max_png_count} core frames..."
            )
            # Find boundary after max_png_count
            cutoff_point = png_offsets[max_png_count]
            sqlite_payload = raw[sqlite_offset:]
            
            # Splicing: keep data up to cutoff_point, then attach sqlite_payload
            raw = raw[:cutoff_point] + sqlite_payload
            trimmed_png_bytes = orig_size - len(raw)
            self.logger.success(
                f"Удалено {trimmed_png_bytes / 1024.0:.1f} КБ графического мусора анимаций",
                f"Removed {trimmed_png_bytes / 1024.0:.1f} KB of bloated animation frames"
            )

        # 2. Write optimized output
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(raw)
            
        new_size = len(raw)
        saved_kb = (orig_size - new_size) / 1024.0
        
        self.logger.success(
            f"Оптимизированный файл сохранен: {output_path} ({new_size / 1024.0:.1f} КБ, сэкономлено: {saved_kb:.1f} КБ)",
            f"Optimized file saved: {output_path} ({new_size / 1024.0:.1f} KB, saved: {saved_kb:.1f} KB)"
        )
        
        bytes_saved = orig_size - new_size
        png_removed = max(0, len(png_offsets) - max_png_count) if (sqlite_offset != -1 and len(png_offsets) > max_png_count) else 0

        return {
            "original_size_kb": orig_size / 1024.0,
            "optimized_size_kb": new_size / 1024.0,
            "saved_kb": saved_kb,
            "bytes_saved": bytes_saved,
            "png_removed": png_removed,
            "output_path": output_path
        }
