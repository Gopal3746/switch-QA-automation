"""Runtime selection of simulated or SSH command transports."""

from __future__ import annotations

from dataclasses import replace
from enum import StrEnum

from switch_qa.config import SSHConfig, TopologyConfig
from switch_qa.simulated_transport import SimulatedTransport
from switch_qa.simulation import SimulatedTopologyState
from switch_qa.transport import (
    CommandTransport,
    ParamikoTransport,
)


class TransportBackend(StrEnum):
    """Supported command transport backends."""

    SIMULATED = "simulated"
    SSH = "ssh"


class BackendConfigurationError(ValueError):
    """Raised when a transport backend cannot be configured."""


def _is_unresolved_placeholder(value: str | None) -> bool:
    return bool(value and value.startswith("${") and value.endswith("}"))


def _prepare_ssh_config(
    switch_name: str,
    config: SSHConfig,
) -> SSHConfig:
    if _is_unresolved_placeholder(config.host):
        raise BackendConfigurationError(f"unresolved SSH host for {switch_name}: {config.host!r}")

    if _is_unresolved_placeholder(config.username):
        raise BackendConfigurationError(
            f"unresolved SSH username for {switch_name}: {config.username!r}"
        )

    key_filename = config.key_filename

    if _is_unresolved_placeholder(key_filename):
        key_filename = None

    return replace(
        config,
        key_filename=key_filename,
    )


def build_transport(
    switch_name: str,
    topology: TopologyConfig,
    *,
    backend: TransportBackend | str,
    state: SimulatedTopologyState | None = None,
    password: str | None = None,
    accept_unknown_host_keys: bool = False,
) -> CommandTransport:
    """Build a transport for one configured switch."""

    try:
        selected_backend = TransportBackend(backend)
    except ValueError as error:
        supported = ", ".join(candidate.value for candidate in TransportBackend)
        raise BackendConfigurationError(
            f"unsupported backend {backend!r}; expected one of: {supported}"
        ) from error

    try:
        switch_config = topology.switches[switch_name]
    except KeyError as error:
        raise BackendConfigurationError(f"unknown switch {switch_name!r}") from error

    if selected_backend is TransportBackend.SIMULATED:
        if state is None:
            raise BackendConfigurationError("simulated backend requires topology state")

        return SimulatedTransport(
            switch_name,
            state,
        )

    ssh_config = _prepare_ssh_config(
        switch_name,
        switch_config.ssh,
    )

    return ParamikoTransport(
        ssh_config,
        password=password,
        accept_unknown_host_keys=accept_unknown_host_keys,
    )
