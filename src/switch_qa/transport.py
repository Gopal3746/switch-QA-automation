"""Command transport abstractions for Cumulus Linux switches."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Protocol, Self, runtime_checkable

from switch_qa.config import SSHConfig


@dataclass(frozen=True)
class CommandResult:
    """Captured result from a remote command."""

    command: str
    stdout: str
    stderr: str
    exit_code: int

    @property
    def succeeded(self) -> bool:
        """Return whether the command completed successfully."""

        return self.exit_code == 0


class TransportNotConnectedError(RuntimeError):
    """Raised when a command is attempted without an active connection."""


class CommandExecutionError(RuntimeError):
    """Raised when a checked command returns a nonzero exit status."""

    def __init__(self, result: CommandResult) -> None:
        message = (
            f"command {result.command!r} exited with status "
            f"{result.exit_code}: {result.stderr.strip()}"
        )
        super().__init__(message)
        self.result = result


@runtime_checkable
class CommandTransport(Protocol):
    """Interface implemented by real and simulated switch transports."""

    def connect(self) -> None:
        """Open the command transport."""

    def disconnect(self) -> None:
        """Close the command transport."""

    def run_command(
        self,
        command: str,
        *,
        timeout: float = 15.0,
        check: bool = False,
    ) -> CommandResult:
        """Execute a command and capture its output."""


ClientFactory = Callable[[], Any]


class ParamikoTransport:
    """SSH command transport backed by Paramiko."""

    def __init__(
        self,
        config: SSHConfig,
        *,
        password: str | None = None,
        connection_timeout: float = 10.0,
        accept_unknown_host_keys: bool = False,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self.config = config
        self.password = password
        self.connection_timeout = connection_timeout
        self.accept_unknown_host_keys = accept_unknown_host_keys
        self._client_factory = client_factory
        self._client: Any | None = None

    @property
    def connected(self) -> bool:
        """Return whether this transport currently has an SSH client."""

        return self._client is not None

    def connect(self) -> None:
        """Create and connect a Paramiko SSH client."""

        if self.connected:
            return

        import paramiko

        client = (
            self._client_factory()
            if self._client_factory is not None
            else paramiko.SSHClient()
        )

        client.load_system_host_keys()

        if self.accept_unknown_host_keys:
            policy = paramiko.AutoAddPolicy()
        else:
            policy = paramiko.RejectPolicy()

        client.set_missing_host_key_policy(policy)
        client.connect(
            hostname=self.config.host,
            port=self.config.port,
            username=self.config.username,
            key_filename=self.config.key_filename,
            password=self.password,
            timeout=self.connection_timeout,
        )

        self._client = client

    def disconnect(self) -> None:
        """Close the active SSH client."""

        if self._client is not None:
            self._client.close()
            self._client = None

    def run_command(
        self,
        command: str,
        *,
        timeout: float = 15.0,
        check: bool = False,
    ) -> CommandResult:
        """Execute a command over SSH and return all captured output."""

        if self._client is None:
            raise TransportNotConnectedError(
                "SSH transport is not connected; call connect() first"
            )

        _stdin, stdout, stderr = self._client.exec_command(
            command,
            timeout=timeout,
        )

        result = CommandResult(
            command=command,
            stdout=self._decode_output(stdout.read()),
            stderr=self._decode_output(stderr.read()),
            exit_code=stdout.channel.recv_exit_status(),
        )

        if check and not result.succeeded:
            raise CommandExecutionError(result)

        return result

    @staticmethod
    def _decode_output(output: bytes | str) -> str:
        if isinstance(output, bytes):
            return output.decode("utf-8", errors="replace")
        return output

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.disconnect()
