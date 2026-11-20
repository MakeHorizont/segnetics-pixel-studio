"""
Generic FBD Runtime & Dataflow Integration Tests.
Verifies topological execution order, multi-layer graph propagation,
feedback loop stability, and input pulse consumption for arbitrary PLC programs.
"""

import unittest
from src.core.dsl_models import FBDProgram
from src.core.fbd_runtime import FBDRuntime


class TestGenericFBDRuntime(unittest.TestCase):
    def test_multi_layer_dataflow_propagation(self):
        """
        Verify that a 4-layer cascading arithmetic graph computes in a single scan cycle:
        Layer 1: Input A, B -> ADD(A, B) = sum1
        Layer 2: sum1, C -> MUL(sum1, C) = prod1
        Layer 3: prod1, D -> SUB(prod1, D) = sub1
        Layer 4: sub1, E -> DIV(sub1, E) = out1
        """
        prog = FBDProgram("DataflowCascade")
        prog.add_block("ADD", "B1_Add")
        prog.add_block("MUL", "B2_Mul")
        prog.add_block("SUB", "B3_Sub")
        prog.add_block("DIV", "B4_Div")

        # Connect cascade
        prog.connect("B1_Add", "out", "B2_Mul", "A")
        prog.connect("B2_Mul", "out", "B3_Sub", "A")
        prog.connect("B3_Sub", "out", "B4_Div", "A")

        # Set constants: ((10 + 5) * 4 - 20) / 8 = (15 * 4 - 20) / 8 = (60 - 20) / 8 = 40 / 8 = 5.0
        prog.blocks["B1_Add"].set_const("A", 10.0).set_const("B", 5.0)
        prog.blocks["B2_Mul"].set_const("B", 4.0)
        prog.blocks["B3_Sub"].set_const("B", 20.0)
        prog.blocks["B4_Div"].set_const("B", 8.0)

        rt = FBDRuntime(prog)
        rt.step(0.1)

        self.assertAlmostEqual(rt.get_signal("B1_Add", "out"), 15.0)
        self.assertAlmostEqual(rt.get_signal("B2_Mul", "out"), 60.0)
        self.assertAlmostEqual(rt.get_signal("B3_Sub", "out"), 40.0)
        self.assertAlmostEqual(rt.get_signal("B4_Div", "out"), 5.0)

    def test_pulse_consumption_and_latch_memory(self):
        """
        Verify that start and stop buttons operate as true 1-cycle pulses:
        - Pulse on btn_start latches MasterRun=True and clears btn_start.
        - Subsequent steps maintain MasterRun=True without re-pulsing.
        - Pulse on btn_stop latches MasterRun=False and clears btn_stop.
        """
        prog = FBDProgram("MotorStarter")
        prog.add_block("RS", "RS_MasterRun")
        prog.add_block("NOT", "NOT_Running")
        prog.connect("RS_MasterRun", "Q", "NOT_Running", "in")

        rt = FBDRuntime(prog)

        # Initially idle
        rt.step(0.1)
        self.assertFalse(rt.get_signal("RS_MasterRun", "Q"))
        self.assertTrue(rt.get_signal("NOT_Running", "out"))

        # Inject start pulse
        rt.inputs["btn_start"] = True
        rt.step(0.1)

        # MasterRun is now True and pulse is automatically consumed
        self.assertTrue(rt.get_signal("RS_MasterRun", "Q"))
        self.assertFalse(rt.get_signal("NOT_Running", "out"))
        self.assertFalse(rt.inputs["btn_start"], "btn_start pulse must be consumed")

        # Run 5 more cycles: latch must remain ON
        for _ in range(5):
            rt.step(0.1)
            self.assertTrue(rt.get_signal("RS_MasterRun", "Q"))

        # Inject stop pulse
        rt.inputs["btn_stop"] = True
        rt.step(0.1)

        self.assertFalse(rt.get_signal("RS_MasterRun", "Q"))
        self.assertTrue(rt.get_signal("NOT_Running", "out"))
        self.assertFalse(rt.inputs["btn_stop"], "btn_stop pulse must be consumed")

    def test_custom_industrial_interlock_system(self):
        """
        Simulate an arbitrary automated pumping station with:
        1. Pressure sensor input (Linear scaling).
        2. High pressure alarm (> 8.0 bar).
        3. Low water float switch (din0).
        4. Auto-shutoff safety interlock.
        """
        prog = FBDProgram("PumpInterlock")
        # 1. Analog scaling: raw 0..10V to 0..10 bar
        prog.add_block("Linear", "Scale_Pressure")
        prog.blocks["Scale_Pressure"].set_const("K", 1.0).set_const("Offset", 0.0)

        # 2. Overpressure comparator (> 8.0 bar)
        prog.add_block("GT", "GT_Overpressure")
        prog.blocks["GT_Overpressure"].set_const("B", 8.0)
        prog.connect("Scale_Pressure", "out", "GT_Overpressure", "A")

        # 3. Invert overpressure to form 'Pressure_OK' flag
        prog.add_block("NOT", "NOT_Overpressure")
        prog.connect("GT_Overpressure", "out", "NOT_Overpressure", "in")

        # 4. Pump enable: MasterRun AND Pressure_OK
        prog.add_block("RS", "RS_MasterRun")
        prog.add_block("AND", "AND_PumpRun")
        prog.connect("RS_MasterRun", "Q", "AND_PumpRun", "in1")
        prog.connect("NOT_Overpressure", "out", "AND_PumpRun", "in2")

        rt = FBDRuntime(prog)

        # Start system
        rt.inputs["btn_start"] = True
        rt.set_signal("Scale_Pressure", "in", 4.5)  # 4.5 bar (Normal)
        rt.step(0.1)

        # Pump should be running
        self.assertTrue(rt.get_signal("AND_PumpRun", "out"))

        # Pressure rises to 8.5 bar (Overpressure)
        rt.set_signal("Scale_Pressure", "in", 8.5)
        rt.step(0.1)

        # Interlock immediately cuts off pump
        self.assertTrue(rt.get_signal("GT_Overpressure", "out"))
        self.assertFalse(rt.get_signal("NOT_Overpressure", "out"))
        self.assertFalse(rt.get_signal("AND_PumpRun", "out"))


if __name__ == "__main__":
    unittest.main()
