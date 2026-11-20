"""
Virtual Serial and TCP-to-RTU Bridge for Segnetics Pixel Emulator
Allows SMLogix, SCADA, or external tools to connect to simulated Pixel via COM port or TCP socket.
"""

import sys
import time
import socket
import struct
import threading
from typing import Optional
from .fbd_runtime import FBDRuntime

def calculate_crc16(data: bytes) -> int:
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 1) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

class VirtualSerialBridge:
    """
    Connects to a serial port (COMx) using pyserial or socket bridge,
    processing Modbus RTU packets against FBD runtime.
    """
    def __init__(self, runtime: FBDRuntime, unit_id: int = 1):
        self.runtime = runtime
        self.unit_id = unit_id
        self.is_running = False

    def process_rtu_frame(self, frame: bytes) -> Optional[bytes]:
        if len(frame) < 4:
            return None
        # Check CRC16
        payload, received_crc = frame[:-2], frame[-2:]
        expected_crc = calculate_crc16(payload)
        actual_crc = struct.unpack("<H", received_crc)[0]
        if expected_crc != actual_crc:
            return None # Bad CRC
            
        unit = payload[0]
        if unit != self.unit_id and unit != 0:
            return None # Not for us
            
        fn = payload[1]
        rt = self.runtime
        
        # Read Holding / Input Registers (0x03, 0x04)
        if fn in (0x03, 0x04):
            start_addr, count = struct.unpack(">HH", payload[2:6])
            t_top = int(rt.inputs.get("ain3", 21.0) * 100)
            t_bot = int(rt.inputs.get("ain5", 20.5) * 100)
            t_avg = int(((t_top + t_bot) / 2))
            stage = int(rt.get_signal("MUX_StatusCode", "out", 0))
            ctd = rt.counter_states.get("CTD_Stage2Timer", {"cv": 43200})
            rem_sec = int(ctd.get("cv", 43200))
            
            regs = [t_top, t_bot, t_avg, 2000, stage, rem_sec // 3600, (rem_sec % 3600) // 60, rem_sec]
            res_words = []
            for i in range(count):
                idx = start_addr + i
                val = regs[idx] if idx < len(regs) else 0
                res_words.append(val & 0xFFFF)
                
            byte_count = count * 2
            resp_pdu = bytes([unit, fn, byte_count]) + struct.pack(f">{count}H", *res_words)
            crc = calculate_crc16(resp_pdu)
            return resp_pdu + struct.pack("<H", crc)
            
        # Read Coils (0x01, 0x02)
        elif fn in (0x01, 0x02):
            start_addr, count = struct.unpack(">HH", payload[2:6])
            coils = [
                bool(rt.outputs.get("dou0", False)),
                bool(rt.outputs.get("dou1", False)),
                bool(rt.get_signal("RS_ExothermDetected", "Q", False)),
                bool(rt.get_signal("RS_MasterRun", "Q", False)),
            ]
            byte_count = (count + 7) // 8
            res_bytes = bytearray(byte_count)
            for i in range(count):
                idx = start_addr + i
                if idx < len(coils) and coils[idx]:
                    res_bytes[i // 8] |= (1 << (i % 8))
            resp_pdu = bytes([unit, fn, byte_count]) + bytes(res_bytes)
            crc = calculate_crc16(resp_pdu)
            return resp_pdu + struct.pack("<H", crc)

        return None
