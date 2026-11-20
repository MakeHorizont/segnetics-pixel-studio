# Segnetics Pixel Studio

**English** | [Русский](README_RU.md)

Open-source development toolkit, memory optimizer, and interactive digital twin emulator for **Segnetics Pixel** programmable logic controllers (Pixel 12xx and 25xx series powered by the ATmega2560 microarchitecture).

Eliminates the critical SMLogix memory overflow defect (*"Error loading string constants. Insufficient memory for project"*) and provides an authentic hardware-free digital twin for building, compiling, and validating FBD automation logic in real time.

---

## Capabilities

### 1. SMLogix Project Audit & Optimization (`audit`, `optimize`)
* **Hardware Memory Audit:** deep binary inspection of `.psl` and `.bk1` project archives against ATmega2560 hardware thresholds (256 KB Flash, 32 KB SRAM, 4 KB EEPROM).
* **Automated Asset Trimming:** discovers and strips duplicate SMArt animation frames down to essential system glyphs, reducing project file weight by 60–75% without corrupting menu layouts or string tables.
* **Resource Extraction (`export-smart`, `export-logic`):** exports internal SQLite3 screen databases (`translation`, `language`, `composite`) and converts functional block connectivity into JSON graphs.

### 2. Declarative FBD DSL Engine (`src/core/`)
* **Python-first Logic Design:** construct industrial automation graphs via declarative Python code instead of manual canvas wiring.
* **Block Library (20+ types):**
  * Boolean logic: `AND`, `OR`, `NOT`, `XOR`;
  * Arithmetic: `ADD`, `SUB`, `MUL`, `DIV` (with divide-by-zero hardware traps);
  * Comparators: `CMP`, `EQ`, `NE`, `GT`, `GE`, `LT`, `LE`;
  * Timers and counters: `TON`, `TOF`, `TP`, `CTU`, `CTD`;
  * Memory latches: `RS` (reset-dominant), `SR` (set-dominant);
  * Multiplexing: `MUX`, `SEL`, `LIMIT`.
* **Cycle-Accurate Topological Runtime (`fbd_runtime.py`):** deterministic single-scan dataflow propagation modeling real PLC task execution cycles.

### 3. Digital Twin Web Emulator (`src/pixel_studio/`)
* **Photorealistic Pixel 2514 Enclosure:** authentic front panel, STN matrix LCD emulator, tactile navigation buttons (ESC, Right, Up, Down, OK), and DO/Alarm LED indicators.
* **Time-Travel Scrubber:** interactive timeline slider allowing engineers to scrub backward in time and inspect how logic states, screen lines, and relays behaved during earlier steps.
* **Live FBD Signal Inspector (F9 Online Watch):** real-time monitor displaying live values across every block pin, wire, and constant.
* **Hardware IO Forcing:** override digital inputs `DI 0..5` and analog transmitters `AI 0..2` via real-time sliders and toggle switches.
* **Time Warp Simulation:** accelerate virtual time from 1x (real-time) to 10x, 60x (1s = 1m), 600x, 3600x (1s = 1h), or pause execution.
* **Hard Factory Reset:** complete state zeroing guarded by a modal token confirmation dialog (`reset` or `сброс`).
* **Embedded Modbus TCP Slave:** integrated Modbus server on port `15502` (Unit ID: 1) with auto-resilient port failover, enabling plug-and-play connection to SCADA, Home Assistant, or Node-RED.
* **Built-in Application Templates:** Dual Pump Station with duty rotation and dry-run interlock, Ventilation AHU with supply air temperature control, and Dual-Loop Thermostat.

---

## Quick Start

### Prerequisites
* Operating System: Windows, Linux, or macOS;
* Python 3.8 or higher.

### Windows One-Click Launcher
Double-click:
```cmd
run_pixel_studio.bat
```
Select `[1]` to launch the web studio at `http://localhost:18088`.

### Command Line Interface (CLI)

```bash
# 1. Launch web studio and Modbus TCP server
python -m src.pixel_studio.cli simulate --port 18088 --modbus-port 15502

# 2. Audit a .psl project for ATmega2560 memory overflow
python -m src.pixel_studio.cli audit path/to/project.psl

# 3. Strip animation bloat and compress memory
python -m src.pixel_studio.cli optimize source.psl clean.psl --max-png 15

# 4. Export FBD logic structure to JSON
python -m src.pixel_studio.cli export-logic project.psl --out logic.json

# 5. Extract SMArt SQLite database and screens
python -m src.pixel_studio.cli export-smart project.psl --out-dir extracted_smart
```

---

## Automated Verification

Run the test suite to verify block math, topology resolution, timers, and simulator APIs:
```bash
python run_tests.py
```
All 19 tests complete in ~0.25 seconds.

---

## Hardware Flashing via RS-485

1. Connect a USB-to-RS485 adapter (BOLID, Segnetics, ICP DAS, etc.) to the Pixel RS-485 port:
   * Adapter terminal A (RS-485+) $\to$ Pixel terminal `+`;
   * Adapter terminal B (RS-485-) $\to$ Pixel terminal `-`;
   * Cable shield $\to$ Pixel terminal GND.
2. Optimize your project:
   ```bash
   python -m src.pixel_studio.cli optimize project.psl project_clean.psl
   ```
3. Open `project_clean.psl` in **SMLogix**.
4. Press `Ctrl+F7` to flash the project onto the controller. The upload will proceed smoothly without memory exhaustion errors.

---

## For AI Agents and Contributors

Refer to [AGENTS.md](AGENTS.md) for architectural invariants, testing protocols, and guidelines on extending blocks and simulator features.
