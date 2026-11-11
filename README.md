# Desperate Render

Desperate Render (formerly PromptLAB) is a Windows-oriented desktop application for designing, managing, and running structured image-generation experiments against a separately installed local Fooocus instance.

It provides prompt and parameter management, experiment matrices, queued generation jobs, result history, preview filtering, and export workflows.

> **Release 1.0 scope:** source-only. This archive does not contain a supported prebuilt Windows executable or installer, a Fooocus installation, model weights, or generated experiment history. A prebuilt Windows executable or installer is not planned for Release 1.0; users run the source application locally after installing the pinned Python dependencies.

## Requirements

- Windows 10/11 (primary target; other platforms are not certified for this release)
- Python 3.14, 64-bit, with the Python Launcher (`py.exe`)
- A separately installed and running Fooocus instance with its Gradio interface enabled
- Enough disk space for Python dependencies, generated images, and experiment history

The current pinned dependency set was validated with Python 3.14.6 against a local Fooocus instance using Gradio 3.41.2. Other Fooocus versions may expose different API behavior.

## Installation and start (Windows)

1. Install Python 3.14 (64-bit) and ensure the Python Launcher is available.
2. Extract this archive to a writable folder.
3. Double-click `INSTALL.bat`. It creates `.venv` if needed and installs the pinned packages from `requirements.txt`. Existing `.venv` environments are reused.
4. Start Fooocus separately and make sure its Gradio endpoint is reachable.
5. Double-click `Start_DR.bat`.

The batch files keep their console window open so installation and runtime errors remain visible.

### Manual installation

From the project root in PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Fooocus connection

Desperate Render does **not** bundle Fooocus, its model weights, or its runtime. It connects to a separately installed Fooocus process through `gradio_client`.

Use the Fooocus address configured by your local installation. The commonly used local default in the development setup is `http://127.0.0.1:7865`; verify the actual address and port in your Fooocus environment.

Fooocus is an independent third-party project. Install it separately and comply with its own license and model/asset terms. No Fooocus source code or model weights are included here.

## Documentation

- `docs/DESPERATE_RENDER_AI_EXPERIMENT_CREATION_PLAYBOOK.md` — practical workflow for designing experiments
- `docs/DESPERATE_RENDER_AI_EXPERIMENT_JSON_GUIDE_REV2.md` — German AI reference for experiment JSON structure and constraints
- `docs/DESPERATE_RENDER_AI_EXPERIMENT_JSON_GUIDE_REV2_EN.md` — English AI reference for experiment JSON structure and constraints
- `docs/DESPERATE_RENDER_STYLE_GUIDE.md` — style selection and usage guidance
- `docs/THIRD_PARTY_NOTICES.md` — runtime dependency inventory and licensing notices
- `docs/release/RELEASE_NOTES.md` — Release 1.0.0 overview
- `docs/release/RELEASE_TEST_REPORT.md` — user-confirmed tests and known limitations
- `docs/internal/release-audit/ASSET_PROVENANCE.md` — asset provenance and evidence record

Detailed release-audit records are retained separately in `docs/internal/release-audit/`; they are not required for normal installation or use. Historical development notes and superseded design snapshots are not part of this public release package.

## Tests and release limitations

The project owner confirmed the core experiment workflows, matrix operators, save/load/continue behavior, Fooocus connection, image generation, and Preview behavior on Windows. See `docs/release/RELEASE_TEST_REPORT.md` for scope and remaining limitations.

This is not a claim that every automated test or every supported platform has been certified. The fresh-venv creation branch of `INSTALL.bat` has not yet been exercised separately; the isolated Python environment and dependency installation were previously created and validated manually, and the batch installer was then run successfully using that environment.

## License

Desperate Render is released under the GNU General Public License, version 3 or (at your option) any later version (GPL-3.0-or-later), as stated in `LICENSE`. See `docs/release/COPYRIGHT.md` for copyright information. Third-party dependencies are installed separately by the recipient; their licenses remain applicable. See `docs/THIRD_PARTY_NOTICES.md` and `licenses/third_party/` for the dependency inventory and included license texts.

The Windows/PyInstaller binary distribution is **not** part of this release. No binary redistribution or Qt/PySide LGPL compliance conclusion is implied by this source-only package.
