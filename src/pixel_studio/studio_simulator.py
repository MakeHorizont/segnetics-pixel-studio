"""
Universal Segnetics Pixel 2514 Studio & Digital Twin Hardware Emulator.
Provides an authentic web-based emulator for any arbitrary FBD program,
with Pixel 2514 chassis, STN LCD screen, full terminal board (DO, DI, AI, AO),
live FBD block inspection (equivalent to F9 in SMLogix), interactive layout editor,
time-travel history scrubber, event log console, factory reset, and Modbus TCP server.
"""

import os
import json
import time
import socket
import mimetypes
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Any, Tuple

from ..core.dsl_models import FBDProgram
from ..core.fbd_runtime import FBDRuntime
from ..core.modbus_server import ModbusTCPServer
from .sample_programs import (
    create_pump_station_program,
    create_ventilation_ahu_program,
    create_thermostat_pid_program,
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
LAYOUT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "layout_config.json")

DEFAULT_LAYOUT = {
    "screen": {"left": 20.8, "top": 34.6, "width": 55.7, "height": 18.0},
    "buttons_row_top": 59.5,
    "buttons_width": 10.4,
    "buttons_height": 11.5,
    "buttons": {
        "esc": {"left": 18.0, "top": 59.5},
        "right": {"left": 29.0, "top": 59.5},
        "up": {"left": 40.1, "top": 59.5},
        "down": {"left": 51.4, "top": 59.5},
        "ok": {"left": 62.6, "top": 59.5},
    },
    "alarm": {"left": 74.9, "top": 62.0, "width": 1.78, "height": 9.5},
}


def load_layout_config():
    if os.path.exists(LAYOUT_CONFIG_PATH):
        try:
            with open(LAYOUT_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = json.loads(json.dumps(DEFAULT_LAYOUT))
                if "screen" in data:
                    merged["screen"].update(data["screen"])
                if "buttons_row_top" in data:
                    merged["buttons_row_top"] = data["buttons_row_top"]
                if "buttons_width" in data:
                    merged["buttons_width"] = data["buttons_width"]
                if "buttons_height" in data:
                    merged["buttons_height"] = data["buttons_height"]
                if "buttons" in data:
                    for k, v in data["buttons"].items():
                        if k in merged["buttons"]:
                            merged["buttons"][k].update(v)
                if "alarm" in data:
                    merged["alarm"].update(data["alarm"])
                return merged
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULT_LAYOUT))


