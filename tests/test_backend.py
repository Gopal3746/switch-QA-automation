"""Tests for runtime transport backend selection."""

import pytest

from switch_qa.backend import (
    BackendConfigurationError,
    TransportBackend,
    build_transport,
)
from switch_qa.config import load_topology
from switch_qa.simulated_transport import SimulatedTransport
from switch_qa.simulation import SimulatedTopologyState
from switch_qa.transport import ParamikoTransport


def test_build_simulated_transport() -> None:
    topology = load_topology()
    state = SimulatedTopologyState.from_config(topology)

    transport = build_transport(
        "switch1",
        topology,
        backend=TransportBackend.SIMULATED,
        state=state,
    )

    assert isinstance(transport, SimulatedTransport)
    assert transport.switch_name == "switch1"
    assert transport.state is state


def test_simulated_transport_requires_state() -> None:
    topology = load_topology()

    with pytest.raises(
        BackendConfigurationError,
        match="requires topology state",
    ):
        build_transport(
            "switch1",
            topology,
            backend="simulated",
        )


def test_build_ssh_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWITCH1_HOST", "192.0.2.10")
    monkeypatch.setenv("SWITCH1_USER", "cumulus")
    monkeypatch.setenv(
        "SWITCH1_SSH_KEY",
        "/tmp/test-switch-key",
    )

    topology = load_topology()

    transport = build_transport(
        "switch1",
        topology,
        backend="ssh",
        password="test-password",
        accept_unknown_host_keys=True,
    )

    assert isinstance(transport, ParamikoTransport)
    assert transport.config.host == "192.0.2.10"
    assert transport.config.username == "cumulus"
    assert transport.config.key_filename == ("/tmp/test-switch-key")
    assert transport.password == "test-password"
    assert transport.accept_unknown_host_keys


def test_ssh_backend_rejects_unresolved_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SWITCH1_HOST", raising=False)
    monkeypatch.setenv("SWITCH1_USER", "cumulus")
    monkeypatch.delenv("SWITCH1_SSH_KEY", raising=False)

    topology = load_topology()

    with pytest.raises(
        BackendConfigurationError,
        match="unresolved SSH host",
    ):
        build_transport(
            "switch1",
            topology,
            backend="ssh",
        )


def test_unresolved_optional_key_becomes_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWITCH1_HOST", "192.0.2.10")
    monkeypatch.setenv("SWITCH1_USER", "cumulus")
    monkeypatch.delenv("SWITCH1_SSH_KEY", raising=False)

    topology = load_topology()

    transport = build_transport(
        "switch1",
        topology,
        backend="ssh",
    )

    assert isinstance(transport, ParamikoTransport)
    assert transport.config.key_filename is None


def test_unknown_backend_is_rejected() -> None:
    topology = load_topology()

    with pytest.raises(
        BackendConfigurationError,
        match="unsupported backend",
    ):
        build_transport(
            "switch1",
            topology,
            backend="telnet",
        )


def test_unknown_switch_is_rejected() -> None:
    topology = load_topology()
    state = SimulatedTopologyState.from_config(topology)

    with pytest.raises(
        BackendConfigurationError,
        match="unknown switch",
    ):
        build_transport(
            "switch99",
            topology,
            backend="simulated",
            state=state,
        )
