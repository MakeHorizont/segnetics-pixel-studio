"""
Bilingual Logger for Segnetics Pixel Translator
Supports Russian and English console output and file logging with timestamps.
"""

import os
import sys
import datetime


class TranslatorLogger:
    def __init__(self, log_dir="logs", lang="ru"):
        self.lang = lang.lower()
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(self.log_dir, f"build_{timestamp}.log")
        self._file_handle = open(self.log_file, "w", encoding="utf-8")

        self.info(
            f"=== Сеанс транслятора запущен / Translator Session Started: {datetime.datetime.now().isoformat()} ==="
        )

    def _write(self, level, text_ru, text_en=None):
        msg = text_ru if self.lang == "ru" else (text_en or text_ru)
        dual_msg = (
            f"{text_ru} | {text_en}" if text_en and text_en != text_ru else text_ru
        )
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        console_line = f"[{timestamp}] [{level}] {msg}"
        file_line = f"[{timestamp}] [{level}] {dual_msg}\n"

        print(console_line)
        self._file_handle.write(file_line)
        self._file_handle.flush()

    def info(self, text_ru, text_en=None):
        self._write("INFO", text_ru, text_en)

    def success(self, text_ru, text_en=None):
        self._write("SUCCESS", text_ru, text_en)

    def warning(self, text_ru, text_en=None):
        self._write("WARN", text_ru, text_en)

    def error(self, text_ru, text_en=None):
        self._write("ERROR", text_ru, text_en)

    def close(self):
        if self._file_handle and not self._file_handle.closed:
            self._file_handle.close()


def setup_logger(
    name: str = "Segnetics", log_dir: str = "logs", lang: str = "ru"
) -> TranslatorLogger:
    """Helper factory for creating a TranslatorLogger instance."""
    return TranslatorLogger(log_dir=log_dir, lang=lang)
