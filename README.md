# Segnetics Pixel Studio

Universal development toolkit, memory optimizer, and interactive digital twin emulator for Segnetics Pixel programmable logic controllers (Pixel 12xx and 25xx series with ATmega2560 architecture).

---

## Capabilities

1. **PSL Project Audit & Optimization**
   - Structural analysis of binary `.psl` and `.bk1` project files.
   - Verification against ATmega2560 hardware boundaries (256 KB Flash, 32 KB SRAM, 4 KB EEPROM).
   - Automated removal of redundant animation bitmap bloat, reducing project footprint and resolving string constants memory overflow.

2. **Declarative FBD DSL Engine**
   - Construction of automation algorithms via Python DSL without manual diagram dragging.
   - Support for standard function blocks: logic (AND, OR, NOT, XOR), arithmetic (ADD, SUB, MUL, DIV), comparators (CMP, EQ, NE, GT, GE, LT, LE), timers (TON, TOF, TP), counters (CTU, CTD), latches (RS, SR), and multiplexers (MUX, SEL).
   - Cycle-accurate topological FBD execution runtime.

3. **Digital Twin Web Emulator**
   - Front-panel emulation with STN LCD matrix rendering, tactile button inputs (ESC, Right, Up, Down, OK), and diagnostic LEDs.
   - Live FBD Signal Watcher (analogous to F9 online mode in SMLogix).
   - Time-travel debugging with interactive history scrubber.
   - Integrated Modbus TCP server (default port 15502) and HTTP UI (port 18088) with auto-resilient port selection.
   - Interactive sensor and digital IO forcing panel.
   - Preloaded application templates: Pump Station with lead-lag alternation, Ventilation AHU with supply air temperature control, and Dual-Loop Thermostat.

---

## Quick Start

### 1. Requirements
- Python 3.8 or newer.

### 2. Launching via Windows Batch
Double-click:
```cmd
run_pixel_studio.bat
```
Select `[1]` to launch the web studio at `http://localhost:18088`.

### 3. Command Line Interface

```bash
# Launch digital twin emulator
python -m src.pixel_studio.cli simulate --port 18088 --modbus-port 15502

# Audit project file memory limits
python -m src.pixel_studio.cli audit path/to/project.psl

# Optimize project and strip graphic bloat
python -m src.pixel_studio.cli optimize input.psl output_clean.psl --max-png 15

# Export FBD logic structure to JSON
python -m src.pixel_studio.cli export-logic project.psl --out logic.json
```

---

## Testing

Run the automated test suite:
```bash
python run_tests.py
```
