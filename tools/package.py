"""Build a deterministic Decky ZIP from an explicit runtime-file allowlist."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent
FILES = ['main.py', 'plugin.json', 'package.json', 'dist/index.js',
         'LICENSE', 'README.md', 'NOTICE.md',
         'licenses/hhd-LICENSE', 'licenses/adjustor-LICENSE']


def package(output=None):
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    output = Path(output) if output else ROOT / 'artifacts'
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'hhd-decky-{version}.zip'
    if (ROOT / 'index.js').read_bytes() != (ROOT / 'dist/index.js').read_bytes():
        raise ValueError('Frontend build is stale: run node tools/build.js')
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name in FILES:
            entry = zipfile.ZipInfo('hhd-decky/' + name, (2000, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(entry, (ROOT / name).read_bytes().replace(b'\r\n', b'\n'))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    return archive


if __name__ == '__main__':
    print(package())
