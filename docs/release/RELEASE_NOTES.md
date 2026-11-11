# Desperate Render 1.0.0

**A free, source-only release for Windows.**

Desperate Render is a desktop application for designing, managing, and running structured image-generation experiments with a separately installed local Fooocus instance.

## What's included

- Prompt and Prompt Block workflows: Individual, All, Combination, and Permutation
- Prompt and numeric parameter matrices, including Guidance Scale, Sharpness, and Resolution
- Generation queue, job status/details, and Fooocus integration
- Preview, result history, filtering, rating/exclusion, and export workflows
- Experiment JSON save/load and Continue Run behavior
- Windows installation and startup scripts

## Installation

1. Install Python 3.14 (64-bit) and the Windows Python Launcher (`py.exe`).
2. Download and extract the source archive.
3. Run `INSTALL.bat`.
4. Start your local Fooocus installation and make sure its Gradio endpoint is reachable.
5. Run `Start_DR.bat`.

Fooocus, model weights, and Python dependencies are not bundled. Dependencies are installed locally from the pinned `requirements.txt`.

See `README.md` for detailed setup instructions and troubleshooting notes.

## Validated environment

The release candidate was tested on Windows with Python 3.14.6 (64-bit) and a local Fooocus instance using Gradio 3.41.2. The owner confirmed installation, startup, connection, image generation, Preview, experiment persistence, Continue Run, and the listed matrix workflows.

## Known limitations

- Windows is the primary target; other operating systems are not certified.
- The first-time `.venv` creation branch of `INSTALL.bat` was not independently exercised in the final batch-script test. Manual virtual-environment creation and dependency installation were validated separately.
- A non-fatal Qt warning may appear at startup: `QFont::setPointSize: Point size <= 0 (-1)`. It did not prevent the tested workflows.
- The full automated Qt GUI test suite was not run.
- Some Prompt Blocks UX improvements remain in the post-release backlog.
- `_rslt.json` may be created even when no image has succeeded; this is an accepted V1 behavior.

## Distribution scope

This is a **source-only** release. No prebuilt Windows executable or installer is included or planned for Release 1.0. Fooocus is a separate application and must be installed independently.

## License

Desperate Render is distributed under **GPL-3.0-or-later**. See `LICENSE`, `COPYRIGHT.md`, and `docs/THIRD_PARTY_NOTICES.md`. Third-party dependencies retain their own licenses; the reviewed license texts and notices are included in `licenses/third_party/`.

This release documentation records the tested scope and known limitations. It is not a legal opinion or a claim of complete automated or cross-platform certification.
