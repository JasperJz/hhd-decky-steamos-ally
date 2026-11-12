"""Package Quick Achievements as a standalone Decky plugin."""

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def build():
    source = Path(__file__).resolve().parent
    version = json.loads((source / "package.json").read_text(encoding="utf-8"))["version"]
    output = source.parent / "artifacts" / f"quick-achievements-{version}.zip"
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name in ("plugin.json", "package.json"):
            archive.write(source / name, f"quick-achievements/{name}")
        archive.write(source / "index.js", "quick-achievements/dist/index.js")
    return output


if __name__ == "__main__":
    print(build())