def save_layout_config(cfg):
    try:
        with open(LAYOUT_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print("Error saving layout config:", e)
        return False


class StudioSimulatorState:
    def __init__(self):
        self.programs: Dict[str, FBDProgram] = {
            "pump": create_pump_station_program(),
            "vent": create_ventilation_ahu_program(),
            "thermostat": create_thermostat_pid_program(),
        }
        self.active_prog_key = "pump"
        self.program = self.programs[self.active_prog_key]
        self.runtime = FBDRuntime(self.program)

        # Physical IO states
        self.di = [False] * 6
        self.ai = [0.0] * 6
        self.do = [False] * 3
        self.ao = [0.0] * 2

        self.virtual_time = 0.0
        self.time_multiplier = 1.0
        self.is_paused = False
        self.start_wall_time = time.time()

        self.http_port = 18088
        self.modbus_port = 15502
        self.last_action_msg = "Студия Segnetics Pixel готова к работе"

        # LCD Text representation
        self.lcd_title = "Segnetics Pixel 2514"
        self.lcd_lines = [
            "PIXEL 2514-02-00",
            "FBD STUDIO v2.5 ",
            "ПРОГРАММА: НАСОС",
            "[OK - Меню инж.]",
        ]

        # Time-Travel History & Human-readable Event Logs
        self.telemetry_history: List[Dict[str, Any]] = []
        self.event_logs: List[Dict[str, Any]] = []

        self.add_log("Система управления Segnetics Pixel 2514 инициализирована.", "info")
        self.add_log("Загружен типовой проект: Насосная станция (Lead-Lag).", "info")

    def add_log(self, msg: str, log_type: str = "info"):
        t_sec = int(self.virtual_time)
        hh = f"{t_sec // 3600:02d}"
        mm = f"{(t_sec % 3600) // 60:02d}"
        ss = f"{t_sec % 60:02d}"
        entry = {
            "time": f"{hh}:{mm}:{ss}",
            "v_sec": round(self.virtual_time, 1),
            "msg": msg,
            "type": log_type,
        }
        self.event_logs.append(entry)
        if len(self.event_logs) > 300:
            self.event_logs.pop(0)

    def hard_factory_reset(self):
        """Completely reset everything back to zero as if freshly booted."""
        self.virtual_time = 0.0
        self.start_wall_time = time.time()
        self.time_multiplier = 1.0
        self.is_paused = False

        self.di = [False] * 6
        self.ai = [0.0] * 6
        self.do = [False] * 3
        self.ao = [0.0] * 2

        # Re-initialize active program and runtime
        self.program = self.programs[self.active_prog_key]
        self.runtime = FBDRuntime(self.program)

        self.telemetry_history.clear()
        self.event_logs.clear()
        self.add_log("Выполнен полный сброс контроллера к заводскому состоянию.", "warn")
        self.last_action_msg = "Контроллер сброшен в ноль"

    def switch_program(self, key: str):
        if key in self.programs:
            self.active_prog_key = key
            self.program = self.programs[key]
            self.runtime = FBDRuntime(self.program)

            # Reset IO defaults for program
            if key == "pump":
                self.di = [True, False, False, False, False, False]
                self.ai = [2.5, 0.0, 0.0, 0.0, 0.0, 0.0]
                name = "НАСОСНАЯ СТАНЦИЯ"
            elif key == "vent":
                self.di = [True, False, False, False, False, False]
                self.ai = [18.0, 22.0, 0.0, 0.0, 0.0, 0.0]
                name = "ВЕНТИЛЯЦИЯ (AHU)"
            else:
                self.di = [True, False, False, False, False, False]
                self.ai = [24.0, 30.0, 0.0, 0.0, 0.0, 0.0]
                name = "ТЕРМОСТАТ ПИД"

            self.lcd_lines = [
                "PIXEL 2514-02-00",
                "ПРОЕКТ ЗАГРУЖЕН ",
                name,
                "FBD РАБОТАЕТ F9 ",
            ]
            self.add_log(f"Переключение на проект: {name}", "action")
            self.last_action_msg = f"Загружен проект: {name}"

    def tick(self, real_dt: float):
        if self.is_paused:
            return

        sim_dt = real_dt * self.time_multiplier
        self.virtual_time += sim_dt

        # Map DI / AI into FBD inputs
        for idx in range(6):
            self.runtime.inputs[f"di{idx}"] = self.di[idx]
            self.runtime.inputs[f"ai{idx}"] = self.ai[idx]

        # Execute FBD cycle
        self.runtime.step(sim_dt)

        # Read back outputs
        prev_do = list(self.do)
        for idx in range(3):
            self.do[idx] = bool(self.runtime.outputs.get(f"dou{idx}", False))
            if self.do[idx] != prev_do[idx]:
                state_str = "ВКЛЮЧЕН" if self.do[idx] else "ВЫКЛЮЧЕН"
                self.add_log(f"Выход DO{idx} {state_str}", "info")

        for idx in range(2):
            self.ao[idx] = float(self.runtime.outputs.get(f"aou{idx}", 0.0))

        # Record telemetry history for time travel scrubbing (every ~1s virtual time)
        if (
            len(self.telemetry_history) == 0
            or (self.virtual_time - self.telemetry_history[-1]["time"]) >= 1.0
        ):
            point = {
                "time": round(self.virtual_time, 1),
                "di": list(self.di),
                "ai": list(self.ai),
                "do": list(self.do),
                "ao": list(self.ao),
                "lcd_lines": list(self.lcd_lines),
            }
            self.telemetry_history.append(point)
            if len(self.telemetry_history) > 300:
                self.telemetry_history.pop(0)


STUDIO_STATE = StudioSimulatorState()

STUDIO_HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Segnetics Pixel Studio — Универсальный цифровой двойник и FBD отладчик</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0d0e12;
    color: #d1d5db;
    padding: 14px;
    font-size: 13px;
    user-select: none;
  }
  .top-navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #15171e;
    border: 1px solid #232734;
    border-radius: 8px;
    padding: 10px 16px;
    margin-bottom: 14px;
  }
  .nav-title { font-size: 15px; font-weight: bold; color: #f3f4f6; display: flex; align-items: center; gap: 8px; }
  .badge {
    background: #2563eb;
    color: #fff;
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 10px;
    text-transform: uppercase;
  }
  .ports-badge {
    display: inline-flex;
    gap: 12px;
    font-family: monospace;
    font-size: 11.5px;
    color: #9ca3af;
    align-items: center;
  }
  .port-pill {
    background: #1c202a;
    border: 1px solid #2d3345;
    padding: 3px 8px;
    border-radius: 4px;
    color: #38bdf8;
  }
  .btn-nav {
    background: #2563eb;
    color: #fff;
    border: none;
    padding: 5px 12px;
    border-radius: 5px;
    cursor: pointer;
    font-weight: 500;
    transition: background 0.15s;
  }
  .btn-nav:hover { background: #1d4ed8; }
  .btn-danger {
    background: #dc2626;
    color: #fff;
    border: none;
    padding: 5px 12px;
    border-radius: 5px;
    cursor: pointer;
    font-weight: 500;
  }
  .btn-danger:hover { background: #b91c1c; }

  .main-layout {
    display: grid;
    grid-template-columns: 565px 1fr;
    gap: 18px;
    align-items: start;
  }
  .chassis-stage {
    position: relative;
    width: 563px;
    height: 520px;
    background-image: url('/static/pixel_chassis.jpg');
    background-size: 563px 520px;
    background-repeat: no-repeat;
    border-radius: 6px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.85);
    border: 1px solid #222;
  }
  .lcd-aperture {
    position: absolute;
    left: 20.78%;
    top: 34.80%;
    width: 55.77%;
    height: 18.00%;
    background: #b2c9ad;
    border: 2px solid #1a2218;
    box-shadow: inset 0 0 10px rgba(0,0,0,0.65);
    border-radius: 2px;
    overflow: hidden;
    padding: 4px 6px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
  .lcd-header {
    font-family: monospace;
    font-size: 9.5px;
    color: #263821;
    font-weight: bold;
    border-bottom: 1px dashed rgba(38,56,33,0.4);
    padding-bottom: 2px;
    white-space: nowrap;
    overflow: hidden;
  }
  .lcd-matrix-text {
    font-family: 'Courier New', Courier, monospace;
    font-size: 13.5px;
    font-weight: bold;
    color: #0b1a07;
    line-height: 1.25;
    letter-spacing: 0.8px;
    white-space: pre-line;
    text-shadow: 1px 1px 0 rgba(255,255,255,0.2);
  }
  .btn-zone {
    position: absolute;
    width: 10.4%;
    height: 11.5%;
    cursor: pointer;
    background-size: contain;
    background-repeat: no-repeat;
    background-position: center;
  }
  .btn-esc   { background-image: url('/static/buttons/esc_up.png'); }
  .btn-esc:hover { background-image: url('/static/buttons/esc_over.png'); }
  .btn-esc:active { background-image: url('/static/buttons/esc_down.png'); }

  .btn-right { background-image: url('/static/buttons/right_up.png'); }
  .btn-right:hover { background-image: url('/static/buttons/right_over.png'); }
  .btn-right:active { background-image: url('/static/buttons/right_down.png'); }

  .btn-up    { background-image: url('/static/buttons/up_up.png'); }
  .btn-up:hover { background-image: url('/static/buttons/up_over.png'); }
  .btn-up:active { background-image: url('/static/buttons/up_down.png'); }

  .btn-down  { background-image: url('/static/buttons/down_up.png'); }
  .btn-down:hover { background-image: url('/static/buttons/down_over.png'); }
  .btn-down:active { background-image: url('/static/buttons/down_down.png'); }

  .btn-ok    { background-image: url('/static/buttons/ok_up.png'); }
  .btn-ok:hover { background-image: url('/static/buttons/ok_over.png'); }
  .btn-ok:active { background-image: url('/static/buttons/ok_down.png'); }

  .alarm-slot {
    position: absolute;
    background: #333;
    border-radius: 1px;
    transition: background 0.1s, box-shadow 0.1s;
  }
  .alarm-slot.on {
    background: #ef4444;
    box-shadow: 0 0 12px #ef4444, inset 0 0 4px #fff;
  }
  .alarm-slot.green {
    background: #22c55e;
    box-shadow: 0 0 10px #22c55e;
  }

  .terminal-leds {
    position: absolute;
    bottom: 22px;
    left: 45px;
    display: flex;
    gap: 18px;
    background: rgba(15,17,23,0.85);
    padding: 4px 10px;
    border-radius: 4px;
    border: 1px solid #333;
  }
  .led-item { display: flex; align-items: center; gap: 6px; font-family: monospace; font-size: 11px; }
  .lamp {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #262933;
    border: 1px solid #444;
  }
  .lamp.on.green { background: #22c55e; box-shadow: 0 0 8px #22c55e; }
  .lamp.on.red   { background: #ef4444; box-shadow: 0 0 8px #ef4444; }

  /* Right column */
  .panel-box {
    background: #15171e;
    border: 1px solid #232734;
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 14px;
  }
  .panel-header {
    font-weight: 600;
    font-size: 13px;
    color: #f3f4f6;
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .timewarp-bar {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .btn-speed {
    background: #1e2330;
    border: 1px solid #333c52;
    color: #94a3b8;
    padding: 5px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 11px;
    font-weight: 600;
  }
  .btn-speed.active {
    background: #2563eb;
    color: #fff;
    border-color: #3b82f6;
  }
  .toggle-switch {
    background: #1e2330;
    border: 1px solid #333c52;
    color: #94a3b8;
    padding: 4px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 11px;
    font-family: monospace;
  }
  .toggle-switch.on {
    background: #166534;
    color: #4ade80;
    border-color: #22c55e;
  }
  .slider-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    font-family: monospace;
    font-size: 12px;
  }
  .slider-row input[type=range] {
    flex: 1;
    accent-color: #38bdf8;
  }
  .slider-val {
    width: 60px;
    text-align: right;
    color: #38bdf8;
    font-weight: bold;
  }

  .fbd-table {
    width: 100%;
    border-collapse: collapse;
    font-family: monospace;
    font-size: 11px;
  }
  .fbd-table th, .fbd-table td {
    padding: 4px 8px;
    text-align: left;
    border-bottom: 1px solid #1f2430;
  }
  .fbd-table th { color: #64748b; font-weight: 600; }
  .val-true { color: #4ade80; font-weight: bold; }
  .val-false { color: #ef4444; }

  /* History Scrubber */
  .scrubber-container {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 10px;
    background: #12141a;
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid #232734;
  }
  .scrubber-slider {
    flex: 1;
    accent-color: #f59e0b;
  }
  .scrubber-badge {
    background: #78350f;
    color: #fde68a;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: bold;
  }

  /* Event Log Console */
  .log-console {
    background: #090a0d;
    border: 1px solid #1f2430;
    border-radius: 4px;
    height: 130px;
    overflow-y: auto;
    font-family: monospace;
    font-size: 11px;
    padding: 6px 10px;
    line-height: 1.45;
  }
  .log-item { margin-bottom: 3px; }
  .log-time { color: #64748b; margin-right: 6px; }
  .log-type-info { color: #38bdf8; }
  .log-type-warn { color: #fbbf24; }
  .log-type-action { color: #a78bfa; }

  /* Modal */
  .modal-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.75);
    z-index: 1000;
    justify-content: center;
    align-items: center;
  }
  .modal-card {
    background: #15171e;
    border: 1px solid #2d3345;
    border-radius: 8px;
    padding: 20px;
    width: 440px;
    max-width: 90%;
    color: #f3f4f6;
  }
</style>
</head>
<body>

<div class="top-navbar">
  <div class="nav-title">
    <span>Segnetics Pixel Studio 2514</span>
    <span class="badge">Digital Twin</span>
  </div>
  <div class="ports-badge">
    <span>Проект:</span>
    <select id="project-select" onchange="switchProject(this.value)" style="background:#1c202a; color:#f3f4f6; border:1px solid #2d3345; padding:3px 8px; border-radius:4px;">
      <option value="pump">Насосная станция (Lead-Lag)</option>
      <option value="vent">Вентиляция AHU (Supply PID)</option>
      <option value="thermostat">Термостат ПИД (Dual-Loop)</option>
    </select>
    <span>Web UI: <span class="port-pill">http://localhost:<span id="http-port">18088</span></span></span>
    <span>Modbus TCP: <span class="port-pill" id="modbus-port">15502</span></span>
    <span>Время: <span id="nav-clock" style="color:#e2e8f0;">00:00:00</span></span>
  </div>
  <div style="display:flex; gap:8px;">
    <button class="btn-nav" onclick="openLayoutEditor()">Редактор разметки</button>
    <button class="btn-danger" onclick="openResetModal()">Сброс</button>
  </div>
</div>

<div class="main-layout">
  <!-- Left Column: Front Panel Chassis -->
  <div>
    <div class="chassis-stage" id="chassis-stage">
      <div class="lcd-aperture" id="lcd-aperture">
        <div class="lcd-header" id="lcd-title">Segnetics Pixel 2514</div>
        <div class="lcd-matrix-text" id="lcd-text">Загрузка...</div>
      </div>

      <!-- Factory Buttons -->
      <div class="btn-zone btn-esc"   id="btn-esc"   title="ESC"   onclick="pressKey('ESC')"></div>
      <div class="btn-zone btn-right" id="btn-right" title="Right" onclick="pressKey('RIGHT')"></div>
      <div class="btn-zone btn-up"    id="btn-up"    title="Up"    onclick="pressKey('UP')"></div>
      <div class="btn-zone btn-down"  id="btn-down"  title="Down"  onclick="pressKey('DOWN')"></div>
      <div class="btn-zone btn-ok"    id="btn-ok"    title="OK"    onclick="pressKey('OK')"></div>

      <!-- Alarm slot -->
      <div class="alarm-slot" id="alarm-slot"></div>

      <!-- Terminal LEDs -->
      <div class="terminal-leds">
        <div class="led-item"><div class="lamp" id="lamp-do0"></div> DO 0</div>
        <div class="led-item"><div class="lamp" id="lamp-do1"></div> DO 1</div>
        <div class="led-item"><div class="lamp" id="lamp-do2"></div> DO 2</div>
      </div>
    </div>

    <!-- Time-Travel History Scrubber -->
    <div class="scrubber-container">
      <span class="scrubber-badge" id="scrubber-badge">LIVE</span>
      <input type="range" class="scrubber-slider" id="historyScrubber" min="0" max="0" value="0" oninput="scrubHistory(this.value)">
      <button class="btn-nav" style="padding:2px 8px; font-size:10px;" onclick="resumeLive()">В эфир</button>
    </div>
  </div>

  <!-- Right Column: Control Panels -->
  <div>
    <!-- Speed & Time Warp -->
    <div class="panel-box">
      <div class="panel-header">
        <span>Ускорение времени (Time Warp)</span>
        <span id="speed-status" style="font-family:monospace; color:#38bdf8;">1x (Реальное)</span>
      </div>
      <div class="timewarp-bar">
        <button class="btn-speed active" onclick="setSpeed(1.0, this)">1x</button>
        <button class="btn-speed" onclick="setSpeed(10.0, this)">10x</button>
        <button class="btn-speed" onclick="setSpeed(60.0, this)">60x (1с = 1м)</button>
        <button class="btn-speed" onclick="setSpeed(600.0, this)">600x (1с = 10м)</button>
        <button class="btn-speed" onclick="setSpeed(3600.0, this)">3600x (1с = 1ч)</button>
        <button class="btn-speed" onclick="togglePause(this)">Пауза</button>
      </div>
    </div>

    <!-- IO Forcing (Inputs) -->
    <div class="panel-box">
      <div class="panel-header">
        <span>Форсирование сигналов (DI / AI Force)</span>
      </div>
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
        <!-- Digital Inputs -->
        <div>
          <div style="font-size:11px; color:#94a3b8; margin-bottom:6px; font-weight:600;">ДИСКРЕТНЫЕ ВХОДЫ (DI 0..5):</div>
          <div style="display:flex; flex-wrap:wrap; gap:6px;">
            <button class="toggle-switch" id="sw-di0" onclick="toggleDI(0)">DI 0: 0</button>
            <button class="toggle-switch" id="sw-di1" onclick="toggleDI(1)">DI 1: 0</button>
            <button class="toggle-switch" id="sw-di2" onclick="toggleDI(2)">DI 2: 0</button>
            <button class="toggle-switch" id="sw-di3" onclick="toggleDI(3)">DI 3: 0</button>
            <button class="toggle-switch" id="sw-di4" onclick="toggleDI(4)">DI 4: 0</button>
            <button class="toggle-switch" id="sw-di5" onclick="toggleDI(5)">DI 5: 0</button>
          </div>
        </div>

        <!-- Analog Inputs -->
        <div>
          <div style="font-size:11px; color:#94a3b8; margin-bottom:6px; font-weight:600;">АНАЛОГОВЫЕ ВХОДЫ (AI 0..2):</div>
          <div class="slider-row">
            <span>AI 0:</span>
            <input type="range" min="0" max="100" step="0.5" value="0" oninput="setAI(0, this.value)">
            <span class="slider-val" id="val-ai0">0.0</span>
          </div>
          <div class="slider-row">
            <span>AI 1:</span>
            <input type="range" min="0" max="100" step="0.5" value="0" oninput="setAI(1, this.value)">
            <span class="slider-val" id="val-ai1">0.0</span>
          </div>
          <div class="slider-row">
            <span>AI 2:</span>
            <input type="range" min="0" max="100" step="0.5" value="0" oninput="setAI(2, this.value)">
            <span class="slider-val" id="val-ai2">0.0</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Live Event Console -->
    <div class="panel-box">
      <div class="panel-header">
        <span>События и лог контроллера</span>
        <button class="btn-nav" style="padding:2px 8px; font-size:10.5px;" onclick="clearLogs()">Очистить</button>
      </div>
      <div class="log-console" id="log-console">
        <!-- Log lines dynamically injected -->
      </div>
    </div>

    <!-- Live FBD Watch (F9) -->
    <div class="panel-box">
      <div class="panel-header">
        <span>Живые сигналы FBD (Аналог F9 в SMLogix)</span>
        <span id="fbd-count" style="font-size:11px; color:#94a3b8;"></span>
      </div>
      <div style="max-height: 160px; overflow-y: auto;">
        <table class="fbd-table">
          <thead>
            <tr>
              <th>Блок</th>
              <th>Тип</th>
              <th>Входы</th>
              <th>Выход</th>
            </tr>
          </thead>
          <tbody id="fbd-table-body">
            <!-- Dynamically injected -->
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<!-- Modal: Factory Reset Confirmation -->
<div class="modal-overlay" id="reset-modal">
  <div class="modal-card">
    <h3 style="color:#ef4444; margin-bottom:10px;">Подтверждение полного сброса</h3>
    <p style="font-size:12px; color:#9ca3af; margin-bottom:14px;">
      Внимание: будут сброшены все переменные, история отладки и состояния триггеров к начальному состоянию.
      Для подтверждения введите слово <strong>сброс</strong> или <strong>reset</strong>:
    </p>
    <input type="text" id="reset-token-input" placeholder="Введите 'сброс'" style="width:100%; padding:8px; background:#0d0e12; border:1px solid #374151; color:#fff; border-radius:4px; margin-bottom:14px; font-family:monospace;">
    <div style="display:flex; justify-content:flex-end; gap:8px;">
      <button class="btn-nav" style="background:#374151;" onclick="closeResetModal()">Отмена</button>
      <button class="btn-danger" onclick="confirmReset()">Сбросить всё</button>
    </div>
  </div>
</div>

<script>
let isScrubbing = false;
let currentHistory = [];

function applyLayout(layout) {
  if (!layout) return;
  const s = document.getElementById('lcd-aperture');
  if (s && layout.screen) {
    s.style.left = layout.screen.left + '%';
    s.style.top = layout.screen.top + '%';
    s.style.width = layout.screen.width + '%';
    s.style.height = layout.screen.height + '%';
  }
  const btns = layout.buttons || {};
  for (const k in btns) {
    const el = document.getElementById('btn-' + k);
    if (el) {
      el.style.left = btns[k].left + '%';
      el.style.top = btns[k].top + '%';
      if (layout.buttons_width) el.style.width = layout.buttons_width + '%';
      if (layout.buttons_height) el.style.height = layout.buttons_height + '%';
    }
  }
  const al = document.getElementById('alarm-slot');
  if (al && layout.alarm) {
    al.style.left = layout.alarm.left + '%';
    al.style.top = layout.alarm.top + '%';
    al.style.width = layout.alarm.width + '%';
    al.style.height = layout.alarm.height + '%';
  }
}

function update() {
  fetch('/api/state')
    .then(r => r.json())
    .then(d => {
      document.getElementById('http-port').innerText = d.http_port;
      document.getElementById('modbus-port').innerText = d.modbus_port;

      // Clock
      const sec = Math.floor(d.virtual_time || 0);
      const hh = String(Math.floor(sec / 3600)).padStart(2, '0');
      const mm = String(Math.floor((sec % 3600) / 60)).padStart(2, '0');
      const ss = String(sec % 60).padStart(2, '0');
      document.getElementById('nav-clock').innerText = `${hh}:${mm}:${ss}`;

      currentHistory = d.telemetry_history || [];
      const scrubber = document.getElementById('historyScrubber');
      if (scrubber && !isScrubbing) {
        scrubber.max = Math.max(0, currentHistory.length - 1);
        scrubber.value = scrubber.max;
      }

      if (!isScrubbing) {
        // LCD
        document.getElementById('lcd-title').innerText = d.lcd_title;
        document.getElementById('lcd-text').innerText = (d.lcd_lines || []).join(String.fromCharCode(10));

        // DO Lamps
        for (let i = 0; i < 3; i++) {
          const el = document.getElementById('lamp-do' + i);
          if (el) el.className = 'lamp ' + (d.do && d.do[i] ? 'on green' : '');
        }

        // Alarm slot
        const alarmSlot = document.getElementById('alarm-slot');
        if (alarmSlot) {
          alarmSlot.className = 'alarm-slot ' + (d.do && d.do[2] ? 'on' : (d.do && (d.do[0] || d.do[1]) ? 'green' : ''));
        }
      }

      // DI Buttons
      for (let i = 0; i < 6; i++) {
        const el = document.getElementById('sw-di' + i);
        if (el && d.di) {
          el.className = 'toggle-switch ' + (d.di[i] ? 'on' : '');
          el.innerText = `DI ${i}: ` + (d.di[i] ? '1' : '0');
        }
      }

      // AI values
      for (let i = 0; i < 3; i++) {
        const valEl = document.getElementById('val-ai' + i);
        if (valEl && d.ai) valEl.innerText = Number(d.ai[i]).toFixed(1);
      }

      // Event Logs
      const logConsole = document.getElementById('log-console');
      if (logConsole && d.event_logs) {
        logConsole.innerHTML = d.event_logs.map(l => `
          <div class="log-item">
            <span class="log-time">[${l.time}]</span>
            <span class="log-type-${l.type}">${l.msg}</span>
          </div>
        `).join('');
      }

      // FBD Table
      const tbody = document.getElementById('fbd-table-body');
      if (tbody && d.blocks) {
        document.getElementById('fbd-count').innerText = `${d.blocks.length} блоков`;
        tbody.innerHTML = d.blocks.map(b => `
          <tr>
            <td><strong>${b.id}</strong></td>
            <td><span style="color:#38bdf8;">${b.type}</span></td>
            <td>${b.inputs}</td>
            <td class="${b.out === 'True' ? 'val-true' : (b.out === 'False' ? 'val-false' : '')}"><strong>${b.out}</strong></td>
          </tr>
        `).join('');
      }

      // Apply initial layout if available
      if (d.layout) applyLayout(d.layout);
    })
    .catch(() => {});
}

function scrubHistory(idx) {
  isScrubbing = true;
  document.getElementById('scrubber-badge').innerText = 'ИСТОРИЯ';
  document.getElementById('scrubber-badge').style.background = '#dc2626';

  if (!currentHistory || !currentHistory[idx]) return;
  const p = currentHistory[idx];

  // Update LCD to historical point
  if (p.lcd_lines) {
    document.getElementById('lcd-text').innerText = p.lcd_lines.join(String.fromCharCode(10));
  }
  // Update DO lamps
  if (p.do) {
    for (let i = 0; i < 3; i++) {
      const el = document.getElementById('lamp-do' + i);
      if (el) el.className = 'lamp ' + (p.do[i] ? 'on green' : '');
    }
  }
}

function resumeLive() {
  isScrubbing = false;
  document.getElementById('scrubber-badge').innerText = 'LIVE';
  document.getElementById('scrubber-badge').style.background = '#78350f';
  update();
}

function pressKey(key) {
  fetch('/api/key', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key: key })
  }).then(() => update());
}

function switchProject(proj) {
  fetch('/api/switch_project', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project: proj })
  }).then(() => update());
}

function toggleDI(idx) {
  fetch('/api/toggle_di', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ index: idx })
  }).then(() => update());
}

function setAI(idx, val) {
  document.getElementById('val-ai' + idx).innerText = Number(val).toFixed(1);
  fetch('/api/set_ai', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ index: idx, value: parseFloat(val) })
  });
}

