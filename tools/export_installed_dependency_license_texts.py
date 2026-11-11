#!/usr/bin/env python3
"""Export installed third-party license/notice text files for a read-only review.

Run with the tested Desperate Render virtual-environment interpreter:
    .\.venv\Scripts\python.exe tools\export_installed_dependency_license_texts.py

The script does not install, remove, or modify packages. It only reads installed
distribution metadata/files and writes a ZIP plus a manifest under tools/.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import re
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tools"
ZIP_PATH = OUT_DIR / "installed_dependency_license_texts.zip"
MANIFEST_PATH = OUT_DIR / "installed_dependency_license_texts_manifest.txt"

EXPECTED = {
    "anyio", "certifi", "charset-normalizer", "click", "colorama", "filelock",
    "fsspec", "gradio-client", "h11", "hf-xet", "httpcore", "httpx",
    "huggingface-hub", "idna", "packaging", "pillow", "pyside6",
    "pyside6-addons", "pyside6-essentials", "pyyaml", "requests", "shiboken6",
    "tqdm", "typing-extensions", "urllib3", "websockets", "sniffio",
}
LICENSE_NAME = re.compile(
    r"(^|[/\\])(license|licence|copying|notice|copyright|authors)"
    r"([._-].*)?$",
    re.IGNORECASE,
)

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    found = {}
    missing = []
    for dist in metadata.distributions():
        name = (dist.metadata.get("Name") or "").lower().replace("_", "-")
        if name not in EXPECTED:
            continue
        version = dist.version
        files = []
        for entry in dist.files or ():
            rel = str(entry).replace("\\", "/")
            if not LICENSE_NAME.search(rel):
                continue
            path = Path(dist.locate_file(entry))
            if not path.is_file():
                continue
            # Avoid accidentally packaging executable/source files.
            if path.suffix.lower() in {".py", ".pyc", ".pyo", ".dll", ".pyd", ".exe"}:
                continue
            data = path.read_bytes()
            files.append((rel, data))
        found[name] = (version, files)

    for name in sorted(EXPECTED):
        if name not in found:
            missing.append(name)

    lines = [
        "Desperate Render — installed third-party license text export",
        f"Date: {date.today().isoformat()}",
        "Read-only export from the active Python environment.",
        "No package was installed, removed, or modified.",
        "",
    ]
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(found):
            version, files = found[name]
            lines.append(f"[{name}=={version}]")
            if not files:
                lines.append("No license/notice file found in distribution RECORD.")
            for rel, data in files:
                arcname = f"{name}/{rel}"
                archive.writestr(arcname, data)
                lines.append(f"{arcname} | {len(data)} bytes | SHA256 {sha256(data)}")
            lines.append("")
        lines.append("Packages not found: " + (", ".join(missing) if missing else "none"))
        lines.append(f"Packages found: {len(found)}/{len(EXPECTED)}")
    # Re-open to verify archive integrity and calculate the final ZIP hash.
    with zipfile.ZipFile(ZIP_PATH, "r") as archive:
        bad = archive.testzip()
    lines.append(f"ZIP SHA256: {sha256(ZIP_PATH.read_bytes())}")
    MANIFEST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if bad:
        raise RuntimeError(f"License export ZIP integrity failure: {bad}")
    print(f"Wrote {ZIP_PATH}")
    print(f"Wrote {MANIFEST_PATH}")
    print(f"Packages found: {len(found)}/{len(EXPECTED)}")
    print("No package was installed, removed, or modified.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
