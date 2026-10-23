import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from screen_color import ScreenColor, DEFAULT, PRESETS, cube, validated


class ColorTests(unittest.TestCase):
    def test_restore_reapplies_same_session_and_disabled_does_no_work(self):
        async def check(root):
            color = ScreenColor(root)
            color.enabled = True
            with patch.object(color, 'session', return_value=('/run/user/1000/gamescope-0', 1)), \
                 patch('screen_color.subprocess.run') as run:
                run.return_value.returncode = 0
                await color.restore()
                await color.restore()  # Lifecycle event after an external reset.
                self.assertEqual(run.call_count, 2)
                color.enabled = False
                await color.restore()
                self.assertEqual(run.call_count, 2)

        with tempfile.TemporaryDirectory() as root:
            asyncio.run(check(root))

    def test_restore_failure_invalidates_applied_and_next_event_recovers(self):
        async def check(root):
            color = ScreenColor(root)
            color.enabled = True
            with patch.object(color, 'session', return_value=('/run/user/1000/gamescope-0', 1)), \
                 patch('screen_color.subprocess.run') as run:
                run.return_value.returncode = 0
                await color.restore()
                run.side_effect = ValueError('not ready')
                result = await color.restore()
                self.assertEqual(result['error'], 'not ready')
                self.assertFalse(result['applied'])
                run.side_effect = None
                result = await color.restore()
                self.assertTrue(result['applied'])
                self.assertEqual(result['error'], '')

        with tempfile.TemporaryDirectory() as root:
            asyncio.run(check(root))

    def test_identity_cube_channels_and_size(self):
        lines = cube(tuple(DEFAULT.values())).splitlines()[4:]
        self.assertEqual(len(lines), 17**3)
        self.assertEqual(lines[0], '0.0000000 0.0000000 0.0000000')
        self.assertEqual(lines[16], '1.0000000 0.0000000 0.0000000')
        self.assertEqual(lines[-1], '1.0000000 1.0000000 1.0000000')

    def test_all_presets_are_bounded(self):
        for state in PRESETS.values():
            for line in cube(tuple(state.values())).splitlines()[4:]:
                self.assertTrue(all(0 <= float(v) <= 1 for v in line.split()))

    def test_rejects_unknown_and_non_integer_values(self):
        for changes in ({'saturation': True}, {'saturation': 151}, {'path': '/tmp/x'}, {}):
            with self.assertRaises(ValueError):
                validated(changes)

    def test_same_state_skips_process_but_new_session_reapplies(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, 'settings.json').write_text('{"enabled":true,"color":{"saturation":120}}')
            color = ScreenColor(root)
            with patch.object(color, 'session', return_value=('/run/user/1000/gamescope-0', 1)), \
                 patch('screen_color.subprocess.run') as run:
                run.return_value.returncode = 0
                color._apply(color.state, True)
                color._apply(color.state, True)
                self.assertEqual(run.call_count, 1)
                self.assertNotIn('composite_force', run.call_args.args[0])
            with patch.object(color, 'session', return_value=('/run/user/1000/gamescope-0', 2)), \
                 patch('screen_color.subprocess.run') as run:
                run.return_value.returncode = 0
                color._apply(color.state, True)
                run.assert_called_once()

    def test_failed_apply_keeps_saved_and_memory_state(self):
        async def check(root):
            Path(root, 'settings.json').write_text('{"enabled":true,"color":{"saturation":120}}')
            color = ScreenColor(root)
            before = color.path.read_text()
            with patch.object(color, '_apply', side_effect=ValueError('rejected')):
                with self.assertRaises(ValueError):
                    await color.update(preset='natural')
            self.assertEqual(color.state['saturation'], 120)
            self.assertEqual(color.path.read_text(), before)
        with tempfile.TemporaryDirectory() as root:
            asyncio.run(check(root))

    def test_off_applies_identity_but_preserves_custom_values(self):
        async def check(root):
            Path(root, 'settings.json').write_text('{"enabled":true,"color":{"saturation":120,"contrast":10}}')
            color = ScreenColor(root)
            with patch.object(color, 'session', return_value=('/run/user/1000/gamescope-0', 1)), \
                 patch('screen_color.subprocess.run') as run:
                run.return_value.returncode = 0
                await color.update(enabled=False)
                lut = Path(run.call_args.args[0][-1]).read_text()
            self.assertEqual(lut, cube(tuple(DEFAULT.values())))
            restored = ScreenColor(root)
            self.assertFalse(restored.enabled)
            self.assertEqual(restored.state['saturation'], 120)
        with tempfile.TemporaryDirectory() as root:
            asyncio.run(check(root))
