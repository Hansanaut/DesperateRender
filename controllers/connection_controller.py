from __future__ import annotations

from models.application_settings import ApplicationSettings
from services.fooocus_client import FooocusClient
from services.fooocus_launcher import FooocusLauncher


class ConnectionController:
    """Handles the connection and local lifecycle of Fooocus."""

    def __init__(self, settings: ApplicationSettings | None = None) -> None:
        self.settings = settings or ApplicationSettings()
        self.client = FooocusClient(self.settings.fooocus_url)
        self.launcher = FooocusLauncher(self.settings.fooocus_path)

    def reload_settings(self) -> None:
        self.client = FooocusClient(self.settings.fooocus_url)
        self.launcher.set_launcher(self.settings.fooocus_path)

    def start_fooocus(self) -> bool:
        if not self.settings.fooocus_auto_start:
            return self.is_fooocus_available()
        return self.launcher.start()

    def is_fooocus_available(self) -> bool:
        return self.launcher.is_available()

    def connect(self) -> bool:
        return self.client.connect()

    def disconnect(self) -> None:
        self.client.disconnect()

    def stop_fooocus_if_started(self) -> bool:
        return self.launcher.stop_if_started()

    def is_connected(self) -> bool:
        return self.client.is_connected()
