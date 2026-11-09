import tempfile
import time
import unittest
from pathlib import Path
from mako_hud import parse_sample, read_live, format_sample


class MakoHUDTests(unittest.TestCase):
    fixed = 'MAKO Renderer: present diagnostics: operation=fixed-plan base_fps=30 observed_output_fps=117 multiplier=4\n'

    def test_combined_display_never_returns_empty_output(self):
        self.assertEqual(format_sample(parse_sample(self.fixed)), 'INPUT 30')
        self.assertEqual(format_sample(None), 'INPUT --')

    def test_counts_are_not_multiplied(self):
        sample = parse_sample(self.fixed)
        self.assertEqual((sample['base'], sample['output']), (30, 117))
        self.assertIsNone(parse_sample(self.fixed.replace('117', 'nan')))

    def test_adaptive_uses_recorded_interval(self):
        sample = parse_sample('MAKO Renderer: present diagnostics: operation=adaptive-plan base_fps=41 target_fps=120 requested_interval_samples=90 requested_interval_mean_ms=10')
        self.assertEqual(sample['output'], 100)
        self.assertEqual(sample['kind'], 'FG req')

    def test_historical_samples_and_stale_samples_are_hidden(self):
        with tempfile.TemporaryDirectory() as folder:
            log, cache = Path(folder)/'log', Path(folder)/'cache'
            log.write_text(self.fixed)
            now = time.time()
            self.assertIsNone(read_live(log, cache, now))
            with log.open('a') as f:
                f.write(self.fixed)
            self.assertEqual(read_live(log, cache, now)['output'], 117)
            self.assertIsNone(read_live(log, cache, now+5))
