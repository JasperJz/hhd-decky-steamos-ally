"""Event-driven Gamescope LUT control; no idle polling."""
import asyncio
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

DEFAULT = dict(saturation=100, contrast=0, vibrance=0, temperature=0,
               gamma=0, black=0, gain_r=100, gain_g=100, gain_b=100)
RANGES = dict(saturation=(0, 150), contrast=(-20, 20), vibrance=(0, 40),
              temperature=(-40, 40), gamma=(-20, 20), black=(-10, 10),
              gain_r=(80, 120), gain_g=(80, 120), gain_b=(80, 120))
PRESETS = {'native': DEFAULT, 'natural': {**DEFAULT, 'saturation': 110, 'contrast': 5},
           'vivid': {**DEFAULT, 'saturation': 120, 'contrast': 10},
           'soft': {**DEFAULT, 'saturation': 110, 'contrast': 5, 'vibrance': 15}}


def validated(changes):
    if not isinstance(changes, dict) or not changes or set(changes) - set(RANGES):
        raise ValueError('无效的调色参数')
    for key, value in changes.items():
        low, high = RANGES[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError('调色参数超出范围：' + key)
    return changes


@lru_cache(maxsize=8)
def cube(values):
    s = dict(zip(DEFAULT, values))
    def transform(rgb):
        y = sum(a*b for a, b in zip(rgb, (.2126, .7152, .0722)))
        saturation = s['saturation']/100 + s['vibrance']/100*(1-(max(rgb)-min(rgb)))
        result = []
        for i, v in enumerate(rgb):
            v = y + (v-y)*saturation
            v = (v-.5)*(1+s['contrast']/100)+.5
            v += s['black']/100
            v *= s[('gain_r', 'gain_g', 'gain_b')[i]]/100
            v *= (1+s['temperature']*.003 if i == 0 else
                  1-s['temperature']*.003 if i == 2 else 1)
            result.append(max(0, min(1, v)) ** (1/(1+s['gamma']/100)))
        return result
    lines = ['TITLE "HHD Screen Color"', 'LUT_3D_SIZE 17',
             'DOMAIN_MIN 0 0 0', 'DOMAIN_MAX 1 1 1']
    for b in range(17):
        for g in range(17):
            for r in range(17):
                lines.append(' '.join(f'{v:.7f}' for v in transform((r/16, g/16, b/16))))
    return '\n'.join(lines)+'\n'


class ScreenColor:
    def __init__(self, directory=None):
        self.directory = Path(directory or '/home/deck/.config/hhd-decky-color')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory/'settings.json'
        self.state = dict(DEFAULT)
        self.enabled = False
        self.applied = None
        self.error = ''
        self.lock = asyncio.Lock()
        try:
            saved = json.loads(self.path.read_text())
            self.state.update(validated(saved['color']))
            self.enabled = bool(saved['enabled'])
        except FileNotFoundError:
            # One-time migration without changing the original plugin's files.
            old = Path('/home/deck/homebrew/settings/Screen Colors/color.json')
            if old.exists():
                saved = json.loads(old.read_text())
                self.state.update(validated({k: saved[k] for k in DEFAULT if k in saved}))
                self.enabled = self.state != DEFAULT
                existing = Path('/tmp/screen_colors_look.cube')
                if existing.is_file():
                    self.cache_path(self.state).write_bytes(existing.read_bytes())
                self._save()
        except (ValueError, KeyError, TypeError):
            self.error = '调色配置损坏，已使用原生值；请重新选择预设'

    def cache_path(self, color):
        key = hashlib.sha256(json.dumps(color, sort_keys=True).encode()).hexdigest()[:20]
        return self.directory/(key+'.cube')

    @staticmethod
    def session():
        for p in sorted(Path('/run/user/1000').glob('gamescope-*')):
            try:
                st = p.stat()
                if stat.S_ISSOCK(st.st_mode):
                    return (str(p), st.st_ino)
            except OSError:
                pass
        return None

    def status(self):
        session = self.session()
        values = self.state if self.enabled else DEFAULT
        target = (session, tuple(values.values()))
        return {'ok': True, 'color': dict(self.state), 'enabled': self.enabled,
                'supported': session is not None and Path('/usr/bin/gamescopectl').exists(),
                'applied': self.applied == target, 'error': self.error,
                'presets': list(PRESETS), 'ranges': RANGES}

    def _apply(self, state, enabled, force=False):
        session = self.session()
        if not session:
            raise ValueError('当前不在 Gamescope 游戏模式；进入游戏模式后再调整')
        color = state if enabled else DEFAULT
        target = (session, tuple(color.values()))
        if not force and self.applied == target:
            return
        p = self.cache_path(color)
        if not p.exists():
            p.write_text(cube(tuple(color.values())))
            # Bound disk usage even after many slider positions; keep the active LUT.
            cached = sorted(self.directory.glob('*.cube'), key=lambda f: f.stat().st_mtime)
            for old in cached[:-16]:
                if old != p:
                    old.unlink()
        env = dict(os.environ)
        original = env.pop('LD_LIBRARY_PATH_ORIG', None)
        env.pop('LD_LIBRARY_PATH', None)
        env.pop('LD_PRELOAD', None)
        if original:
            env['LD_LIBRARY_PATH'] = original
        env.update(XDG_RUNTIME_DIR=str(Path(session[0]).parent),
                   WAYLAND_DISPLAY=Path(session[0]).name)
        # Never force composition: leave hardware-plane selection to Gamescope.
        r = subprocess.run(['/usr/bin/gamescopectl', 'set_look', str(p)], env=env,
                           capture_output=True, text=True, timeout=3)
        if r.returncode:
            raise ValueError('Gamescope 未接受调色：' + (r.stderr or r.stdout)[:160])
        self.applied = target

    def _save(self):
        t = self.path.with_suffix('.tmp')
        t.write_text(json.dumps({'enabled': self.enabled, 'color': self.state}))
        t.replace(self.path)

    async def update(self, changes=None, preset=None, enabled=None):
        async with self.lock:
            state = dict(self.state)
            if preset is not None:
                if preset not in PRESETS:
                    raise ValueError('未知调色预设')
                state = dict(PRESETS[preset])
            if changes is not None:
                state.update(validated(changes))
            if enabled is not None and type(enabled) is not bool:
                raise ValueError('调色开关无效')
            active = enabled if enabled is not None else self.enabled
            if preset is not None:
                active = preset != 'native'
            await asyncio.to_thread(self._apply, state, active)
            self.state, self.enabled, self.error = state, active, ''
            await asyncio.to_thread(self._save)
            return self.status()

    async def restore(self):
        """Called by Steam lifecycle hooks, including frontend plugin load."""
        async with self.lock:
            if self.enabled:
                self.applied = None
                try:
                    await asyncio.to_thread(self._apply, dict(self.state), True, force=True)
                    self.error = ''
                except Exception as e:
                    self.error = str(e)
            return self.status()
