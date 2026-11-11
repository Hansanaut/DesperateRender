# Third-party dependency notices — source-only release

**Review date:** 2026-11-11  
**Scope:** Desperate Render source-only release candidate; 26 direct runtime pins plus observed transitive dependency `sniffio`.

## 1. Scope and distribution model

This archive contains Desperate Render application source and documentation. It does **not** contain Python wheels, installed third-party package trees, Qt shared libraries, Shiboken native modules, Qt plugins, or a PyInstaller executable/installer. Dependencies are installed separately by the recipient from the pinned requirements.

The dependency license information below describes the separately installed packages. It does not relicense those packages under the Desperate Render GPL-3.0-or-later license.

The release is not a binary redistribution of Qt/PySide. Any future EXE/installer release requires a separate inventory of the exact Qt DLLs, plugins, native dependencies, notices, source offers, and relinking/replacement mechanism.

## 2. Runtime dependency inventory

Installed versions and license indications were collected from the tested `C:\Projekte\DesperateRender\.venv` on 2026-11-11. All 26 direct packages match `requirements.txt`. `sniffio` 1.3.1 is an observed transitive dependency.

| Package | Version | License indication in installed metadata |
|---|---:|---|
| anyio | 4.14.2 | MIT |
| certifi | 2026.7.22 | MPL-2.0 |
| charset-normalizer | 3.4.9 | MIT |
| click | 8.4.2 | BSD-3-Clause |
| colorama | 0.4.6 | BSD classifier |
| filelock | 3.32.2 | MIT |
| fsspec | 2026.7.0 | BSD-3-Clause |
| gradio-client | 0.5.0 | Apache-2.0 |
| h11 | 0.16.0 | MIT |
| hf-xet | 1.6.0 | Apache-2.0 |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.27.0 | BSD-3-Clause |
| huggingface-hub | 0.24.2 | Apache |
| idna | 3.18 | BSD-3-Clause |
| packaging | 26.2 | Apache-2.0 OR BSD-2-Clause |
| Pillow | 12.3.0 | MIT-CMU |
| PySide6 | 6.11.1 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Addons | 6.11.1 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PySide6_Essentials | 6.11.1 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| PyYAML | 6.0.3 | MIT |
| requests | 2.34.2 | Apache-2.0 |
| shiboken6 | 6.11.1 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| tqdm | 4.70.0 | MPL-2.0 AND MIT |
| typing-extensions | 4.16.0 | PSF-2.0 |
| urllib3 | 2.7.0 | MIT |
| websockets | 11.0.3 | BSD-3-Clause |
| sniffio (transitive) | 1.3.1 | MIT OR Apache-2.0 |

The exact installed metadata, file paths, sizes and SHA-256 values are retained in `docs/internal/release-audit/INSTALLED_DEPENDENCY_LICENSE_AUDIT_2026-11-11.txt`.

## 3. Qt for Python / PySide6 / Shiboken6 — content review completed

### Exact package evidence

The tested environment contains `PySide6`, `PySide6_Addons`, `PySide6_Essentials`, and `shiboken6`, all at version 6.11.1. Their installed metadata advertises:

`LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`

The installed wheels expose `LicenseRef-Qt-Commercial.txt` in their distribution records. That short file is **not** the LGPL or GPL text. It states that commercial licensees are governed by their separate written Qt agreement.

### Upstream source verification

The official Qt for Python source tag `6.11.1` contains the complete license texts in its `LICENSES/` directory:

- `LGPL-3.0-only.txt`
- `GPL-2.0-only.txt`
- `GPL-3.0-only.txt`
- `Qt-GPL-exception-1.0.txt`
- `LicenseRef-Qt-Commercial.txt`

The full standard LGPL-3.0, GPL-2.0 and GPL-3.0 texts, plus the two Qt-specific texts, are included under `licenses/third_party/qt/`. The authoritative versioned source copies are linked below.

### Desperate Render's Qt API use

A source scan of this release candidate found imports from:

- `PySide6.QtCore`
- `PySide6.QtGui`
- `PySide6.QtWidgets`
- `PySide6.QtTest` (test code)

No imports from Qt modules named in the Qt 6.11 GPLv3-only module list were found. The Qt 6.11 licensing page lists those GPLv3-only modules separately; Qt Core, Gui, Widgets and Test are not on that list.

