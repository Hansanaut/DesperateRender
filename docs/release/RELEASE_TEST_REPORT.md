# Release candidate test report

**Report date:** 2026-11-04  
**Target:** Desperate Render 1.0 source-only release candidate  
**Test owner:** Project owner, Windows desktop

## Confirmed by user

### Environment and installation

- Python 3.14.6 (64-bit) available through the Windows Python Launcher.
- A separate project test folder was used; the working Git repository was not used as the release test folder.
- A virtual environment was created and the pinned dependencies installed successfully.
- `python -m compileall -q .` completed successfully.
- `main.py` opened the GUI successfully.
- `INSTALL.bat` ran successfully using the existing isolated `.venv`.
- `Start_DR.bat` started the application successfully.

### Fooocus and rendering

- Fooocus endpoint connected successfully at `http://127.0.0.1:7865`.
- Runtime inspection found task-creation dependency 67, generation dependency 68, and 153 inputs.
- One image generation completed successfully and the result appeared in Preview.
- Experiment persistence and result metadata were checked.
- Continue Run was tested; completed jobs were not duplicated.

### Experiment and matrix regression

- Prompt Blocks: Individual (3 jobs), All (1 job), Combination min 2/max 3 (4 jobs), and Permutation min 2/max 3 (12 jobs).
- Permutation counts: min 1/max 3 = 15; min 2/max 2 = 6; min 2/max 3 = 12; min 3/max 3 = 6.
- Guidance Scale Matrix: 2.0 / 4.0 / 6.0.
- Sharpness Matrix: 0.0 / 2.0 / 4.0.
- Resolution Matrix: configuration import and expected settings/queue validated.
- Loading, rating, exclusion, continuation, and resumption from a loaded experiment were reported working.

## Scope limitations

- The full automated Qt GUI test suite was not run.
- The `INSTALL.bat` branch that creates a brand-new `.venv` was not independently exercised by the final batch-script test; the script reused an existing isolated environment. Manual venv creation and dependency installation had been validated separately. This is accepted and documented for the source-only 1.0 release.
- Other operating systems and other Fooocus/Gradio versions are not certified.
- A non-fatal Qt warning appeared: `QFont::setPointSize: Point size <= 0 (-1)`. It did not prevent startup, connection, or generation; root cause remains open.

## Known post-release backlog

- Prompt Blocks operator display can be inconsistent with the Properties Matrix operator.
- Prompt Block remove-row control lacks a clearly visible X (tooltip only).
- Accepted V1 deviation: `_rslt.json` may be created even when zero images have succeeded.
- Investigate the non-fatal QFont warning in a post-release maintenance update; the owner accepts it for 1.0.

## Release conclusion

The owner-confirmed functional smoke and regression tests support the source-only candidate's core Windows workflow. They do not constitute complete automated test coverage, cross-platform certification, or a legal licensing opinion. The owner approved GPL-3.0-or-later and source-only publication on 2026-11-11. The pinned runtime dependency license-text review and notices are included in the archive. No Windows executable or installer is planned for Release 1.0.
