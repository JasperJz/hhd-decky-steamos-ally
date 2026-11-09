import tempfile
import unittest
import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
from performance_hud import PerformanceHUD, OPTIONS, FANS, MAKO_EXEC, LEGACY_MAKO
from main import Plugin


class HUDTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'output-hud.conf'
        self.original = 'legacy_layout=0\nfont_size=18\nfps\nframetime=0\n' + FANS + '\nexec=other-command\n'
        self.path.write_text(self.original)
        self.reloads = 0
        def reload():
            self.reloads += 1
        self.hud = PerformanceHUD(self.path, reload)

    def test_all_options_enable_disable_and_preserve_unmanaged(self):
        for key in OPTIONS:
            self.assertTrue(self.hud.update({key: True})['selected'][key], key)
            self.assertFalse(self.hud.update({key: False})['selected'][key], key)
        text = self.path.read_text()
        self.assertIn('font_size=18\n', text)
        self.assertIn('exec=other-command\n', text)
        self.assertEqual(self.path.with_name(self.path.name + '.before-hhd-manager').read_text(), self.original)
        self.assertEqual(self.reloads, len(OPTIONS)*2)

    def test_failure_restores_configuration(self):
        def fail():
            raise RuntimeError('reload unavailable')
        self.hud.reload = fail
        with self.assertRaisesRegex(ValueError, '已恢复'):
            self.hud.update({'fps': False})
        self.assertEqual(self.path.read_text(), self.original)

    def test_existing_items_keep_their_layout_position(self):
        self.hud.update({'version': True})
        self.assertIn('font_size=18\n', self.path.read_text())
        self.hud.update({'version': False})
        self.assertIn('font_size=18\n', self.path.read_text())

    def test_subfields_enable_the_parent_and_parent_off_disables_children(self):
        state = self.hud.update({'gpu_power_limit': True})
        for key in ('gpu_power_limit', 'gpu_power', 'gpu_stats'):
            self.assertTrue(state['selected'][key])
        state = self.hud.update({'gpu_stats': False})
        for key in ('gpu_power_limit', 'gpu_power', 'gpu_stats'):
            self.assertFalse(state['selected'][key])

    def test_validation_and_global_visibility(self):
        for changes in [{'exec': 'unsafe'}, {'fps': 1}, {'unknown': True}]:
            with self.assertRaises(ValueError):
                self.hud.update(changes)
        self.assertEqual(self.path.read_text(), self.original)
        self.assertFalse(self.hud.update(enabled=False)['enabled'])
        self.assertTrue(self.hud.update(enabled=True)['enabled'])

    def test_disabled_rows_do_not_create_horizontal_slots_or_metrics(self):
        self.hud.update({'fps_metrics': False, 'ram': False, 'version': False})
        active = [line for line in self.path.read_text().splitlines() if not line.startswith('#')]
        for key in ('fps_metrics', 'ram', 'version'):
            self.assertFalse(any(line.split('=')[0] == key for line in active), key)
        self.hud.update({'ram': True})
        self.assertEqual(self.path.read_text().splitlines().count('ram'), 1)

    def test_old_dual_commands_migrate_to_one_fast_command(self):
        self.path.write_text(self.original + '\n'.join(LEGACY_MAKO) + '\n')
        state = self.hud.update({})
        text = self.path.read_text()
        self.assertTrue(state['selected']['mako_fps'])
        self.assertTrue(state['selected']['fps'])
        for command in LEGACY_MAKO:
            self.assertNotIn(command, text)
        self.assertEqual(text.splitlines().count(MAKO_EXEC['mako_fps']), 1)

    def test_fps_input_and_graph_are_first_and_fps_is_red(self):
        self.hud.update({'fps': True, 'mako_fps': True, 'frame_timing': True})
        lines = self.path.read_text().splitlines()
        self.assertEqual(lines[:3], ['fps', 'frame_timing', MAKO_EXEC['mako_fps']])
        self.assertIn('fps_color_change=0', lines)
        self.assertIn('engine_color=FF4040', lines)


class SamplerTests(unittest.IsolatedAsyncioTestCase):
    async def test_decky_namespace_starts_and_stops_sampler(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'fps.txt'
            hud = PerformanceHUD(Path(folder) / 'config', lambda: None)
            namespace = SimpleNamespace(performance_hud=hud, hud_task=None)
            with patch('performance_hud.FPS_TEXT', output), patch('performance_hud.read_live', return_value={'base': 30, 'output': 117, 'kind': 'FG'}):
                Plugin._sync_hud_sampler(namespace, {'enabled': True, 'selected': {'mako_fps': True}})
                for _ in range(100):
                    if output.exists():
                        break
                    await asyncio.sleep(.01)
                self.assertEqual(output.read_text(encoding='utf-8').strip(), 'INPUT 30')
                await Plugin._unload(namespace)
                self.assertTrue(namespace.hud_task.done())
                self.assertEqual(output.read_text(encoding='utf-8').strip(), 'INPUT --')
