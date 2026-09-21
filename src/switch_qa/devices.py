"""High-level APIs for switches and attached hosts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from switch_qa.transport import (
    CommandResult,
    CommandTransport,
)


class DeviceResponseError(ValueError):
    """Raised when device output cannot be parsed."""


class Switch:
    """High-level NVUE-aware interface to a Cumulus Linux switch."""

    def __init__(
        self,
        name: str,
        display_name: str,
        transport: CommandTransport,
    ) -> None:
        self.name = name
        self.display_name = display_name
        self.transport = transport

    def connect(self) -> None:
        """Connect the underlying command transport."""

        self.transport.connect()

    def disconnect(self) -> None:
        """Disconnect the underlying command transport."""

        self.transport.disconnect()

    def run_command(
        self,
        command: str,
        *,
        check: bool = False,
    ) -> CommandResult:
        """Run an arbitrary diagnostic command."""

        return self.transport.run_command(
            command,
            check=check,
        )

    def show_interfaces(
        self,
        interface: str | None = None,
    ) -> dict[str, Any]:
        """Return parsed NVUE interface information."""

        if interface is None:
            command = "nv show interface -o json"
        else:
            command = f"nv show interface {interface} -o json"

        result = self.run_command(command, check=True)

        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise DeviceResponseError(
                f"{self.name} returned invalid NVUE JSON"
            ) from error

        if not isinstance(output, dict):
            raise DeviceResponseError(
                f"{self.name} returned unexpected NVUE output"
            )

        return output

    def show_interface(
        self,
        interface: str,
    ) -> dict[str, Any]:
        """Return parsed data for one interface."""

        output = self.show_interfaces(interface)

        try:
            interface_data = output[interface]
        except KeyError as error:
            raise DeviceResponseError(
                f"{self.name} response omitted {interface}"
            ) from error

        if not isinstance(interface_data, dict):
            raise DeviceResponseError(
                f"{self.name}.{interface} data is not a mapping"
            )

        return interface_data

    def get_pvid(self, interface: str) -> int:
        """Return an interface's untagged VLAN ID."""

        data = self.show_interface(interface)

        try:
            value = data["bridge"]["domain"]["br_default"]["untagged"]
            return int(value)
        except (KeyError, TypeError, ValueError) as error:
            raise DeviceResponseError(
                f"could not read PVID for {self.name}.{interface}"
            ) from error

    def get_allowed_vlans(
        self,
        interface: str,
    ) -> list[int]:
        """Return the sorted VLANs permitted on an interface."""

        data = self.show_interface(interface)

        try:
            vlans = data["bridge"]["domain"]["br_default"]["vlan"]
            return sorted(int(vlan) for vlan in vlans)
        except (KeyError, TypeError, ValueError) as error:
            raise DeviceResponseError(
                f"could not read VLANs for {self.name}.{interface}"
            ) from error

    def get_admin_state(self, interface: str) -> str:
        """Return the administrative state of an interface."""

        data = self.show_interface(interface)

        try:
            return str(data["link"]["state"]["admin"])
        except (KeyError, TypeError) as error:
            raise DeviceResponseError(
                f"could not read admin state for {self.name}.{interface}"
            ) from error

    def get_operational_state(
        self,
        interface: str,
    ) -> str:
        """Return the operational state of an interface."""

        data = self.show_interface(interface)

        try:
            return str(data["link"]["state"]["oper"])
        except (KeyError, TypeError) as error:
            raise DeviceResponseError(
                f"could not read operational state for "
                f"{self.name}.{interface}"
            ) from error

    def bridge_vlan_show(self) -> str:
        """Return Linux bridge VLAN output."""

        return self.run_command(
            "bridge vlan show",
            check=True,
        ).stdout

    def ip_link_show(self, interface: str) -> str:
        """Return Linux link information for an interface."""

        return self.run_command(
            f"ip link show dev {interface}",
            check=True,
        ).stdout

    def ip_address_show(self, interface: str) -> str:
        """Return Linux address information."""

        return self.run_command(
            f"ip addr show dev {interface}",
            check=True,
        ).stdout

    def ip_route_show(self) -> str:
        """Return the Linux routing table."""

        return self.run_command(
            "ip route show",
            check=True,
        ).stdout

    def configure_trunk_vlan(
        self,
        interface: str,
        vlan: int,
        *,
        apply: bool = True,
    ) -> None:
        """Add an allowed VLAN to a trunk interface."""

        self.run_command(
            (
                f"nv set interface {interface} bridge domain "
                f"br_default vlan {vlan}"
            ),
            check=True,
        )

        if apply:
            self.apply_configuration()

    def configure_access_vlan(
        self,
        interface: str,
        vlan: int,
        *,
        apply: bool = True,
    ) -> None:
        """Set the access VLAN for an interface."""

        self.run_command(
            (
                f"nv set interface {interface} bridge domain "
                f"br_default access {vlan}"
            ),
            check=True,
        )

        if apply:
            self.apply_configuration()

    def set_admin_state(
        self,
        interface: str,
        state: str,
        *,
        apply: bool = True,
    ) -> None:
        """Set an interface's administrative state."""

        if state not in {"up", "down"}:
            raise ValueError("state must be either 'up' or 'down'")

        self.run_command(
            f"nv set interface {interface} link state {state}",
            check=True,
        )

        if apply:
            self.apply_configuration()

    def apply_configuration(self) -> None:
        """Apply pending NVUE configuration."""

        self.run_command("nv config apply", check=True)

    def save_configuration(self) -> None:
        """Persist the current NVUE configuration."""

        self.run_command("nv config save", check=True)


_PACKET_LOSS_PATTERN = re.compile(
    r"(?P<transmitted>\d+) packets transmitted,\s*"
    r"(?P<received>\d+) received,\s*"
    r"(?P<loss>[0-9.]+)% packet loss"
)


@dataclass(frozen=True)
class PingResult:
    """Parsed result from a Linux ping command."""

    target: str
    transmitted: int
    received: int
    packet_loss_percent: float
    output: str
    exit_code: int

    @property
    def reachable(self) -> bool:
        """Return whether at least one packet was received."""

        return self.received > 0


class Host:
    """Host endpoint that executes diagnostics through a transport."""

    def __init__(
        self,
        name: str,
        display_name: str,
        ip_address: str,
        transport: CommandTransport,
    ) -> None:
        self.name = name
        self.display_name = display_name
        self.ip_address = ip_address
        self.transport = transport

    def ping(
        self,
        target: str,
        *,
        count: int = 4,
    ) -> PingResult:
        """Ping a target and return parsed packet statistics."""

        if count < 1:
            raise ValueError("ping count must be at least 1")

        result = self.transport.run_command(
            f"ping -c {count} {target}",
        )
        match = _PACKET_LOSS_PATTERN.search(result.stdout)

        if match is None:
            raise DeviceResponseError(
                f"could not parse ping output for {target}"
            )

        return PingResult(
            target=target,
            transmitted=int(match.group("transmitted")),
            received=int(match.group("received")),
            packet_loss_percent=float(match.group("loss")),
            output=result.stdout,
            exit_code=result.exit_code,
        )