The PySide6 metadata still exposes multiple licensing options. This review does not purport to select a private/commercial Qt license for the recipient. For this GPL-3.0-or-later application, the LGPLv3 option or GPLv3 option is the relevant open-source route; the GPL-2.0-only option should not be assumed to be the selected option for this application.

### Scope boundary

The PySide6 PyPI page states that the `PySide6` wheel is an alias for `PySide6_Essentials` and `PySide6_Addons` and describes the open-source/commercial licensing alternatives. The installed environment is not a redistributable Qt package bundle in this project archive.

Qt's own LGPL obligations must be addressed if Qt libraries are redistributed with a binary: Qt identifies, among other things, provision of license copies, acknowledgement, source availability for the Qt components used, and a relinking/replacement mechanism. This is why the Windows executable/installer remains excluded.

## 4. gradio-client 0.5.0 — content review completed

The installed package metadata reports Apache-2.0, but its installed distribution RECORD did not list a separate license file.

The upstream Gradio repository tag `gradio@3.41.2` was checked:

- `client/python/gradio_client/version.txt` identifies version `0.5.0`.
- `client/python/pyproject.toml` declares `license = "Apache-2.0"`.
- The repository-root `LICENSE` contains the complete Apache License, Version 2.0 text.

The full Apache-2.0 license text is included at `licenses/third_party/gradio-client/Apache-2.0.txt`. This resolves the missing-license-file evidence gap for the source-only notice inventory. The package itself remains separately installed and is not bundled in this archive.

## 5. Other direct dependencies — license text review completed

The complete installed license/notice texts available for the tested dependency set have been reviewed and retained under `licenses/third_party/python/`. This includes all 24 files from the installed export, plus the upstream Apache-2.0 text for `gradio-client==0.5.0` and both alternative license texts for transitive `sniffio==1.3.1`.

For `httpx==0.27.0` and `huggingface-hub==0.24.2`, the global export labels differed from the release pins, but the actual license-file byte lengths and SHA-256 values match the tested DR virtual environment audit exactly. The exact upstream tag contents were also hash-verified; see `docs/internal/release-audit/PINNED_DEPENDENCY_LICENSE_COMPARISON_2026-11-11.md`.

The detailed package-by-package findings, exact included file paths and SHA-256 values are recorded in `docs/internal/release-audit/PYTHON_DEPENDENCY_LICENSE_TEXT_REVIEW_2026-11-11.md`. The original metadata audit remains at `docs/internal/release-audit/INSTALLED_DEPENDENCY_LICENSE_AUDIT_2026-11-11.txt`.

No build-time dependency manifest is included in this source-only release. Any future executable distribution must separately pin and review the actual PyInstaller version and bootloader notices.

This is a technical license inventory, not a legal opinion. It does not certify future binary redistribution or replace a review of exact wheel/binary artifacts.

## 6. Qt third-party notices

Qt for Python's documentation explains that its third-party license acknowledgements apply to the third-party components actually used by an application. Its published list includes selected Material Icons used in a Qt documentation example; that example asset is not part of Desperate Render.

Qt itself separately publishes a third-party code inventory and SBOM for its Qt modules. These native Qt component notices are outside this source-only archive because no Qt runtime binaries are redistributed here. They must be included in any future Qt binary redistribution review.

## 7. Primary upstream sources

- PySide6 6.11.1 PyPI metadata: https://pypi.org/project/PySide6/6.11.1/
- Qt for Python 6.11.1 source archive: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.1-src/
- Qt for Python 6.11.1 source license directory: https://github.com/pyside/pyside-setup/tree/6.11.1/LICENSES
- Qt 6.11 licensing and GPLv3-only module list: https://doc.qt.io/qt-6.11/licensing.html
- Qt for Python third-party licenses: https://doc.qt.io/qtforpython-6/licenses.html
- Qt open-source LGPL obligations: https://www.qt.io/development/open-source-lgpl-obligations
- gradio-client 0.5.0 source tag: https://github.com/gradio-app/gradio/tree/gradio@3.41.2/client/python
- gradio-client 0.5.0 upstream license: https://github.com/gradio-app/gradio/blob/gradio@3.41.2/LICENSE
- Apache License 2.0: https://www.apache.org/licenses/LICENSE-2.0
- GNU LGPL 3.0: https://www.gnu.org/licenses/lgpl-3.0.html
- GNU GPL 2.0: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html
- GNU GPL 3.0: https://www.gnu.org/licenses/gpl-3.0.html

---

This document is a technical license inventory for the source-only release. It is not a legal opinion or a certification of all third-party binary components.
