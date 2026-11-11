from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path
from subprocess import Popen


class FooocusLauncher:
    """Cross-platform local Fooocus process launcher."""

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 7865
    LAUNCHER_ENV = "DESPERATE_RENDER_FOOOCUS_LAUNCHER"

    def __init__(
        self,
        launcher: str | Path | None = None,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        configured_path = launcher or os.environ.get(self.LAUNCHER_ENV)
        self.launcher = Path(configured_path).expanduser() if configured_path else None
        self.host = host
        self.port = port
        self.process: Popen | None = None
        self.started_by_promptlab = False

    def set_launcher(self, launcher: str | Path | None) -> None:
        self.launcher = Path(launcher).expanduser() if launcher else None

    def is_available(self, timeout: float = 0.25) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout):
                return True
        except OSError:
            return False

    def _resolve_launcher(self) -> Path | None:
        if self.launcher is None:
            return None
        path = self.launcher
        if path.is_file():
            return path
        if path.is_dir():
            # A directory is the user-facing setting. Prefer the normal
            # cross-platform Python entry point, then shell launchers.
            for name in ("run.py", "run.sh", "run.bat", "run.cmd"):
                candidate = path / name
                if candidate.is_file():
                    return candidate
        return None

    def _build_command(self) -> tuple[list[str] | str, bool, Path] | None:
        launcher = self._resolve_launcher()
        if launcher is None:
            if self.launcher is None:
                print("Fooocus path is not configured.")
            else:
                print(f"Fooocus launcher not found: {self.launcher}")
            return None

        suffix = launcher.suffix.lower()
        if suffix == ".py":
            return [sys.executable, str(launcher)], False, launcher
        if suffix in {".bat", ".cmd", ".sh"}:
            return str(launcher), True, launcher
        return [str(launcher)], False, launcher

    def start(self) -> bool:
        if self.is_available():
            self.started_by_promptlab = False
            return True

        command = self._build_command()
        if command is None:
            return False

        command_value, use_shell, launcher = command
        try:
            self.process = subprocess.Popen(
                command_value,
                cwd=str(launcher.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=use_shell,
                start_new_session=True,
            )
        except (OSError, ValueError) as exc:
            print(f"Could not start Fooocus: {exc}")
            self.process = None
            self.started_by_promptlab = False
            return False

        self.started_by_promptlab = True
        return True

    def started_process_is_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop_if_started(self) -> bool:
        if not self.started_by_promptlab:
            return False

        process = self.process
        self.process = None
        self.started_by_promptlab = False

        if process is None or process.poll() is not None:
            return False

        try:
            if os.name == "nt":
                # Fooocus is commonly launched through run.bat/cmd.exe.
                # Terminating only cmd.exe can leave the actual Fooocus
                # process alive, so Windows uses the native process-tree
                # termination command here. This is isolated to the
                # platform-specific lifecycle path.
                subprocess.run(
                    [
                        "taskkill",
                        "/PID",
                        str(process.pid),
                        "/T",
                        "/F",
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=5,
                )
            else:
                os.killpg(process.pid, 15)
                process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(process.pid, 9)
                    process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
        return True