function setSpeed(mult, btn) {
  document.querySelectorAll('.btn-speed').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('speed-status').innerText = mult + 'x';
  fetch('/api/command', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cmd: 'set_speed', val: mult })
  });
}

function togglePause(btn) {
  fetch('/api/command', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cmd: 'toggle_pause' })
  }).then(() => {
    btn.classList.toggle('active');
    document.getElementById('speed-status').innerText = btn.classList.contains('active') ? 'ПАУЗА' : 'РАБОТА';
  });
}

function clearLogs() {
  fetch('/api/clear_logs', { method: 'POST' }).then(() => update());
}

function openResetModal() {
  document.getElementById('reset-modal').style.display = 'flex';
  document.getElementById('reset-token-input').value = '';
}
function closeResetModal() {
  document.getElementById('reset-modal').style.display = 'none';
}
function confirmReset() {
  const token = document.getElementById('reset-token-input').value.trim();
  fetch('/api/reset_all', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: token })
  })
  .then(r => r.json())
  .then(d => {
    if (d.status === 'ok') {
      closeResetModal();
      resumeLive();
      update();
    } else {
      alert('Ошибка: ' + (d.error || 'Неверный токен'));
    }
  });
}

function openLayoutEditor() {
  alert('Режим калибровки: кнопки и экран загружены из layout_config.json.');
}

