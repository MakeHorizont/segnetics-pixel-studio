"""
Lightweight Pure-Python Modbus TCP Server for Segnetics Pixel Emulator
Provides non-standard auto-hunting ports and maps simulated FBD variables to Modbus registers.
Compatible with SMLogix, QModMaster, SCADA systems, and HW Virtual Serial Port.
"""

import socket
import struct
import threading
import os
from typing import Dict, Any, Tuple
from .fbd_runtime import FBDRuntime

class ModbusTCPServer:
    def __init__(self, runtime: FBDRuntime, base_port: int = 15502, unit_id: int = 1):
        self.runtime = runtime
        self.base_port = base_port
        self.unit_id = unit_id
        self.port = base_port
        self.server_socket = None
        self.is_running = False
        self._thread = None

    def start(self, max_tries: int = 50) -> int:
        """Bind with dynamic port fallback on conflict (WinError 10048 / EADDRINUSE)."""
        target_port = int(os.environ.get("MODBUS_PORT", self.base_port))
        
        for p in range(target_port, target_port + max_tries):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", p))
                s.listen(5)
                self.server_socket = s
                self.port = p
                break
            except (OSError, socket.error):
                continue

        if not self.server_socket:
            # Fallback to ephemeral OS assigned port
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("0.0.0.0", 0))
            s.listen(5)
            self.server_socket = s
            self.port = s.getsockname()[1]

        self.is_running = True
        self._thread = threading.Thread(target=self._serve_loop, daemon=True)
        self._thread.start()
        return self.port

    def _serve_loop(self):
        while self.is_running:
            try:
                client_sock, addr = self.server_socket.accept()
                t = threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True)
                t.start()
            except Exception:
                break

    def _handle_client(self, sock: socket.socket):
        sock.settimeout(5.0)
        try:
            while self.is_running:
                header = sock.recv(7)
                if not header or len(header) < 7:
                    break
                trans_id, proto_id, length, unit = struct.unpack(">HHHB", header)
                pdu = sock.recv(length - 1)
                if not pdu:
                    break
                
                resp_pdu = self._process_pdu(pdu)
                if resp_pdu:
                    resp_len = len(resp_pdu) + 1
                    resp_header = struct.pack(">HHHB", trans_id, proto_id, resp_len, unit)
                    sock.sendall(resp_header + resp_pdu)
        except Exception:
            pass
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _process_pdu(self, pdu: bytes) -> bytes:
        fn = pdu[0]
        rt = self.runtime
        
        # Function 0x01 / 0x02: Read Coils / Discrete Inputs
        if fn in (0x01, 0x02):
            start_addr, count = struct.unpack(">HH", pdu[1:5])
            # Coils mapping:
            # 0: dou0 (Heater)
            # 1: dou1 (Cooler)
            # 2: RS_ExothermDetected
            # 3: Master_Run
            # 4: Compressor_Delay_Active
            coils = [
                bool(rt.outputs.get("dou0", False)),
                bool(rt.outputs.get("dou1", False)),
                bool(rt.get_signal("RS_ExothermDetected", "Q", False)),
                bool(rt.get_signal("RS_MasterRun", "Q", False)),
                bool(rt.get_signal("TON_CompressorDelay", "ET", 0) > 0 and not rt.outputs.get("dou1", False))
            ]
            byte_count = (count + 7) // 8
            res_bytes = bytearray(byte_count)
            for i in range(count):
                idx = start_addr + i
                if idx < len(coils) and coils[idx]:
                    res_bytes[i // 8] |= (1 << (i % 8))
            return bytes([fn, byte_count]) + bytes(res_bytes)

        # Function 0x03 / 0x04: Read Holding / Input Registers
        elif fn in (0x03, 0x04):
            start_addr, count = struct.unpack(">HH", pdu[1:5])
            t_top = int(rt.inputs.get("ain3", 21.0) * 100)
            t_bot = int(rt.inputs.get("ain5", 20.5) * 100)
            t_avg = int(((rt.inputs.get("ain3", 21.0) + rt.inputs.get("ain5", 20.5)) / 2.0) * 100)
            t_amb = int(rt.inputs.get("ain2", 20.0) * 100)
            stage = int(rt.get_signal("MUX_StatusCode", "out", 0))
            
            ctd = rt.counter_states.get("CTD_Stage2Timer", {"cv": 43200})
            rem_sec = int(ctd.get("cv", 43200))
            rem_hours = rem_sec // 3600
            rem_mins = (rem_sec % 3600) // 60
            
            # Register map (16-bit signed integers)
            registers = [
                t_top,      # Reg 0: Top temp (x100)
                t_bot,      # Reg 1: Bottom temp (x100)
                t_avg,      # Reg 2: Average temp (x100)
                t_amb,      # Reg 3: Ambient temp (x100)
                stage,      # Reg 4: Current Stage (0..3)
                rem_hours,  # Reg 5: Remaining Hours
                rem_mins,   # Reg 6: Remaining Minutes
                rem_sec,    # Reg 7: Total remaining seconds
            ]
            
            res_words = []
            for i in range(count):
                idx = start_addr + i
                val = registers[idx] if idx < len(registers) else 0
                res_words.append(val & 0xFFFF)
                
            byte_count = count * 2
            payload = struct.pack(f">{count}H", *res_words)
            return bytes([fn, byte_count]) + payload

        # Function 0x05: Write Single Coil (Remote Start / Stop)
        elif fn == 0x05:
            addr, val = struct.unpack(">HH", pdu[1:5])
            is_on = (val == 0xFF00)
            if addr == 0: # Coil 0: Remote Start
                rt.inputs["btn_start"] = is_on
                rt.inputs["btn_stop"] = not is_on
            elif addr == 1: # Coil 1: Remote Stop
                rt.inputs["btn_stop"] = is_on
                rt.inputs["btn_start"] = not is_on
            return pdu # Echo response

        # Function 0x06: Write Single Register (Setpoint adjustment)
        elif fn == 0x06:
            addr, val = struct.unpack(">HH", pdu[1:5])
            # Reg 10: Manual Temp Override
            if addr == 10:
                target_c = val / 100.0
                rt.inputs["ain3"] = target_c
                rt.inputs["ain5"] = target_c
            return pdu

        # Error: Illegal Function
        return bytes([fn | 0x80, 0x01])

    def stop(self):
        self.is_running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
