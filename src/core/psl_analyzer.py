"""
PSL Analyzer & Memory Auditor for Segnetics Pixel (ATmega256)
Analyzes memory footprint, detects bloat (ghost macros, redundant PNG animations),
and validates compatibility with Segnetics Pixel 2514 hardware limits.
"""

from typing import Dict, Any, List
from .psl_parser import PSLParser

# Segnetics Pixel 2514-02-00 hardware specifications
PIXEL_SPEC = {
    "model": "Pixel 2514-02-00",
    "mcu": "Atmel ATmega2560",
    "flash_kb": 256,
    "ram_total_kb": 32,      # 8KB internal SRAM + 32KB external SRAM
    "ram_usable_runtime_kb": 28,
    "eeprom_kb": 4,          # Retained variables
    "max_recommended_project_kb": 150, # SMLogix safe project file size
    "max_safe_png_count": 15,
}

class PSLAnalyzer:
    def __init__(self, parser: Any):
        if isinstance(parser, str):
            self.parser = PSLParser(parser)
        else:
            self.parser = parser

    def audit(self) -> Dict[str, Any]:
        """Run complete audit and return health metrics, warnings and recommendations."""
        file_kb = self.parser.file_size / 1024.0
        png_count = len(self.parser.png_offsets)
        subdoc_count = len(self.parser.subdocs)
        
        # Calculate image payload size
        img_payload_kb = 0
        if self.parser.png_offsets:
            first_png = self.parser.png_offsets[0]
            last_png = self.parser.png_offsets[-1]
            img_payload_kb = (last_png - first_png + 5000) / 1024.0
            
        # Detect Sensor_v1.9 duplicate macros
        raw_text = self.parser.raw_data.decode("utf-16le", errors="ignore")
        sensor_macro_count = raw_text.count("Sensor_v1.9") // 2 # each macro mentions itself at least twice
        ectd_macro_count = raw_text.count("eCTD") // 2
        
        # Determine risks
        risks = []
        if file_kb > PIXEL_SPEC["max_recommended_project_kb"]:
            risks.append({
                "level": "CRITICAL",
                "code": "MEM_OVERFLOW",
                "title_ru": "Превышение лимита памяти Pixel",
                "title_en": "Pixel Memory Limit Exceeded",
                "desc_ru": f"Размер проекта {file_kb:.1f} КБ превышает безопасный порог {PIXEL_SPEC['max_recommended_project_kb']} КБ. Контроллер ATmega256 выдаст 'Недостаточно памяти для проекта'.",
                "desc_en": f"Project size {file_kb:.1f} KB exceeds safe threshold {PIXEL_SPEC['max_recommended_project_kb']} KB. ATmega256 MCU will trigger 'Not enough memory for project'."
            })
            
        if png_count > PIXEL_SPEC["max_safe_png_count"]:
            risks.append({
                "level": "CRITICAL",
                "code": "ANIM_BLOAT",
                "title_ru": "Критический избыток анимаций SMArt",
                "title_en": "Critical SMArt Animation Bloat",
                "desc_ru": f"В проекте обнаружено {png_count} PNG-кадров (~{img_payload_kb:.1f} КБ). На экране 128x64 это вызывает коллапс таблицы ресурсов.",
                "desc_en": f"Detected {png_count} PNG frames (~{img_payload_kb:.1f} KB). On a 128x64 display, this crashes the resource table."
            })
            
        if sensor_macro_count > 1:
            risks.append({
                "level": "HIGH",
                "code": "DUPLICATE_MACROS",
                "title_ru": "Дублирование тяжелых макросов Sensor_v1.9",
                "title_en": "Duplicate Heavy Sensor_v1.9 Macros",
                "desc_ru": f"Обнаружено {sensor_macro_count} копий макроса Sensor_v1.9. Каждая копия дублирует 110 КБ таблиц интерполяции и строк.",
                "desc_en": f"Detected {sensor_macro_count} instances of Sensor_v1.9. Each instance duplicates 110 KB of ADC interpolation tables and string constants."
            })

        variables = self.parser.extract_smart_variables()
        
        return {
            "file_size_kb": file_kb,
            "subdoc_count": subdoc_count,
            "png_count": png_count,
            "bmp_count": len(self.parser.bmp_offsets),
            "sensor_macro_count": sensor_macro_count,
            "ectd_macro_count": ectd_macro_count,
            "has_sqlite_db": self.parser.sqlite_offset != -1,
            "extracted_variables_count": len(variables),
            "variables": list(variables.keys()),
            "risks": risks,
            "is_pixel_compatible": len(risks) == 0
        }

    def run_full_audit(self) -> str:
        """Run audit and format as human-readable report string."""
        data = self.audit()
        lines = [
            "=" * 76,
            "  РЕЗУЛЬТАТЫ АУДИТА ПАМЯТИ SEGNETICS PIXEL (ATmega2560)",
            "=" * 76,
            f"  Файл проекта:          {self.parser.file_path}",
            f"  Размер файла:          {data['file_size_kb']:.1f} КБ (рекомендуемый лимит: {PIXEL_SPEC['max_recommended_project_kb']} КБ)",
            f"  Кадров PNG анимаций:   {data['png_count']} (безопасный лимит: {PIXEL_SPEC['max_safe_png_count']})",
            f"  Субдокументов SMLogix: {data['subdoc_count']}",
            f"  Макросов Sensor_v1.9:  {data['sensor_macro_count']} экз.",
            f"  Переменных SMArt:      {data['extracted_variables_count']} шт.",
            f"  База данных SQLite:    {'Присутствует' if data['has_sqlite_db'] else 'Отсутствует'}",
            "-" * 76,
        ]
        if data["risks"]:
            lines.append("  ОБНАРУЖЕННЫЕ РИСКИ И УЗКИЕ МЕСТА:")
            for r in data["risks"]:
                lines.append(f"  * [{r['level']}] {r['title_ru']}")
                lines.append(f"    -> {r['desc_ru']}")
        else:
            lines.append("  ✓ Все параметры проекта в пределах заводских норм Segnetics Pixel 2514.")
        lines.append("-" * 76)
        verdict = "СОВМЕСТИМ" if data["is_pixel_compatible"] else "ТРЕБУЕТ ОПТИМИЗАЦИИ"
        lines.append(f"  ИТОГОВЫЙ СТАТУС: {verdict}")
        lines.append("=" * 76)
        return "\n".join(lines)
