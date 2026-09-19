"""Load and validate the switch QA topology configuration."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_TOPOLOGY_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "topology.yaml"
)

_ENVIRONMENT_VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class TopologyConfigError(ValueError):
    """Raised when a topology configuration is malformed."""


@dataclass(frozen=True)
class SSHConfig:
    """SSH connection settings for one switch."""

    host: str
    port: int
    username: str
    key_filename: str | None


@dataclass(frozen=True)
class PortConfig:
    """Expected configuration for one switch port."""

    name: str
    role: str
    expected_pvid: int | None
    expected_allowed_vlans: tuple[int, ...]
    peer_switch: str | None
    peer_port: str | None


@dataclass(frozen=True)
class SwitchConfig:
    """Configuration for one Cumulus Linux switch."""

    name: str
    display_name: str
    ssh: SSHConfig
    ports: dict[str, PortConfig]


@dataclass(frozen=True)
class HostConfig:
    """Host attachment and expected VLAN information."""

    name: str
    display_name: str
    switch: str
    port: str
    expected_vlan: int


@dataclass(frozen=True)
class TopologyConfig:
    """Complete validated test topology."""

    vlans: dict[int, str]
    switches: dict[str, SwitchConfig]
    hosts: dict[str, HostConfig]


def _expand_environment_variables(text: str) -> str:
    """Expand configured environment variables while preserving unset placeholders."""

    def replace(match: re.Match[str]) -> str:
        variable_name = match.group(1)
        return os.environ.get(variable_name, match.group(0))

    return _ENVIRONMENT_VARIABLE.sub(replace, text)


def _build_port(name: str, data: dict[str, Any]) -> PortConfig:
    peer = data.get("peer") or {}

    return PortConfig(
        name=name,
        role=str(data["role"]),
        expected_pvid=(
            int(data["expected_pvid"])
            if data.get("expected_pvid") is not None
            else None
        ),
        expected_allowed_vlans=tuple(
            int(vlan) for vlan in data.get("expected_allowed_vlans", [])
        ),
        peer_switch=peer.get("switch"),
        peer_port=peer.get("port"),
    )


def _build_switch(name: str, data: dict[str, Any]) -> SwitchConfig:
    ssh_data = data["ssh"]
    ports = {
        port_name: _build_port(port_name, port_data)
        for port_name, port_data in data["ports"].items()
    }

    return SwitchConfig(
        name=name,
        display_name=str(data.get("display_name", name)),
        ssh=SSHConfig(
            host=str(ssh_data["host"]),
            port=int(ssh_data.get("port", 22)),
            username=str(ssh_data["username"]),
            key_filename=ssh_data.get("key_filename"),
        ),
        ports=ports,
    )


def _build_host(name: str, data: dict[str, Any]) -> HostConfig:
    connection = data["connects_to"]

    return HostConfig(
        name=name,
        display_name=str(data.get("display_name", name)),
        switch=str(connection["switch"]),
        port=str(connection["port"]),
        expected_vlan=int(data["expected_vlan"]),
    )


def _validate_topology(topology: TopologyConfig) -> None:
    valid_roles = {"access", "trunk"}

    for switch in topology.switches.values():
        for port in switch.ports.values():
            if port.role not in valid_roles:
                raise TopologyConfigError(
                    f"{switch.name}.{port.name} has unsupported role {port.role!r}"
                )

            if port.role == "access" and port.expected_pvid is None:
                raise TopologyConfigError(
                    f"{switch.name}.{port.name} is missing expected_pvid"
                )

            if port.role == "trunk" and not port.expected_allowed_vlans:
                raise TopologyConfigError(
                    f"{switch.name}.{port.name} is missing expected_allowed_vlans"
                )

            referenced_vlans = set(port.expected_allowed_vlans)
            if port.expected_pvid is not None:
                referenced_vlans.add(port.expected_pvid)

            unknown_vlans = referenced_vlans - topology.vlans.keys()
            if unknown_vlans:
                raise TopologyConfigError(
                    f"{switch.name}.{port.name} references unknown VLANs "
                    f"{sorted(unknown_vlans)}"
                )

    for host in topology.hosts.values():
        if host.switch not in topology.switches:
            raise TopologyConfigError(
                f"{host.name} references unknown switch {host.switch!r}"
            )

        switch = topology.switches[host.switch]
        if host.port not in switch.ports:
            raise TopologyConfigError(
                f"{host.name} references unknown port {host.switch}.{host.port}"
            )

        if host.expected_vlan not in topology.vlans:
            raise TopologyConfigError(
                f"{host.name} references unknown VLAN {host.expected_vlan}"
            )


def load_topology(
    path: str | Path = DEFAULT_TOPOLOGY_PATH,
) -> TopologyConfig:
    """Load a YAML topology file and return a validated configuration."""

    config_path = Path(path)

    try:
        expanded_yaml = _expand_environment_variables(
            config_path.read_text(encoding="utf-8")
        )
        data = yaml.safe_load(expanded_yaml)

        if not isinstance(data, dict):
            raise TopologyConfigError("topology root must be a mapping")

        topology = TopologyConfig(
            vlans={
                int(vlan_id): str(name)
                for vlan_id, name in data["vlans"].items()
            },
            switches={
                name: _build_switch(name, switch_data)
                for name, switch_data in data["switches"].items()
            },
            hosts={
                name: _build_host(name, host_data)
                for name, host_data in data["hosts"].items()
            },
        )
    except TopologyConfigError:
        raise
    except (KeyError, TypeError, ValueError, yaml.YAMLError) as error:
        raise TopologyConfigError(
            f"invalid topology configuration: {error}"
        ) from error

    _validate_topology(topology)
    return topology
