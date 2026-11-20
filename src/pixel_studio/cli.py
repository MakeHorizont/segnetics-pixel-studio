"""
Segnetics Pixel Studio - Universal Command Line Interface
Engineering suite for compiling, optimizing memory, simulating, and auditing Segnetics Pixel PLCs.
"""

import sys
import argparse
from ..core.logger import setup_logger
from ..core.psl_parser import PSLParser
from ..core.psl_analyzer import PSLAnalyzer
from ..core.psl_optimizer import PSLOptimizer
from .studio_simulator import start_studio_server

logger = setup_logger("PixelStudioCLI")


def print_flash_help():
    print("""
============================================================================
  ИНСТРУКЦИЯ: ЗАЛИВКА ПРОГРАММЫ В РЕАЛЬНЫЙ КОНТРОЛЛЕР SEGNETICS PIXEL 2514
============================================================================

1. АППАРАТНАЯ СВЯЗЬ:
   - Segnetics Pixel 2514 построен на базе ATmega2560 и прошивается
     через промышленный последовательный интерфейс RS-485.
   - Подключите адаптер USB-RS485 (например, BOLID USB-RS485, ОВЕН или Segnetics):
     * Клемма A (RS-485+) адаптера -> клемма '+' интерфейса RS-485 Pixel.
     * Клемма B (RS-485-) адаптера -> клемма '-' интерфейса RS-485 Pixel.
     * Если используется длинная линия, подключите общий провод к GND / Экран.

2. ДИСПЕТЧЕР УСТРОЙСТВ WINDOWS:
   - Вставьте USB-RS485 в компьютер.
   - Откройте Диспетчер устройств -> Порты (COM и LPT).
   - Найдите виртуальный COM-порт (например, COM3 или COM4).

3. ЗАГРУЗКА ЧЕРЕЗ SMLOGIX:
   - Шаг 1: Оптимизируйте ваш проект командой:
     pixel-studio optimize "my_project.psl" "my_project_clean.psl"
   - Шаг 2: Откройте созданный файл в заводской среде SMLogix.
   - Шаг 3: Нажмите клавишу F7 (или меню: Контроллер -> Поиск).
   - Шаг 4: Выберите COM-порт вашего адаптера BOLID (например, COM3),
     скорость 115200 бит/с (или 9600), сетевой адрес 1.
   - Шаг 5: Нажмите 'Записать проект' (Ctrl+F7).

Все! Программа записана в энергонезависимую Flash и EEPROM память Pixel 2514.
============================================================================
""")


def main():
    parser = argparse.ArgumentParser(
        description="Segnetics Pixel Studio - Universal PLC Development Suite"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 1. Simulate
    sim_p = subparsers.add_parser("simulate", help="Launch interactive Pixel Studio web emulator")
    sim_p.add_argument("--port", type=int, default=18088, help="Web UI HTTP port")
    sim_p.add_argument("--modbus-port", type=int, default=15502, help="Modbus TCP port")

    # 2. Audit
    audit_p = subparsers.add_parser("audit", help="Audit memory footprint of a .psl project")
    audit_p.add_argument("psl_file", help="Path to .psl project file")

    # 3. Optimize
    opt_p = subparsers.add_parser("optimize", help="Strip bloated assets and optimize .psl memory")
    opt_p.add_argument("input_psl", help="Source .psl file")
    opt_p.add_argument("output_psl", help="Target optimized .psl file")
    opt_p.add_argument("--max-png", type=int, default=15, help="Maximum embedded PNG images to retain")

    # 4. Export logic
    export_p = subparsers.add_parser("export-logic", help="Export FBD logic blocks from .psl to JSON")
    export_p.add_argument("psl_file", help="Path to .psl project file")
    export_p.add_argument("--out", default="logic_graph.json", help="Output JSON path")

    # 5. Export SMArt
    smart_p = subparsers.add_parser("export-smart", help="Extract SMArt screens and assets from .psl")
    smart_p.add_argument("psl_file", help="Path to .psl project file")
    smart_p.add_argument("--out-dir", default="extracted_smart", help="Output directory")

    # 6. Flash Help
    subparsers.add_parser("flash-help", aliases=["flash-guide"], help="How to flash physical Pixel 2514 via RS-485")

    args = parser.parse_args()

    if args.command == "simulate":
        print("=" * 76)
        print("=== SEGNETICS PIXEL STUDIO: UNIVERSAL HARDWARE EMULATOR ===")
        print("=" * 76)
        http_port, mb_port = start_studio_server(
            base_port=args.port, base_modbus_port=args.modbus_port
        )
        import time
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nОстановка Segnetics Pixel Studio.")

    elif args.command == "audit":
        parser_psl = PSLParser(args.psl_file)
        analyzer = PSLAnalyzer(parser_psl)
        report = analyzer.run_full_audit()
        print(report)

    elif args.command == "optimize":
        optimizer = PSLOptimizer(args.input_psl)
        report = optimizer.optimize_memory(args.output_psl, max_png_count=args.max_png)
        print(f"✓ Оптимизация завершена! Сохранено в: {args.output_psl}")
        print(f"  Удалено PNG изображений: {report.get('png_removed', 0)}")
        print(f"  Сэкономлено байт: {report.get('bytes_saved', 0)}")

    elif args.command == "export-logic":
        parser_psl = PSLParser(args.psl_file)
        import json
        tree = parser_psl.get_summary()
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(tree, f, indent=2, ensure_ascii=False)
        print(f"✓ Граф логики экспортирован в: {args.out}")

    elif args.command == "export-smart":
        parser_psl = PSLParser(args.psl_file)
        parser_psl.export_smart_assets(args.out_dir)
        print(f"✓ Ресурсы SMArt успешно извлечены в папку: {args.out_dir}")

    elif args.command in ("flash-help", "flash-guide"):
        print_flash_help()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
