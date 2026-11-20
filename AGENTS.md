# AGENTS.md — Developer and AI Agent Architecture Guide

This document defines architectural invariants, coding conventions, operational protocols, and extension workflows for human contributors and autonomous AI agents working within **Segnetics Pixel Studio**.

---

## 1. Project Overview & Architectural Boundaries

Segnetics Pixel Studio is divided into two distinct layers:

```
Segnetics_Pixel_Studio/
├── src/
│   ├── core/                  # Domain-independent PLC compilation and runtime engine
│   │   ├── dsl_models.py      # Declarative FBD graph models (Program, Block, Wire, Pin)
│   │   ├── fbd_runtime.py     # Deterministic cycle-by-cycle FBD execution engine
│   │   ├── psl_parser.py      # Binary parser for SMLogix .psl and .bk1 archives
│   │   ├── psl_analyzer.py    # ATmega2560 hardware resource audit (Flash, SRAM, EEPROM)
│   │   ├── psl_optimizer.py   # Animation bloat stripper and memory compressor
│   │   ├── modbus_server.py   # Resilient Modbus TCP slave server
│   │   ├── virtual_serial_bridge.py # Serial/COM port bridge abstraction
│   │   └── logger.py          # Structured multi-level logger
│   └── pixel_studio/          # Digital twin web emulator and CLI
│       ├── cli.py             # Studio CLI entrypoint (simulate, audit, optimize, export)
│       ├── studio_simulator.py# HTTP server, state container, front panel Web UI
│       ├── sample_programs.py # Built-in reference projects (Pump, Vent, Thermostat)
│       ├── layout_config.json # Calibrated front panel button and LED coordinates
│       └── static/            # Photorealistic chassis graphics and button tactile sprites
├── tests/                     # Unit and integration test suite (100% autonomous)
├── run_pixel_studio.bat       # Windows interactive launcher
├── run_tests.py               # Standalone test runner
└── requirements.txt           # Python dependencies (Standard library + optional pymodbus)
```

---

## 2. Fundamental Invariants (Strict Rules)

1. **Zero-Host-Assumption (Rule 17):**
   * Never hardcode absolute paths (`C:\`, `D:\`, `/home/`).
   * Compute file paths relative to `Path(__file__).resolve().parent` in Python or `%~dp0` in Windows batch scripts.
   * Tests must execute independently on any machine (Linux, macOS, Windows) without external file dependencies.

2. **Deterministic Topological Execution:**
   * In `fbd_runtime.py`, blocks execute in topological dependency order within each scan cycle.
   * Feedback loops must be broken across scan cycles using latches (`RS`, `SR`) or state registers.

3. **Resilient Multi-Port Discovery (Rule 4):**
   * Local servers (HTTP and Modbus TCP) must never crash with `EADDRINUSE` or `WinError 10048`.
   * When a default port (e.g., 18088 or 15502) is occupied, the application must sequentially search for the next available port using `find_available_port()`.

4. **Fail-Fast Error Handling (Rule 16):**
   * Never mask errors with bare `except: pass` or return synthetic dummy values (`null`, `[]`, `{}`).
   * If a parse or calculation step fails, raise an explicit exception with actionable diagnostic context.

5. **Text Hygiene:**
   * Use straight double quotes (`"`) and hyphens (`-`).
   * Avoid em-dashes and typographer quotes.

---

## 3. Testing & Verification Protocol

Before committing any modifications, agents MUST run the full test suite and confirm that all tests pass:

```bash
python run_tests.py
```

* Expected outcome: 19/19 tests pass in under 0.5 seconds.
* Tests cover: block mathematical accuracy, latch edge triggers, multi-layer arithmetic propagation, timer accumulation, project switching, state serialization, and memory optimization.

---

## 4. Extension Recipes for Agents

### Recipe A: Adding a New FBD Block Type
1. Define the block type and default inputs in `src/core/dsl_models.py` (`FBDBlock`).
2. Add the block evaluation logic in `src/core/fbd_runtime.py` inside `FBDRuntime.evaluate_block()`.
3. Add a unit test verifying truth tables or transfer functions in `tests/test_fbd_blocks.py`.
4. Run `python run_tests.py` to confirm verification.

### Recipe B: Adding a New Reference Application
1. In `src/pixel_studio/sample_programs.py`, create a function `create_<name>_program() -> FBDProgram`.
2. Register the program in `StudioSimulatorState.__init__()` inside `src/pixel_studio/studio_simulator.py`.
3. Add a project option in the `<select id="project-select">` dropdown in `studio_simulator.py`.
4. Add a test in `tests/test_pixel_studio.py` verifying state switching and IO re-binding.

### Recipe C: Modifying Front Panel Button Hitboxes
1. Never edit hardcoded percentages in Python.
2. Edit `src/pixel_studio/layout_config.json` directly or use the Layout Editor modal in the browser.
3. Verification is preserved via `test_layout_config_roundtrip` in `tests/test_studio_simulator.py`.

---

## 5. CLI Quick Reference for Automated Tasks

```bash
# Launch emulator daemon on background ports
python -m src.pixel_studio.cli simulate --port 18088 --modbus-port 15502

# Run non-interactive memory audit on a .psl file
python -m src.pixel_studio.cli audit <path_to_file.psl>

# Optimize and strip animations with custom retention count
python -m src.pixel_studio.cli optimize <input.psl> <output.psl> --max-png 10

# Export logic graph to JSON
python -m src.pixel_studio.cli export-logic <input.psl> --out <graph.json>

# Extract SQLite3 database from .psl
python -m src.pixel_studio.cli export-smart <input.psl> --out-dir <output_directory>
```
