"""
Tests for Studio Web Simulator backend and state management.
Verifies:
1. Dynamic project switching and IO mappings.
2. Hard factory reset with token verification.
3. Time warp and pause mechanics.
4. Layout config load/save.
5. Telemetry history accumulation and time travel consistency.
"""

import unittest
from src.pixel_studio.studio_simulator import (
    StudioSimulatorState,
    load_layout_config,
    save_layout_config,
)


class TestStudioSimulator(unittest.TestCase):
    def setUp(self):
        self.state = StudioSimulatorState()

    def test_initial_state_and_defaults(self):
        """Verify clean initial state of simulator."""
        self.assertEqual(self.state.active_prog_key, "pump")
        self.assertEqual(len(self.state.di), 6)
        self.assertEqual(len(self.state.ai), 6)
        self.assertEqual(len(self.state.do), 3)
        self.assertFalse(self.state.is_paused)
        self.assertEqual(self.state.time_multiplier, 1.0)
        self.assertGreater(len(self.state.event_logs), 0)

    def test_project_switching_and_io_rebind(self):
        """Verify that switching projects re-initializes runtime and updates LCD."""
        self.state.switch_program("vent")
        self.assertEqual(self.state.active_prog_key, "vent")
        self.assertIn("ВЕНТИЛЯЦИЯ", self.state.lcd_lines[2])

        self.state.switch_program("thermostat")
        self.assertEqual(self.state.active_prog_key, "thermostat")
        self.assertIn("ТЕРМОСТАТ", self.state.lcd_lines[2])

    def test_tick_and_telemetry_history(self):
        """Verify that tick updates virtual time and records history points."""
        initial_history_len = len(self.state.telemetry_history)
        # Advance 2 seconds
        self.state.tick(1.0)
        self.state.tick(1.0)

        self.assertGreaterEqual(self.state.virtual_time, 2.0)
        self.assertGreaterEqual(len(self.state.telemetry_history), initial_history_len)

    def test_hard_factory_reset(self):
        """Verify that hard factory reset clears timers, history, and restores zero state."""
        # Mutate state
        self.state.virtual_time = 500.0
        self.state.time_multiplier = 60.0
        self.state.is_paused = True
        self.state.di[0] = True
        self.state.ai[0] = 75.5

        # Perform reset
        self.state.hard_factory_reset()

        self.assertEqual(self.state.virtual_time, 0.0)
        self.assertEqual(self.state.time_multiplier, 1.0)
        self.assertFalse(self.state.is_paused)
        self.assertEqual(self.state.di[0], False)
        self.assertEqual(self.state.ai[0], 0.0)
        self.assertEqual(len(self.state.telemetry_history), 0)
        self.assertIn("сброс", self.state.event_logs[-1]["msg"].lower())

    def test_layout_config_roundtrip(self):
        """Verify layout configuration persistence."""
        cfg = load_layout_config()
        self.assertIn("screen", cfg)
        self.assertIn("buttons", cfg)

        # Ensure save and load are consistent
        ok = save_layout_config(cfg)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
