"""
FBD Domain-Specific Language (DSL) & Graph Models
Provides declarative classes to construct valid PLC programs for Segnetics Pixel.
"""

from typing import Dict, List, Optional, Any, Union

# Standard SMLogix FBD Block Catalog
SUPPORTED_BLOCKS = {
    # Logic
    "AND": {"inputs": ["in1", "in2"], "outputs": ["out"], "type": "bool"},
    "OR": {"inputs": ["in1", "in2"], "outputs": ["out"], "type": "bool"},
    "XOR": {"inputs": ["in1", "in2"], "outputs": ["out"], "type": "bool"},
    "NOT": {"inputs": ["in"], "outputs": ["out"], "type": "bool"},
    # Math
    "ADD": {"inputs": ["A", "B"], "outputs": ["out"], "type": "math"},
    "SUB": {"inputs": ["A", "B"], "outputs": ["out"], "type": "math"},
    "MUL": {"inputs": ["A", "B"], "outputs": ["out"], "type": "math"},
    "DIV": {"inputs": ["A", "B"], "outputs": ["out"], "type": "math"},
    # Comparators
    "CMP": {"inputs": ["A", "B"], "outputs": ["<", "=", ">"], "type": "relational"},
    "EQ": {"inputs": ["A", "B"], "outputs": ["out"], "type": "relational"},
    "NE": {"inputs": ["A", "B"], "outputs": ["out"], "type": "relational"},
    "GT": {"inputs": ["A", "B"], "outputs": ["out"], "type": "relational"},
    "GE": {"inputs": ["A", "B"], "outputs": ["out"], "type": "relational"},
    "LT": {"inputs": ["A", "B"], "outputs": ["out"], "type": "relational"},
    "LE": {"inputs": ["A", "B"], "outputs": ["out"], "type": "relational"},
    # Latches / Triggers
    "RS": {"inputs": ["S", "R"], "outputs": ["Q"], "type": "trigger"},
    "SR": {"inputs": ["S", "R"], "outputs": ["Q"], "type": "trigger"},
    # Timers
    "TON": {"inputs": ["in", "T"], "outputs": ["out", "ET"], "type": "timer"},
    "TOF": {"inputs": ["in", "T"], "outputs": ["out", "ET"], "type": "timer"},
    "TP": {"inputs": ["in", "T"], "outputs": ["out", "ET"], "type": "timer"},
    "Spdelay": {"inputs": ["in", "time"], "outputs": ["out"], "type": "timer"},
    "CTD": {"inputs": ["CD", "LD", "PV"], "outputs": ["Q", "CV"], "type": "counter"},
    "CTU": {"inputs": ["CU", "R", "PV"], "outputs": ["Q", "CV"], "type": "counter"},
    # Selectors / Converters
    "MUX": {"inputs": ["sel", "in0", "in1"], "outputs": ["out"], "type": "multiplexer"},
    "SEL": {"inputs": ["G", "in0", "in1"], "outputs": ["out"], "type": "multiplexer"},
    "LIMIT": {"inputs": ["min", "in", "max"], "outputs": ["out"], "type": "limiter"},
    "Linear": {"inputs": ["in", "K", "Offset"], "outputs": ["out"], "type": "scaling"},
    "bool->int": {"inputs": ["in"], "outputs": ["out"], "type": "conversion"},
    "int->real": {"inputs": ["in"], "outputs": ["out"], "type": "conversion"},
    "real->int": {"inputs": ["in"], "outputs": ["out"], "type": "conversion"},
}

class FBDBlock:
    def __init__(self, block_type: str, instance_id: str, x: int = 0, y: int = 0, comment: str = ""):
        self.block_type = block_type
        self.instance_id = instance_id
        self.x = x
        self.y = y
        self.comment = comment
        self.constants: Dict[str, Any] = {}
        self.inputs: Dict[str, Optional["FBDWire"]] = {}
        
    def set_const(self, pin_name: str, value: Any):
        self.constants[pin_name] = value
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.block_type,
            "id": self.instance_id,
            "pos": [self.x, self.y],
            "comment": self.comment,
            "constants": self.constants
        }

class FBDWire:
    def __init__(self, source_block: str, source_pin: str, target_block: str, target_pin: str):
        self.source_block = source_block
        self.source_pin = source_pin
        self.target_block = target_block
        self.target_pin = target_pin

    def to_dict(self) -> Dict[str, str]:
        return {
            "from": f"{self.source_block}.{self.source_pin}",
            "to": f"{self.target_block}.{self.target_pin}"
        }

class FBDProgram:
    def __init__(self, name: str, controller: str = "Pixel 2514"):
        self.name = name
        self.controller = controller
        self.blocks: Dict[str, FBDBlock] = {}
        self.wires: List[FBDWire] = []
        self.smart_bindings: Dict[str, str] = {} # Variable Name -> Block.Pin

    def add_block(self, block_type: str, instance_id: str, x: int = 0, y: int = 0, comment: str = "") -> FBDBlock:
        if block_type not in SUPPORTED_BLOCKS and not block_type.startswith("macro:"):
            raise ValueError(f"Unknown block type: {block_type}. Supported: {list(SUPPORTED_BLOCKS.keys())}")
        
        block = FBDBlock(block_type, instance_id, x, y, comment)
        self.blocks[instance_id] = block
        return block

    def connect(self, src_id: str, src_pin: str, dst_id: str, dst_pin: str) -> "FBDProgram":
        wire = FBDWire(src_id, src_pin, dst_id, dst_pin)
        self.wires.append(wire)
        if dst_id in self.blocks:
            self.blocks[dst_id].inputs[dst_pin] = wire
        return self

    def bind_smart_var(self, var_name: str, block_id: str, pin_name: str):
        """Bind an internal FBD pin to a user-visible SMArt screen parameter."""
        self.smart_bindings[var_name] = f"{block_id}.{pin_name}"

    def export_graph(self) -> Dict[str, Any]:
        return {
            "program_name": self.name,
            "controller": self.controller,
            "block_count": len(self.blocks),
            "wire_count": len(self.wires),
            "blocks": {bid: b.to_dict() for bid, b in self.blocks.items()},
            "wires": [w.to_dict() for w in self.wires],
            "smart_bindings": self.smart_bindings
        }
