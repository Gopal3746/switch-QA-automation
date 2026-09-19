from __future__ import annotations

from typing import Any

import pytest

from switch_qa.config import SSHConfig
from switch_qa.transport import (
    CommandExecutionError,
    ParamikoTransport,
    TransportNotConnectedError,
)


class FakeChannel:
    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code

    def recv_exit_status(self) -> int:
        return self.exit_code


class FakeStream:
    def __init__(
        self,
        content: bytes,
        *,
        exit_code: int = 0,
    ) -> None:
        self.content = content
        self.channel = FakeChannel(exit_code)

    def read(self) -> bytes:
        return self.content


class FakeSSHClient:
    def __init__(
        self,
        *,
        stdout: bytes = b"",
        stderr: bytes = b"",
        exit_code: int = 0,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.connection_arguments: dict[str, Any] | None = None
        self.executed_commands: list[tuple[str, float]] = []
        self.host_keys_loaded = False
        self.host_key_policy: Any | None = None
        self.closed = False

    def load_system_host_keys(self) -> None:
        self.host_keys_loaded = True

    def set_missing_host_key_policy(self, policy: Any) -> None:
        self.host_key_policy = policy

    def connect(self, **arguments: Any) -> None:
        self.connection_arguments = arguments

    def exec_command(
        self,
        command: str,
        *,
        timeout: float,
    ) -> tuple[None, FakeStream, FakeStream]:
        self.executed_commands.append((command, timeout))

        return (
            None,
            FakeStream(self.stdout, exit_code=self.exit_code),
            FakeStream(self.stderr),
        )

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def ssh_config() -> SSHConfig:
    return SSHConfig(
        host="192.0.2.10",
        port=22,
        username="cumulus",
        key_filename="/tmp/test-key",
    )


def test_connect_uses_configured_ssh_settings(
    ssh_config: SSHConfig,
) -> None:
    client = FakeSSHClient()
    transport = ParamikoTransport(
        ssh_config,
        client_factory=lambda: client,
    )

    transport.connect()

    assert transport.connected
    assert client.host_keys_loaded
    assert client.connection_arguments == {
        "hostname": "192.0.2.10",
        "port": 22,
        "username": "cumulus",
        "key_filename": "/tmp/test-key",
        "password": None,
        "timeout": 10.0,
    }


def test_run_command_captures_output(
    ssh_config: SSHConfig,
) -> None:
    client = FakeSSHClient(
        stdout=b"swp1 up\n",
        stderr=b"",
    )
    transport = ParamikoTransport(
        ssh_config,
        client_factory=lambda: client,
    )
    transport.connect()

    result = transport.run_command(
        "nv show interface swp1",
        timeout=20.0,
    )

    assert result.command == "nv show interface swp1"
    assert result.stdout == "swp1 up\n"
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.succeeded
    assert client.executed_commands == [
        ("nv show interface swp1", 20.0)
    ]


def test_checked_command_raises_for_nonzero_exit(
    ssh_config: SSHConfig,
) -> None:
    client = FakeSSHClient(
        stderr=b"unknown interface\n",
        exit_code=1,
    )
    transport = ParamikoTransport(
        ssh_config,
        client_factory=lambda: client,
    )
    transport.connect()

    with pytest.raises(CommandExecutionError) as captured:
        transport.run_command(
            "nv show interface missing",
            check=True,
        )

    assert captured.value.result.exit_code == 1
    assert captured.value.result.stderr == "unknown interface\n"


def test_command_requires_active_connection(
    ssh_config: SSHConfig,
) -> None:
    transport = ParamikoTransport(
        ssh_config,
        client_factory=FakeSSHClient,
    )

    with pytest.raises(
        TransportNotConnectedError,
        match="call connect",
    ):
        transport.run_command("nv show interface")


def test_context_manager_disconnects_client(
    ssh_config: SSHConfig,
) -> None:
    client = FakeSSHClient()

    with ParamikoTransport(
        ssh_config,
        client_factory=lambda: client,
    ) as transport:
        assert transport.connected

    assert client.closed
    assert not transport.connected
