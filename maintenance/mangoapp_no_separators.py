"""User-level MangoApp copy omitting only the first (FPS-to-graph) separator.

The first row skips the inlined horizontal_separator draw block, retaining its
spacing; all later rows draw normally. Verified against overlay.cpp and ELF build
ID 92a40175a97d148b0c3060a1644f20cbe89e12df. No system executable is changed.
"""
import hashlib
import os
import struct
from pathlib import Path
import subprocess

EXPECTED = '978779ed3c8cd91549b6a622d50e292444f9d268fa3753c425fa2108b4cd0976'
OFFSET = 0x5a199
BEFORE = bytes.fromhex('807850000f85df080000')
CAVE = 0x42c1a
PLACE = 0x32c5cc


def jump(source, target, opcode=b'\xe9'):
    return opcode + struct.pack('<i', target - source - len(opcode) - 4)


def patch(data):
    if hashlib.sha256(data).hexdigest() != EXPECTED or data[OFFSET:OFFSET+10] != BEFORE:
        raise ValueError('MangoApp build differs; refusing native patch')
    # The first display element is FPS. After it, place==1: skip only
    # its separator. Every other row follows the original draw path.
    if data[CAVE-2:CAVE] != b'\xeb\x54':
        raise ValueError('Verified unreachable alignment padding changed')
    code = b'\x83\x3d' + struct.pack('<i', PLACE - (CAVE+7)) + b'\x01'
    code += jump(CAVE+len(code), 0x5a1e4, b'\x0f\x84')
    code += BEFORE[:4]
    code += jump(CAVE+len(code), 0x5aa82, b'\x0f\x85')
    code += jump(CAVE+len(code), 0x5a1a3)
    assert len(code) <= 38
    result = bytearray(data)
    result[OFFSET:OFFSET+10] = jump(OFFSET, CAVE) + b'\x90'*5
    result[CAVE:CAVE+len(code)] = code
    return bytes(result)


if __name__ == '__main__':
    root = Path('/home/deck/.local/share/hhd-mangoapp')
    root.mkdir(parents=True, exist_ok=True)
    target = root / 'mangoapp'
    temporary = target.with_suffix('.tmp')
    temporary.write_bytes(patch(Path('/usr/bin/mangoapp').read_bytes()))
    temporary.chmod(0o755)
    os.replace(temporary, target)
    launcher = root / 'launch'
    launcher.write_text('#!/bin/sh\n'
                        f'if [ "$(sha256sum /usr/bin/mangoapp | cut -d " " -f1)" = "{EXPECTED}" ]; then\n'
                        f'  exec {target}\nfi\nexec /usr/bin/mangoapp\n')
    launcher.chmod(0o755)
    override = Path('/home/deck/.config/systemd/user/gamescope-mangoapp.service.d/90-output-hud.conf')
    backup = override.with_suffix('.conf.before-no-separators')
    if not backup.exists():
        backup.write_bytes(override.read_bytes())
    override.write_text('[Service]\nExecStart=\nExecStart=/usr/bin/env -u MANGOHUD_CONFIG '
                        'MANGOHUD_CONFIGFILE=/home/deck/.config/MangoHud/output-hud.conf '
                        f'{launcher}\n')
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'restart', 'gamescope-mangoapp.service'], check=True)