setInterval(update, 250);
update();
</script>
</body>
</html>
"""


class StudioHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(STUDIO_HTML_PAGE.encode("utf-8"))

        elif self.path.startswith("/static/"):
            fname = self.path[len("/static/") :]
            fpath = os.path.join(STATIC_DIR, fname)
            if not os.path.exists(fpath):
                # Fallback to general static
                fpath = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "static", fname
                )
            if os.path.exists(fpath) and os.path.isfile(fpath):
                mime, _ = mimetypes.guess_type(fpath)
                self.send_response(200)
                self.send_header("Content-Type", mime or "application/octet-stream")
                self.end_headers()
                with open(fpath, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()

        elif self.path == "/api/state":
            rt = STUDIO_STATE.runtime
            blocks_data = []
            for bid in STUDIO_STATE.runtime.execution_order:
                block = STUDIO_STATE.program.blocks[bid]
                # Format inputs
                inps = []
                for k, w in block.inputs.items():
                    if w:
                        v = rt.get_signal(w.source_block, w.source_pin)
                        inps.append(f"{k}={v}")
                for k, c in block.constants.items():
                    inps.append(f"{k}={c}")

                # Output
                out_v = rt.get_signal(bid, "out", rt.get_signal(bid, "Q", "-"))
                if isinstance(out_v, float):
                    out_str = f"{out_v:.2f}"
                else:
                    out_str = str(out_v)

                blocks_data.append(
                    {
                        "id": bid,
                        "type": block.block_type,
                        "inputs": ", ".join(inps) if inps else "-",
                        "out": out_str,
                    }
                )

            d = {
                "active_project": STUDIO_STATE.active_prog_key,
                "virtual_time": STUDIO_STATE.virtual_time,
                "http_port": STUDIO_STATE.http_port,
                "modbus_port": STUDIO_STATE.modbus_port,
                "di": STUDIO_STATE.di,
                "ai": STUDIO_STATE.ai,
                "do": STUDIO_STATE.do,
                "ao": STUDIO_STATE.ao,
                "lcd_title": STUDIO_STATE.lcd_title,
                "lcd_lines": STUDIO_STATE.lcd_lines,
                "blocks": blocks_data,
                "event_logs": STUDIO_STATE.event_logs[-50:],
                "telemetry_history": STUDIO_STATE.telemetry_history[-200:],
                "layout": load_layout_config(),
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(d).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        body = json.loads(data) if data else {}

        if self.path == "/api/switch_project":
            proj = body.get("project", "pump")
            STUDIO_STATE.switch_program(proj)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        elif self.path == "/api/toggle_di":
            idx = int(body.get("index", 0))
            if 0 <= idx < 6:
                STUDIO_STATE.di[idx] = not STUDIO_STATE.di[idx]
                state_str = "1 (True)" if STUDIO_STATE.di[idx] else "0 (False)"
                STUDIO_STATE.add_log(f"Вход DI{idx} переключен в {state_str}", "action")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        elif self.path == "/api/set_ai":
            idx = int(body.get("index", 0))
            val = float(body.get("value", 0.0))
            if 0 <= idx < 6:
                STUDIO_STATE.ai[idx] = val
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        elif self.path == "/api/key":
            key = body.get("key", "").upper()
            action = f"Нажата клавиша Pixel: {key}"
            STUDIO_STATE.last_action_msg = action
            STUDIO_STATE.add_log(action, "action")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"status": "ok", "action": action}).encode("utf-8")
            )

        elif self.path == "/api/command":
            cmd = body.get("cmd", "")
            val = body.get("val", None)
            if cmd == "set_speed":
                STUDIO_STATE.time_multiplier = float(val)
                STUDIO_STATE.add_log(f"Скорость времени установлена в {val}x", "info")
            elif cmd == "toggle_pause":
                STUDIO_STATE.is_paused = not STUDIO_STATE.is_paused
                status = "на паузу" if STUDIO_STATE.is_paused else "возобновлена"
                STUDIO_STATE.add_log(f"Эмуляция поставлена {status}", "info")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        elif self.path == "/api/reset_all":
            token = body.get("token", "").strip().lower()
            if token in ("сброс", "reset"):
                STUDIO_STATE.hard_factory_reset()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            else:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    b'{"status":"error","error":"\xd0\x94\xd0\xbb\xd1\x8f \xd1\x81\xd0\xb1\xd1\x80\xd0\xbe\xd1\x81\xd0\xb0 \xd0\xb2\xd0\xb2\xd0\xb5\xd0\xb4\xd0\xb8\xd1\x82\xd0\xb5 \'\xd1\x81\xd0\xb1\xd1\x80\xd0\xbe\xd1\x81\' \xd0\xb8\xd0\xbb\xd0\xb8 \'reset\'"}'
                )

        elif self.path == "/api/clear_logs":
            STUDIO_STATE.event_logs.clear()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        elif self.path == "/api/layout":
            new_layout = body.get("layout", {})
            if save_layout_config(new_layout):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok"}')
            else:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"error"}')
        else:
            self.send_response(404)
            self.end_headers()


def run_studio_simulation_loop():
    last_t = time.time()
    while True:
        now = time.time()
        dt = now - last_t
        last_t = now
        if dt > 0.5:
            dt = 0.1
        STUDIO_STATE.tick(dt)
        time.sleep(0.05)


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False


def find_available_port(
    start_port: int, max_attempts: int = 50, host: str = "127.0.0.1"
) -> int:
    for p in range(start_port, start_port + max_attempts):
        if is_port_available(p, host):
            return p
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return s.getsockname()[1]


def start_studio_server(
    base_port: int = 18088, base_modbus_port: int = 15502
) -> Tuple[int, int]:
    http_port = find_available_port(base_port)
    modbus_port = find_available_port(base_modbus_port)

    STUDIO_STATE.http_port = http_port
    STUDIO_STATE.modbus_port = modbus_port

    # Start Modbus TCP background server
    mb_server = ModbusTCPServer(host="127.0.0.1", port=modbus_port)
    mb_thread = threading.Thread(target=mb_server.start, daemon=True)
    mb_thread.start()

    # Start simulation tick loop
    sim_thread = threading.Thread(target=run_studio_simulation_loop, daemon=True)
    sim_thread.start()

    # Start HTTP server
    httpd = HTTPServer(("127.0.0.1", http_port), StudioHTTPHandler)
    http_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    http_thread.start()

    url = f"http://localhost:{http_port}"
    print("=" * 76)
    print(f"=== [OK] SEGNETICS PIXEL STUDIO WEB UI : {url}")
    print(
        f"=== [OK] MODBUS TCP СЕРВЕР             : localhost:{modbus_port} (Unit ID: 1)"
    )
    print("=" * 76)

    return http_port, modbus_port
