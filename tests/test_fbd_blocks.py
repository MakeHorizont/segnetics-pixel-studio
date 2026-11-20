"""
Unit tests for standard FBD blocks in the Segnetics execution engine.
Verifies logic, math, comparators, timers, counters, latches, and converters.
"""

import unittest
from src.core.dsl_models import FBDProgram
from src.core.fbd_runtime import FBDRuntime


class TestFBDBlocks(unittest.TestCase):
    def test_math_blocks(self):
        """Verify ADD, SUB, MUL, DIV operations and divide-by-zero safety."""
        prog = FBDProgram("TestMath")
        prog.add_block("ADD", "add1")
        prog.add_block("SUB", "sub1")
        prog.add_block("MUL", "mul1")
        prog.add_block("DIV", "div1")
        prog.add_block("DIV", "div_zero")

        prog.blocks["add1"].set_const("A", 12.5).set_const("B", 7.5)
        prog.blocks["sub1"].set_const("A", 20.0).set_const("B", 5.5)
        prog.blocks["mul1"].set_const("A", 3.0).set_const("B", 4.0)
        prog.blocks["div1"].set_const("A", 42.0).set_const("B", 2.0)
        prog.blocks["div_zero"].set_const("A", 10.0).set_const("B", 0.0)

        rt = FBDRuntime(prog)
        rt.step(0.1)

        self.assertAlmostEqual(rt.get_signal("add1", "out"), 20.0)
        self.assertAlmostEqual(rt.get_signal("sub1", "out"), 14.5)
        self.assertAlmostEqual(rt.get_signal("mul1", "out"), 12.0)
        self.assertAlmostEqual(rt.get_signal("div1", "out"), 21.0)
        # Division by zero should safely fallback without crashing
        self.assertAlmostEqual(rt.get_signal("div_zero", "out"), 10.0)

    def test_logic_blocks(self):
        """Verify AND, OR, NOT, XOR behavior with boolean truth tables."""
        prog = FBDProgram("TestLogic")
        prog.add_block("NOT", "not_true").set_const("in", True)
        prog.add_block("NOT", "not_false").set_const("in", False)

        prog.add_block("AND", "and_tt").set_const("in1", True).set_const("in2", True)
        prog.add_block("AND", "and_tf").set_const("in1", True).set_const("in2", False)

        prog.add_block("OR", "or_ft").set_const("in1", False).set_const("in2", True)
        prog.add_block("OR", "or_ff").set_const("in1", False).set_const("in2", False)

        prog.add_block("XOR", "xor_tt").set_const("in1", True).set_const("in2", True)
        prog.add_block("XOR", "xor_tf").set_const("in1", True).set_const("in2", False)

        rt = FBDRuntime(prog)
        rt.step(0.1)

        self.assertFalse(rt.get_signal("not_true", "out"))
        self.assertTrue(rt.get_signal("not_false", "out"))

        self.assertTrue(rt.get_signal("and_tt", "out"))
        self.assertFalse(rt.get_signal("and_tf", "out"))

        self.assertTrue(rt.get_signal("or_ft", "out"))
        self.assertFalse(rt.get_signal("or_ff", "out"))

        self.assertFalse(rt.get_signal("xor_tt", "out"))
        self.assertTrue(rt.get_signal("xor_tf", "out"))

    def test_comparator_blocks(self):
        """Verify CMP, EQ, NE, GT, GE, LT, LE comparators."""
        prog = FBDProgram("TestCmp")
        prog.add_block("CMP", "cmp1").set_const("A", 25.0).set_const("B", 30.0)
        prog.add_block("CMP", "cmp2").set_const("A", 30.0).set_const("B", 30.0)
        prog.add_block("CMP", "cmp3").set_const("A", 35.0).set_const("B", 30.0)

        prog.add_block("EQ", "eq_t").set_const("A", 5.0).set_const("B", 5.0)
        prog.add_block("NE", "ne_t").set_const("A", 5.0).set_const("B", 6.0)
        prog.add_block("GT", "gt_t").set_const("A", 10.0).set_const("B", 5.0)
        prog.add_block("GE", "ge_t").set_const("A", 5.0).set_const("B", 5.0)
        prog.add_block("LT", "lt_t").set_const("A", 4.0).set_const("B", 5.0)
        prog.add_block("LE", "le_t").set_const("A", 5.0).set_const("B", 5.0)

        rt = FBDRuntime(prog)
        rt.step(0.1)

        self.assertTrue(rt.get_signal("cmp1", "<"))
        self.assertTrue(rt.get_signal("cmp2", "="))
        self.assertTrue(rt.get_signal("cmp3", ">"))

        self.assertTrue(rt.get_signal("eq_t", "out"))
        self.assertTrue(rt.get_signal("ne_t", "out"))
        self.assertTrue(rt.get_signal("gt_t", "out"))
        self.assertTrue(rt.get_signal("ge_t", "out"))
        self.assertTrue(rt.get_signal("lt_t", "out"))
        self.assertTrue(rt.get_signal("le_t", "out"))

    def test_latches_rs_and_sr(self):
        """Verify RS (reset-dominant) and SR (set-dominant) triggers."""
        prog = FBDProgram("TestLatches")
        prog.add_block("RS", "rs1")
        prog.add_block("SR", "sr1")

        rt = FBDRuntime(prog)

        # 1. Set pulse
        prog.blocks["rs1"].set_const("S", True).set_const("R", False)
        prog.blocks["sr1"].set_const("S", True).set_const("R", False)
        rt.step(0.1)
        self.assertTrue(rt.get_signal("rs1", "Q"))
        self.assertTrue(rt.get_signal("sr1", "Q"))

        # 2. Both low: latches maintain state
        prog.blocks["rs1"].set_const("S", False).set_const("R", False)
        prog.blocks["sr1"].set_const("S", False).set_const("R", False)
        rt.step(0.1)
        self.assertTrue(rt.get_signal("rs1", "Q"))
        self.assertTrue(rt.get_signal("sr1", "Q"))

        # 3. Conflict condition: S=True and R=True
        prog.blocks["rs1"].set_const("S", True).set_const("R", True)
        prog.blocks["sr1"].set_const("S", True).set_const("R", True)
        rt.step(0.1)
        # RS: Reset dominant -> Q must be False
        self.assertFalse(rt.get_signal("rs1", "Q"))
        # SR: Set dominant -> Q must be True
        self.assertTrue(rt.get_signal("sr1", "Q"))

    def test_timers_ton_and_tof(self):
        """Verify TON (on-delay) and TOF (off-delay) timer dynamics."""
        prog = FBDProgram("TestTimers")
        prog.add_block("TON", "ton1").set_const("T", 2.0).set_const("in", True)
        prog.add_block("TOF", "tof1").set_const("T", 2.0).set_const("in", True)

        rt = FBDRuntime(prog)

        # At t=0.5s: TON not yet elapsed, TOF immediately true
        rt.step(0.5)
        self.assertFalse(rt.get_signal("ton1", "out"))
        self.assertAlmostEqual(rt.get_signal("ton1", "ET"), 0.5)
        self.assertTrue(rt.get_signal("tof1", "out"))

        # Step up to 2.1s: TON now fires
        rt.step(1.6)
        self.assertTrue(rt.get_signal("ton1", "out"))

        # Drop input to False
        prog.blocks["ton1"].set_const("in", False)
        prog.blocks["tof1"].set_const("in", False)
        rt.step(0.5)
        # TON resets immediately
        self.assertFalse(rt.get_signal("ton1", "out"))
        self.assertAlmostEqual(rt.get_signal("ton1", "ET"), 0.0)
        # TOF holds true during off-delay
        self.assertTrue(rt.get_signal("tof1", "out"))

        # Finish off-delay for TOF (1.6s more -> 2.1s total)
        rt.step(1.6)
        self.assertFalse(rt.get_signal("tof1", "out"))

    def test_counters_ctu_and_ctd(self):
        """Verify CTU (count-up) and CTD (count-down) counters."""
        prog = FBDProgram("TestCounters")
        prog.add_block("CTU", "ctu1").set_const("PV", 3.0).set_const("R", False)
        prog.add_block("CTD", "ctd1").set_const("PV", 10.0).set_const("LD", True)

        rt = FBDRuntime(prog)
        # Load preset on CTD
        rt.step(0.1)
        self.assertEqual(rt.get_signal("ctd1", "CV"), 10.0)
        self.assertFalse(rt.get_signal("ctd1", "Q"))

        # Pulse CTU three times
        prog.blocks["ctd1"].set_const("LD", False).set_const("CD", True)
        prog.blocks["ctu1"].set_const("CU", True)
        rt.step(1.0)
        prog.blocks["ctu1"].set_const("CU", False)
        rt.step(1.0)
        prog.blocks["ctu1"].set_const("CU", True)
        rt.step(1.0)
        prog.blocks["ctu1"].set_const("CU", False)
        rt.step(1.0)
        prog.blocks["ctu1"].set_const("CU", True)
        rt.step(1.0)

        # CTU reached 3 pulses -> Q=True
        self.assertEqual(rt.get_signal("ctu1", "CV"), 3.0)
        self.assertTrue(rt.get_signal("ctu1", "Q"))

        # CTD counted down from 10 by 5.0 seconds
        self.assertAlmostEqual(rt.get_signal("ctd1", "CV"), 5.0)

    def test_converters_and_limit(self):
        """Verify LIMIT clamping, SEL multiplexing, and type converters."""
        prog = FBDProgram("TestConverters")
        prog.add_block("LIMIT", "lim1").set_const("min", 10.0).set_const(
            "max", 50.0
        ).set_const("in", 5.0)
        prog.add_block("LIMIT", "lim2").set_const("min", 10.0).set_const(
            "max", 50.0
        ).set_const("in", 65.0)
        prog.add_block("LIMIT", "lim3").set_const("min", 10.0).set_const(
            "max", 50.0
        ).set_const("in", 30.0)

        prog.add_block("SEL", "sel_f").set_const("G", False).set_const(
            "in0", 100.0
        ).set_const("in1", 200.0)
        prog.add_block("SEL", "sel_t").set_const("G", True).set_const(
            "in0", 100.0
        ).set_const("in1", 200.0)

        prog.add_block("Linear", "lin").set_const("in", 10.0).set_const(
            "K", 2.5
        ).set_const("Offset", 5.0)
        prog.add_block("bool->int", "b2i").set_const("in", True)
        prog.add_block("real->int", "r2i").set_const("in", 42.8)

        rt = FBDRuntime(prog)
        rt.step(0.1)

        self.assertAlmostEqual(rt.get_signal("lim1", "out"), 10.0)  # Clamped to min
        self.assertAlmostEqual(rt.get_signal("lim2", "out"), 50.0)  # Clamped to max
        self.assertAlmostEqual(rt.get_signal("lim3", "out"), 30.0)  # Inside limits

        self.assertEqual(rt.get_signal("sel_f", "out"), 100.0)
        self.assertEqual(rt.get_signal("sel_t", "out"), 200.0)

        self.assertAlmostEqual(rt.get_signal("lin", "out"), 30.0)  # 10 * 2.5 + 5 = 30
        self.assertEqual(rt.get_signal("b2i", "out"), 1)
        self.assertEqual(rt.get_signal("r2i", "out"), 42)


if __name__ == "__main__":
    unittest.main()
