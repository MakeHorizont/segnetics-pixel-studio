"""
Deterministic FBD Execution Engine & Runtime Simulator for Segnetics Pixel
Executes FBDProgram graphs in virtual time with millisecond precision.
"""

from typing import Dict, Any, List
from .dsl_models import FBDProgram


class FBDRuntime:
    def __init__(self, program: FBDProgram):
        self.program = program
        self.cycle_time_ms = 100  # Standard Pixel cycle: 100 ms
        self.virtual_time_sec = 0.0

        # State storages
        self.signals: Dict[str, Any] = {}  # "BlockID.Pin" -> value
        self.timer_states: Dict[str, Dict[str, Any]] = {}  # BlockID -> timer internals
        self.latch_states: Dict[str, bool] = {}  # BlockID -> Q
        self.counter_states: Dict[str, Dict[str, Any]] = {}

        # External Hardware IO
        self.inputs = {
            "ain0": 0.0,
            "ain1": 0.0,
            "ain2": 21.0,  # Ambient room
            "ain3": 21.0,  # Air Top
            "ain4": 0.0,
            "ain5": 21.0,  # Air Bottom
            "din0": False,
            "din1": False,
            "din2": False,
            "btn_start": False,
            "btn_stop": False,
        }
        self.outputs = {
            "dou0": False,  # Heater
            "dou1": False,  # Cooler
            "dou2": False,
        }

        self.execution_order = self._build_execution_order()

    def _build_execution_order(self) -> List[str]:
        """Topological sort of blocks to compute in correct dataflow order."""
        # Simple topological sort
        order = []
        visited = set()

        def visit(block_id):
            if block_id in visited or block_id not in self.program.blocks:
                return
            visited.add(block_id)
            block = self.program.blocks[block_id]
            for wire in block.inputs.values():
                if wire:
                    visit(wire.source_block)
            order.append(block_id)

        for bid in self.program.blocks:
            visit(bid)
        return order

    def get_signal(self, block_id: str, pin_name: str, default: Any = 0.0) -> Any:
        key = f"{block_id}.{pin_name}"
        if key in self.signals:
            return self.signals[key]
        if block_id in self.program.blocks:
            btype = self.program.blocks[block_id].block_type
            if btype == "NOT" and pin_name == "out":
                return True
        return default

    def set_signal(self, block_id: str, pin_name: str, value: Any):
        key = f"{block_id}.{pin_name}"
        self.signals[key] = value

    def step(self, dt_sec: float = 0.1):
        """Execute one simulation cycle with step size dt_sec."""
        self.virtual_time_sec += dt_sec

        # Inject inputs into entry blocks
        # Average sensors entry
        if "ADD_Sensors" in self.program.blocks:
            self.set_signal("ADD_Sensors", "A", float(self.inputs.get("ain3", 21.0)))
            self.set_signal("ADD_Sensors", "B", float(self.inputs.get("ain5", 20.5)))

        # Master run/stop buttons (pulse consumption)
        if "RS_MasterRun" in self.program.blocks:
            if self.inputs.get("btn_start", False):
                self.latch_states["RS_MasterRun"] = True
                self.latch_states["RS_ExothermDetected"] = False
                self.inputs["btn_start"] = False
            elif self.inputs.get("btn_stop", False):
                self.latch_states["RS_MasterRun"] = False
                if "RS_ExothermDetected" in self.program.blocks:
                    self.latch_states["RS_ExothermDetected"] = False
                self.inputs["btn_stop"] = False

        # Execute all blocks in order
        for bid in self.execution_order:
            block = self.program.blocks[bid]
            btype = block.block_type

            # Resolve inputs:
            # 1. From wires
            in_vals = {}
            for pin_name, wire in block.inputs.items():
                if wire:
                    if wire.source_block in self.inputs:
                        in_vals[pin_name] = self.inputs[wire.source_block]
                    elif wire.source_pin in self.inputs:
                        in_vals[pin_name] = self.inputs[wire.source_pin]
                    else:
                        in_vals[pin_name] = self.get_signal(
                            wire.source_block, wire.source_pin
                        )
            # 2. From constants
            for cpin, cval in block.constants.items():
                if cpin not in in_vals:
                    in_vals[cpin] = cval
            # 3. From injected signals on this block's pins (e.g. ADD_Sensors.A)
            prefix = f"{bid}."
            for sig_key, sig_val in self.signals.items():
                if sig_key.startswith(prefix):
                    pin = sig_key[len(prefix) :]
                    if pin not in in_vals:
                        in_vals[pin] = sig_val

            # Execute block logic
            if btype == "ADD":
                val = float(in_vals.get("A", 0)) + float(in_vals.get("B", 0))
                self.set_signal(bid, "out", val)

            elif btype == "SUB":
                val = float(in_vals.get("A", 0)) - float(in_vals.get("B", 0))
                self.set_signal(bid, "out", val)

            elif btype == "MUL":
                val = float(in_vals.get("A", 0)) * float(in_vals.get("B", 0))
                self.set_signal(bid, "out", val)

            elif btype == "DIV":
                denom = float(in_vals.get("B", 1.0))
                val = float(in_vals.get("A", 0)) / (denom if denom != 0 else 1.0)
                self.set_signal(bid, "out", val)

            elif btype == "NOT":
                val = not bool(in_vals.get("in", False))
                self.set_signal(bid, "out", val)

            elif btype == "AND":
                # Check only connected/defined in* pins
                in_pins = [in_vals[k] for k in in_vals if k.startswith("in")]
                if in_pins:
                    val = all(bool(v) for v in in_pins)
                else:
                    val = bool(in_vals.get("in1", False)) and bool(
                        in_vals.get("in2", False)
                    )
                self.set_signal(bid, "out", val)

            elif btype == "OR":
                # Check only connected/defined in* pins
                in_pins = [in_vals[k] for k in in_vals if k.startswith("in")]
                if in_pins:
                    val = any(bool(v) for v in in_pins)
                else:
                    val = bool(in_vals.get("in1", False)) or bool(
                        in_vals.get("in2", False)
                    )
                self.set_signal(bid, "out", val)

            elif btype == "XOR":
                val = bool(in_vals.get("in1", False)) ^ bool(in_vals.get("in2", False))
                self.set_signal(bid, "out", val)

            elif btype == "CMP":
                A = float(in_vals.get("A", 0))
                B = float(in_vals.get("B", 0))
                self.set_signal(bid, "<", A < B)
                self.set_signal(bid, "=", abs(A - B) < 0.001)
                self.set_signal(bid, ">", A > B)

            elif btype == "EQ":
                self.set_signal(
                    bid,
                    "out",
                    abs(float(in_vals.get("A", 0)) - float(in_vals.get("B", 0)))
                    < 0.0001,
                )

            elif btype == "NE":
                self.set_signal(
                    bid,
                    "out",
                    abs(float(in_vals.get("A", 0)) - float(in_vals.get("B", 0)))
                    >= 0.0001,
                )

            elif btype == "GE":
                self.set_signal(
                    bid, "out", float(in_vals.get("A", 0)) >= float(in_vals.get("B", 0))
                )

            elif btype == "GT":
                self.set_signal(
                    bid, "out", float(in_vals.get("A", 0)) > float(in_vals.get("B", 0))
                )

            elif btype == "LT":
                self.set_signal(
                    bid, "out", float(in_vals.get("A", 0)) < float(in_vals.get("B", 0))
                )

            elif btype == "LE":
                self.set_signal(
                    bid, "out", float(in_vals.get("A", 0)) <= float(in_vals.get("B", 0))
                )

            elif btype == "RS":
                S = bool(in_vals.get("S", False))
                R = bool(in_vals.get("R", False))
                cur_q = self.latch_states.get(bid, False)
                if R:
                    cur_q = False
                elif S:
                    cur_q = True
                self.latch_states[bid] = cur_q
                self.set_signal(bid, "Q", cur_q)

            elif btype == "SR":
                S = bool(in_vals.get("S", False))
                R = bool(in_vals.get("R", False))
                cur_q = self.latch_states.get(bid, False)
                if S:
                    cur_q = True
                elif R:
                    cur_q = False
                self.latch_states[bid] = cur_q
                self.set_signal(bid, "Q", cur_q)

            elif btype == "TON":
                # On-Delay Timer
                cond = bool(in_vals.get("in", False))
                t_target = float(in_vals.get("T", 10.0))
                st = self.timer_states.setdefault(bid, {"elapsed": 0.0, "out": False})
                if cond:
                    st["elapsed"] += dt_sec
                    if st["elapsed"] >= t_target:
                        st["out"] = True
                else:
                    st["elapsed"] = 0.0
                    st["out"] = False
                self.set_signal(bid, "out", st["out"])
                self.set_signal(bid, "ET", st["elapsed"])

            elif btype == "TOF":
                # Off-Delay Timer
                cond = bool(in_vals.get("in", False))
                t_target = float(in_vals.get("T", 10.0))
                st = self.timer_states.setdefault(bid, {"elapsed": 0.0, "out": False})
                if cond:
                    st["out"] = True
                    st["elapsed"] = 0.0
                else:
                    if st.get("out", False):
                        st["elapsed"] += dt_sec
                        if st["elapsed"] >= t_target:
                            st["out"] = False
                self.set_signal(bid, "out", st["out"])
                self.set_signal(bid, "ET", st["elapsed"])

            elif btype == "CTU":
                # Count-up counter
                cu_pulse = bool(in_vals.get("CU", False))
                r_pulse = bool(in_vals.get("R", False))
                pv = float(in_vals.get("PV", 10.0))
                st = self.counter_states.setdefault(bid, {})
                st.setdefault("cv", 0.0)
                st.setdefault("q", False)
                if r_pulse:
                    st["cv"] = 0.0
                    st["q"] = False
                elif cu_pulse:
                    st["cv"] += 1.0
                    st["q"] = st["cv"] >= pv
                self.set_signal(bid, "CV", float(st.get("cv", 0.0)))
                self.set_signal(bid, "Q", bool(st.get("q", False)))

            elif btype == "LIMIT":
                mn = float(in_vals.get("min", 0.0))
                mx = float(in_vals.get("max", 100.0))
                in_val = float(in_vals.get("in", 0.0))
                self.set_signal(bid, "out", max(mn, min(mx, in_val)))

            elif btype == "SEL":
                g = bool(in_vals.get("G", False))
                self.set_signal(bid, "out", in_vals.get("in1" if g else "in0", 0.0))

            elif btype == "Linear":
                v = float(in_vals.get("in", 0.0))
                k = float(in_vals.get("K", 1.0))
                offset = float(in_vals.get("Offset", 0.0))
                self.set_signal(bid, "out", v * k + offset)

            elif btype == "bool->int":
                self.set_signal(bid, "out", 1 if bool(in_vals.get("in", False)) else 0)

            elif btype == "int->real":
                self.set_signal(bid, "out", float(in_vals.get("in", 0.0)))

            elif btype == "real->int":
                self.set_signal(bid, "out", int(float(in_vals.get("in", 0.0))))

            elif btype == "CTD":
                # Countdown timer
                cd_pulse = bool(in_vals.get("CD", False))
                ld_pulse = bool(in_vals.get("LD", False))
                pv = float(in_vals.get("PV", 43200.0))  # 12 hours default in seconds
                st = self.counter_states.setdefault(bid, {})
                st.setdefault("cv", pv)
                st.setdefault("q", False)
                if ld_pulse:
                    st["cv"] = pv
                    st["q"] = False
                elif cd_pulse:  # Count down when active
                    st["cv"] = max(0.0, st["cv"] - dt_sec)
                    st["q"] = st["cv"] <= 0.0
                self.set_signal(bid, "CV", float(st.get("cv", pv)))
                self.set_signal(bid, "Q", bool(st.get("q", False)))

            elif btype == "MUX":
                # Integer status code MUX
                stage1 = bool(self.get_signal("AND_Stage1Active", "out", False))
                stage2 = bool(self.get_signal("AND_Stage2Active", "out", False))
                stage3 = bool(self.get_signal("AND_Stage3Active", "out", False))
                status = 0  # STOP
                if stage3:
                    status = 3
                elif stage2:
                    status = 2
                elif stage1:
                    status = 1
                self.set_signal(bid, "out", status)

        # Update physical outputs
        self.outputs["dou0"] = bool(self.get_signal("AND_HeaterDou0", "out", False))
        self.outputs["dou1"] = bool(
            self.get_signal("TON_CompressorDelay", "out", False)
        )
