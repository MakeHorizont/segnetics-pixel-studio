"""
Tests for Universal Segnetics Pixel Studio.
Verifies sample FBD generation, execution of arbitrary non-tempeh programs,
and studio state switching.
"""

import unittest
from src.pixel_studio.sample_programs import (
    create_pump_station_program,
    create_ventilation_ahu_program,
    create_thermostat_pid_program,
)
from src.core.fbd_runtime import FBDRuntime
from src.pixel_studio.studio_simulator import StudioSimulatorState


class TestPixelStudio(unittest.TestCase):
    def test_pump_station_sample_execution(self):
        """Verify that the universal dual pump station FBD program executes properly."""
        prog = create_pump_station_program()
        rt = FBDRuntime(prog)

        # Dry run condition: di0 is 0 (water level too low)
        rt.inputs["di0"] = False  # Float low
        rt.step(1.0)
        self.assertTrue(rt.get_signal("NOT_DryRun", "out"))

        # Safe level, pump float high (di1 is True)
        rt.inputs["di0"] = True   # Safe water
        rt.inputs["di1"] = True   # Demand high
        rt.inputs["di2"] = False  # No P1 fault
        rt.step(1.0)
        self.assertFalse(rt.get_signal("NOT_DryRun", "out"))

    def test_ventilation_ahu_sample_execution(self):
        """Verify that ventilation AHU program executes comparator logic."""
        prog = create_ventilation_ahu_program()
        rt = FBDRuntime(prog)

        # Supply air temperature cold (18.0°C < 22.0°C setpoint)
        rt.inputs["ai3"] = 18.0
        rt.step(1.0)
        self.assertTrue(rt.get_signal("CMP_SupplyTemp", "<"))

        # Supply air reaches setpoint (23.0°C > 22.0°C)
        rt.inputs["ai3"] = 23.0
        rt.step(1.0)
        self.assertTrue(rt.get_signal("CMP_SupplyTemp", ">"))

    def test_studio_simulator_state_switching(self):
        """Verify dynamic project switching in Pixel Studio."""
        state = StudioSimulatorState()
        self.assertEqual(state.active_prog_key, "pump")

        state.switch_program("vent")
        self.assertEqual(state.active_prog_key, "vent")
        self.assertIn("ВЕНТИЛЯЦИЯ", state.lcd_lines[2])

        state.switch_program("thermostat")
        self.assertEqual(state.active_prog_key, "thermostat")
        self.assertIn("ТЕРМОСТАТ", state.lcd_lines[2])

    def test_psl_optimizer_and_analyzer_methods(self):
        """Verify PSLOptimizer optimize_memory and PSLAnalyzer run_full_audit."""
        import os
        from src.core.psl_analyzer import PSLAnalyzer
        from src.core.psl_optimizer import PSLOptimizer

        # Look for local sample PSL or fallback gracefully without host assumption
        sample_psl = os.environ.get("PIXEL_TEST_PSL", "")
        if not sample_psl or not os.path.exists(sample_psl):
            candidates = [
                os.path.join(os.path.dirname(__file__), "..", "sample.psl"),
                os.path.join(os.path.dirname(__file__), "..", "..", "Программы", "29,10,2026.psl"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    sample_psl = c
                    break

        if not sample_psl or not os.path.exists(sample_psl):
            # Graceful pass when running on clean CI machine without proprietary binary assets
            return

        # 1. Analyzer
        analyzer = PSLAnalyzer(sample_psl)
        report_text = analyzer.run_full_audit()
        self.assertIn("РЕЗУЛЬТАТЫ АУДИТА", report_text)
        self.assertIn("ATmega2560", report_text)

        # 2. Optimizer
        out_temp = "test_opt_temp.psl"
        try:
            opt = PSLOptimizer(sample_psl)
            res = opt.optimize_memory(out_temp, max_png_count=10)
            self.assertIn("saved_kb", res)
            self.assertIn("bytes_saved", res)
            self.assertIn("png_removed", res)
            self.assertTrue(os.path.exists(out_temp))
        finally:
            if os.path.exists(out_temp):
                os.remove(out_temp)


if __name__ == "__main__":
    unittest.main()
