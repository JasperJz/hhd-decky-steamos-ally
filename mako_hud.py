"""Bounded, on-demand MAKO diagnostic reader for MangoHud exec fields."""
import json
import math
import os
import re
import sys
import time
from pathlib import Path


def parse_sample(line):
    if 'MAKO Renderer: present diagnostics:' not in line:
        return None
    fields = dict(re.findall(r'([a-z_]+)=([^\s]+)', line))
    try:
        base = float(fields['base_fps'])
        if fields.get('operation') == 'fixed-plan':
            output = float(fields['observed_output_fps'])
            kind = 'FG'
        elif fields.get('operation') == 'adaptive-plan':
            # Recorded output-request intervals, not target FPS or multiplier.
            if int(fields.get('requested_interval_samples', '0')) < 2:
                return None
            output = 1000 / float(fields['requested_interval_mean_ms'])
            kind = 'FG req'
        else:
            return None
        if all(math.isfinite(v) and 0 < v < 10000 for v in (base, output)):
            return {'base': base, 'output': output, 'kind': kind}
    except (KeyError, ValueError, ZeroDivisionError):
        pass
    return None


def read_live(log, cache, now=None):
    now = time.time() if now is None else now
    try:
        stat = log.stat()
        start = max(0, stat.st_size - 65536)
        with log.open('rb') as f:
            f.seek(start)
            data = f.read(65536)
        sample = None
        offset = start
        for line in data.splitlines(keepends=True):
            offset += len(line)
            if not line.endswith(b'\n'):
                continue
            candidate = parse_sample(line.decode(errors='replace'))
            if candidate:
                sample = {**candidate, 'position': offset, 'inode': stat.st_ino}
        try:
            previous = json.loads(cache.read_text())
        except (OSError, ValueError):
            # Establish a baseline; never display historical samples on startup.
            previous = {**(sample or {}), 'seen': 0}
        if sample and (sample['position'], sample['inode']) != (previous.get('position'), previous.get('inode')):
            previous = {**sample, 'seen': now}
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_name(cache.name + '.' + str(os.getpid()))
        tmp.write_text(json.dumps(previous))
        os.replace(tmp, cache)
        if now - previous.get('seen', 0) <= 4 and now - stat.st_mtime <= 4:
            return previous
    except (OSError, ValueError):
        pass
    return None


def format_sample(sample):
    return f"INPUT {sample['base']:.0f}" if sample else 'INPUT --'


if __name__ == '__main__':
    root = Path('/home/deck/.config/mako-render')
    sample = read_live(root / 'present-diagnostics.log', Path('/home/deck/.cache/hhd-mako-hud/sample.json'))
    key = 'base' if sys.argv[-1] == 'base' else 'output'
    label = 'BASE' if key == 'base' else (sample['kind'] if sample else 'FG')
    print(f"{label} {sample[key]:.1f}" if sample else f'{label} N/A')
