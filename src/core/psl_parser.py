"""
PSL Binary Parser & Extractor for Segnetics SMLogix Projects
Parses MFC CArchive containers, extracts nested FBD macros, SMArt assets, and SQLite DB.
"""

import os
import re
import struct
import sqlite3
from typing import Dict, List, Any, Optional

class PSLParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Project file not found: {file_path}")
        
        with open(file_path, "rb") as f:
            self.raw_data = f.read()
        
        self.file_size = len(self.raw_data)
        self.header = self._parse_header()
        self.subdocs = self._find_subdocs()
        self.sqlite_offset = self._find_sqlite_offset()
        self.png_offsets = self._find_png_offsets()
        self.bmp_offsets = self._find_bmp_offsets()

    def _parse_header(self) -> Dict[str, Any]:
        magic = self.raw_data[:28]
        is_psl = b"@S M   L o g i x   P r o j e c t" in magic
        return {
            "magic": magic,
            "is_valid_smlogix": is_psl,
            "file_size": self.file_size
        }

    def _find_subdocs(self) -> List[int]:
        """Find start offsets of all nested FBD macro documents."""
        return [m.start() for m in re.finditer(b"@S M   L o g i x", self.raw_data)]

    def _find_sqlite_offset(self) -> int:
        """Find offset of embedded SQLite database."""
        return self.raw_data.find(b"SQLite format 3")

    def _find_png_offsets(self) -> List[int]:
        """Find offsets of all embedded PNG images."""
        return [m.start() for m in re.finditer(b"\x89PNG", self.raw_data)]

    def _find_bmp_offsets(self) -> List[int]:
        """Find offsets of all embedded BMP bitmaps."""
        return [m.start() for m in re.finditer(b"BM", self.raw_data)]

    def extract_sqlite_db(self, out_path: str) -> bool:
        """Extract embedded SQLite database to a standalone file."""
        if self.sqlite_offset == -1:
            return False
        db_bytes = self.raw_data[self.sqlite_offset:]
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(db_bytes)
        return True

    def extract_smart_variables(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract all SMArt variable bindings and GUIDs from macro headers and strings.
        Maps variable names to their GUIDs and types.
        """
        variables = {}
        # Find 32-character hexadecimal GUIDs commonly used in SMLogix / SMArt
        guid_pattern = re.compile(rb'[0-9A-Fa-f]{32}')
        
        # Scan through sub-documents to find variable macros
        for i, pos in enumerate(self.subdocs):
            end_pos = self.subdocs[i+1] if i+1 < len(self.subdocs) else pos + 5000
            chunk = self.raw_data[pos:end_pos]
            
            # Find UTF-16 strings
            u16 = chunk.decode("utf-16le", errors="ignore")
            strs = [s.strip() for s in re.findall(r'[\u0400-\u04FF\w\.\-\:\s]{3,}', u16) if re.search(r'[\u0400-\u04FFa-zA-Z]', s)]
            clean_strs = [s for s in strs if "Logix" not in s and "FBDprog" not in s and "Project" not in s]
            
            guids = [m.group(0).decode() for m in guid_pattern.finditer(chunk)]
            
            if clean_strs and guids:
                var_name = clean_strs[0]
                variables[var_name] = {
                    "subdoc_index": i,
                    "offset": pos,
                    "size": len(chunk),
                    "guid": guids[0],
                    "all_guids": list(set(guids)),
                    "labels": clean_strs
                }
        
        return variables

    def get_main_fbd_range(self) -> (int, int):
        """
        Estimate byte range of the Main FBD canvas.
        Main FBD is located between the last macro sub-document and the start of image assets.
        """
        if not self.subdocs:
            return 0, 0
        
        # The main FBD canvas follows the last macro
        last_macro_pos = self.subdocs[-1]
        
        # End is before PNGs or SQLite
        end_pos = self.file_size
        if self.png_offsets:
            end_pos = min(end_pos, self.png_offsets[0])
        elif self.sqlite_offset != -1:
            end_pos = min(end_pos, self.sqlite_offset)
            
        return last_macro_pos, end_pos
