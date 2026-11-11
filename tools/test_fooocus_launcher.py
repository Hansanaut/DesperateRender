from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from services.fooocus_launcher import FooocusLauncher


def test_default_configuration() -> None:
    launcher = FooocusLauncher()

    assert launcher.host == "127.0.0.1"
    assert launcher.port == 7865
    assert launcher.launcher is None


def test_explicit_launcher_path() -> None:
    launcher = FooocusLauncher(Path("~/Fooocus"))

    assert launcher.launcher == Path("~/Fooocus").expanduser()


def test_environment_override() -> None:
    with patch.dict(
        "os.environ",
        {FooocusLauncher.LAUNCHER_ENV: r"/tmp/Fooocus"},
        clear=False,
    ):
        launcher = FooocusLauncher()

    assert launcher.launcher == Path("/tmp/Fooocus")


def test_directory_resolves_python_entrypoint(tmp_path: Path) -> None:
    run_py = tmp_path / "run.py"
    run_py.write_text("print('fooocus')", encoding="utf-8")

    launcher = FooocusLauncher(tmp_path)

    command, use_shell, resolved = launcher._build_command()

    assert command == [__import__("sys").executable, str(run_py)]
    assert use_shell is False
    assert resolved == run_py


def test_directory_prefers_run_py_over_shell_launchers(tmp_path: Path) -> None:
    run_py = tmp_path / "run.py"
    run_sh = tmp_path / "run.sh"
    run_py.write_text("", encoding="utf-8")
    run_sh.write_text("", encoding="utf-8")

    launcher = FooocusLauncher(tmp_path)
    _, _, resolved = launcher._build_command()

    assert resolved == run_py


def test_missing_launcher_fails_cleanly(tmp_path: Path) -> None:
    launcher = FooocusLauncher(tmp_path / "does-not-exist")

    assert launcher.start() is False
    assert launcher.started_by_promptlab is False


def test_start_marks_process_as_promptlab_owned(tmp_path: Path) -> None:
    run_py = tmp_path / "run.py"
    run_py.write_text("", encoding="utf-8")
    fake_process = MagicMock()
    fake_process.poll.return_value = None

    launcher = FooocusLauncher(tmp_path)

    with patch.object(launcher, "is_available", return_value=False), patch(
        "services.fooocus_launcher.subprocess.Popen",
        return_value=fake_process,
    ) as popen:
        assert launcher.start() is True

    popen.assert_called_once()
    assert launcher.process is fake_process
    assert launcher.started_by_promptlab is True


def test_start_does_not_spawn_when_service_is_already_available() -> None:
    launcher = FooocusLauncher()

    with patch.object(launcher, "is_available", return_value=True), patch(
        "services.fooocus_launcher.subprocess.Popen"
    ) as popen:
        assert launcher.start() is True

    popen.assert_not_called()
    assert launcher.started_by_promptlab is False


def test_stop_does_not_touch_process_not_owned_by_promptlab() -> None:
    launcher = FooocusLauncher()
    launcher.process = MagicMock()
    launcher.started_by_promptlab = False

    assert launcher.stop_if_started() is False
    launcher.process.terminate.assert_not_called()


def test_stop_terminates_owned_process() -> None:
    launcher = FooocusLauncher()
    fake_process = MagicMock()
    fake_process.poll.return_value = None
    launcher.process = fake_process
    launcher.started_by_promptlab = True

    assert launcher.stop_if_started() is True

    fake_process.terminate.assert_called_once()
    fake_process.wait.assert_called_once_with(timeout=5)
    assert launcher.process is None
    assert launcher.started_by_promptlab is False
