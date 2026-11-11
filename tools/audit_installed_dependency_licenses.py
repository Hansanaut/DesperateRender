"""Read-only inventory of installed Python distribution license metadata.
Run from the Desperate Render root with .venv active or its Python executable.
Writes tools/installed_dependency_license_audit.txt; does not modify installed packages.
"""
from importlib import metadata
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tools" / "installed_dependency_license_audit.txt"
EXPECTED = {
    "anyio": "4.14.2", "certifi": "2026.7.22", "charset-normalizer": "3.4.9",
    "click": "8.4.2", "colorama": "0.4.6", "filelock": "3.32.2",
    "fsspec": "2026.7.0", "gradio-client": "0.5.0", "h11": "0.16.0",
    "hf-xet": "1.6.0", "httpcore": "1.0.9", "httpx": "0.27.0",
    "huggingface-hub": "0.24.2", "idna": "3.18", "packaging": "26.2",
    "pillow": "12.3.0", "pyside6": "6.11.1", "pyside6-addons": "6.11.1",
    "pyside6-essentials": "6.11.1", "pyyaml": "6.0.3", "requests": "2.34.2",
    "shiboken6": "6.11.1", "tqdm": "4.70.0", "typing-extensions": "4.16.0",
    "urllib3": "2.7.0", "websockets": "11.0.3",
}
def norm(s): return s.lower().replace('_','-').replace('.','-')
lines=["Desperate Render — installed dependency license metadata audit", "Read-only; generated from the active Python environment.", ""]
found={}
for d in metadata.distributions():
    name=d.metadata.get('Name','')
    if not name: continue
    key=norm(name)
    if key not in {norm(x) for x in EXPECTED}: continue
    found[key]=(d,name)
for pkg, expected in EXPECTED.items():
    key=norm(pkg)
    lines += [f"## {pkg} (expected {expected})"]
    if key not in found:
        lines += ["NOT INSTALLED / METADATA NOT FOUND", ""]
        continue
    d,name=found[key]
    md=d.metadata
    lines += [f"Installed version: {d.version}", f"Version matches requirements pin: {d.version == expected}",
              f"License-Expression: {md.get('License-Expression','')}",
              f"License: {md.get('License','')}"]
    classifiers=[x for x in md.get_all('Classifier',[]) if x.startswith('License ::')]
    lines += ["License classifiers: " + ('; '.join(classifiers) if classifiers else '(none)')]
    licfiles=[]
    for f in d.files or []:
        low=str(f).lower()
        if 'license' in low or 'copying' in low or 'notice' in low or 'copyright' in low:
            p=d.locate_file(f)
            if p.is_file():
                b=p.read_bytes(); licfiles.append((str(f),len(b),hashlib.sha256(b).hexdigest()))
    if licfiles:
        lines.append("Bundled license/notice files:")
        lines.extend([f"- {n} | {size} bytes | SHA256 {sha}" for n,size,sha in licfiles])
    else: lines.append("Bundled license/notice files: none found via distribution RECORD")
    lines.append("")
missing=[p for p in EXPECTED if norm(p) not in found]
lines += ["## Additional transitive dependency", "sniffio is expected transitively; record its installed version and license metadata if present."]
try:
    d=metadata.distribution('sniffio')
    lines += [f"sniffio version: {d.version}", f"sniffio License-Expression: {d.metadata.get('License-Expression','')}", f"sniffio License: {d.metadata.get('License','')}"]
except metadata.PackageNotFoundError: lines += ["sniffio: not installed"]
lines += ["", "## Summary", f"Expected packages missing: {', '.join(missing) if missing else 'none'}"]
OUT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(f"Wrote {OUT}")
print(f"Expected packages found: {len(found)}/{len(EXPECTED)}")
print("No package was installed, removed, or modified.")
