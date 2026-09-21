"""Simulated NVUE and Linux command transport."""

from __future__ import annotations

import json
import re
from types import TracebackType
from typing import Self

from switch_qa.simulation import (
    SimulatedPortState,
    SimulatedTopologyState,
)
from switch_qa.transport import (
    CommandExecutionError,
    CommandResult,
    TransportNotConnectedError,
)


class SimulatedTransport:
    """Execute NVUE and Linux commands against in-memory switch state."""

    def __init__(
        self,
        switch_name: str,
        state: SimulatedTopologyState,
    ) -> None:
        if switch_name not in state.switches:
            raise ValueError(f"unknown simulated switch {switch_name!r}")

        self.switch_name = switch_name
        self.state = state
        self.connected = False
        self.command_history: list[str] = []

    def connect(self) -> None:
        """Open the simulated transport."""

        self.connected = True

    def disconnect(self) -> None:
        """Close the simulated transport."""

        self.connected = False

    def run_command(
        self,
        command: str,
        *,
        timeout: float = 15.0,
        check: bool = False,
    ) -> CommandResult:
        """Execute a supported command against the simulated topology."""

        del timeout

        if not self.connected:
            raise TransportNotConnectedError(
                "simulated transport is not connected; call connect() first"
            )

        normalized = " ".join(command.strip().split())
        self.command_history.append(normalized)

        result = self._dispatch(normalized)

        if check and not result.succeeded:
            raise CommandExecutionError(result)

        return result

    def _dispatch(self, command: str) -> CommandResult:
        show_match = re.fullmatch(
            r"nv show interface(?: (\S+))? (?:-o|--output) json",
            command,
        )
        if show_match:
            return self._show_interface(
                command,
                show_match.group(1),
            )

        if command == "bridge vlan show":
            return self._bridge_vlan_show(command)

        link_match = re.fullmatch(
            r"ip link show(?: dev)?(?: (\S+))?",
            command,
        )
        if link_match:
            return self._ip_link_show(
                command,
                link_match.group(1),
            )

        address_match = re.fullmatch(
            r"ip addr show(?: dev)?(?: (\S+))?",
            command,
        )
        if address_match:
            return self._ip_address_show(
                command,
                address_match.group(1),
            )

        if command == "ip route show":
            return self._success(
                command,
                (
                    "default via 192.0.2.1 dev eth0\n"
                    "10.0.10.0/24 dev vlan10 proto kernel\n"
                ),
            )

        ping_match = re.fullmatch(
            r"ping(?: -c (\d+))? (\S+)",
            command,
        )
        if ping_match:
            count = int(ping_match.group(1) or 4)
            target = ping_match.group(2)
            return self._ping(command, target, count)

        trunk_match = re.fullmatch(
            (
                r"nv set interface (\S+) bridge domain "
                r"br_default vlan (\d+)"
            ),
            command,
        )
        if trunk_match:
            return self._add_trunk_vlan(
                command,
                trunk_match.group(1),
                int(trunk_match.group(2)),
            )

        access_match = re.fullmatch(
            (
                r"nv set interface (\S+) bridge domain "
                r"br_default access (\d+)"
            ),
            command,
        )
        if access_match:
            return self._set_access_vlan(
                command,
                access_match.group(1),
                int(access_match.group(2)),
            )

        admin_match = re.fullmatch(
            r"nv set interface (\S+) link state (up|down)",
            command,
        )
        if admin_match:
            return self._set_admin_state(
                command,
                admin_match.group(1),
                admin_match.group(2),
            )

        if command == "nv config apply":
            return self._success(command, "applied\n")

        if command == "nv config save":
            self.state.save_config()
            return self._success(command, "saved\n")

        if command == "__simulate_reload__":
            self.state.reload()
            return self._success(command, "reloaded\n")

        return self._failure(
            command,
            f"unsupported simulated command: {command}\n",
            exit_code=127,
        )

    def _show_interface(
        self,
        command: str,
        port_name: str | None,
    ) -> CommandResult:
        ports = self.state.switches[self.switch_name]

        if port_name is not None:
            if port_name not in ports:
                return self._failure(
                    command,
                    f"unknown interface {port_name}\n",
                )

            selected_ports = {port_name: ports[port_name]}
        else:
            selected_ports = ports

        output = {
            name: self._interface_data(port)
            for name, port in selected_ports.items()
        }

        return self._success(
            command,
            json.dumps(output, indent=2) + "\n",
        )

    def _interface_data(
        self,
        port: SimulatedPortState,
    ) -> dict[str, object]:
        return {
            "type": port.role,
            "link": {
                "state": {
                    "admin": port.admin_state,
                    "oper": self.state.operational_state(
                        self.switch_name,
                        port.name,
                    ),
                }
            },
            "bridge": {
                "domain": {
                    "br_default": {
                        "untagged": port.pvid,
                        "vlan": sorted(port.allowed_vlans),
                    }
                }
            },
        }

    def _bridge_vlan_show(
        self,
        command: str,
    ) -> CommandResult:
        lines = ["port              vlan-id"]

        for port_name, port in self.state.switches[
            self.switch_name
        ].items():
            for vlan in sorted(port.allowed_vlans):
                suffix = ""

                if vlan == port.pvid:
                    suffix = " PVID Egress Untagged"

                lines.append(
                    f"{port_name:<18}{vlan}{suffix}"
                )

        return self._success(
            command,
            "\n".join(lines) + "\n",
        )

    def _ip_link_show(
        self,
        command: str,
        port_name: str | None,
    ) -> CommandResult:
        ports = self.state.switches[self.switch_name]

        if port_name is not None:
            if port_name not in ports:
                return self._failure(
                    command,
                    f'Device "{port_name}" does not exist.\n',
                    exit_code=1,
                )

            port = ports[port_name]
            admin_flag = (
                "UP"
                if port.admin_state == "up"
                else "DOWN"
            )
            operational = self.state.operational_state(
                self.switch_name,
                port_name,
            ).upper()

            output = (
                f"2: {port_name}: "
                f"<BROADCAST,MULTICAST,{admin_flag}> "
                f"mtu 9216 state {operational} mode DEFAULT\n"
            )
            return self._success(command, output)

        lines = []

        for index, name in enumerate(ports, start=2):
            operational = self.state.operational_state(
                self.switch_name,
                name,
            ).upper()
            lines.append(
                f"{index}: {name}: state {operational}"
            )

        return self._success(
            command,
            "\n".join(lines) + "\n",
        )

    def _ip_address_show(
        self,
        command: str,
        interface_name: str | None,
    ) -> CommandResult:
        interface = interface_name or "eth0"
        host_octet = 10 if self.switch_name == "switch1" else 11

        output = (
            f"{interface}: inet 192.0.2.{host_octet}/24 "
            f"scope global {interface}\n"
        )
        return self._success(command, output)

    def _ping(
        self,
        command: str,
        target: str,
        count: int,
    ) -> CommandResult:
        reachable = self.state.can_hosts_reach(
            "host_a",
            "host_b",
        )

        lines = [f"PING {target} 56(84) bytes of data."]

        if reachable:
            for sequence in range(1, count + 1):
                lines.append(
                    f"64 bytes from {target}: "
                    f"icmp_seq={sequence} ttl=64 time=0.3 ms"
                )

            lines.extend(
                [
                    "",
                    f"--- {target} ping statistics ---",
                    (
                        f"{count} packets transmitted, "
                        f"{count} received, 0% packet loss"
                    ),
                ]
            )

            return self._success(
                command,
                "\n".join(lines) + "\n",
            )

        lines.extend(
            [
                "",
                f"--- {target} ping statistics ---",
                (
                    f"{count} packets transmitted, "
                    "0 received, 100% packet loss"
                ),
            ]
        )

        return CommandResult(
            command=command,
            stdout="\n".join(lines) + "\n",
            stderr="",
            exit_code=1,
        )

    def _add_trunk_vlan(
        self,
        command: str,
        port_name: str,
        vlan: int,
    ) -> CommandResult:
        try:
            self.state.add_trunk_vlan(
                self.switch_name,
                port_name,
                vlan,
            )
        except (KeyError, ValueError) as error:
            return self._failure(command, f"{error}\n")

        return self._success(
            command,
            f"pending: {port_name} vlan {vlan} added\n",
        )

    def _set_access_vlan(
        self,
        command: str,
        port_name: str,
        vlan: int,
    ) -> CommandResult:
        try:
            self.state.set_access_vlan(
                self.switch_name,
                port_name,
                vlan,
            )
        except (KeyError, ValueError) as error:
            return self._failure(command, f"{error}\n")

        return self._success(
            command,
            f"pending: {port_name} access vlan set to {vlan}\n",
        )

    def _set_admin_state(
        self,
        command: str,
        port_name: str,
        admin_state: str,
    ) -> CommandResult:
        try:
            self.state.set_admin_state(
                self.switch_name,
                port_name,
                admin_state,
            )
        except (KeyError, ValueError) as error:
            return self._failure(command, f"{error}\n")

        return self._success(
            command,
            (
                f"pending: {port_name} admin state "
                f"set to {admin_state}\n"
            ),
        )

    @staticmethod
    def _success(
        command: str,
        stdout: str,
    ) -> CommandResult:
        return CommandResult(
            command=command,
            stdout=stdout,
            stderr="",
            exit_code=0,
        )

    @staticmethod
    def _failure(
        command: str,
        stderr: str,
        *,
        exit_code: int = 1,
    ) -> CommandResult:
        return CommandResult(
            command=command,
            stdout="",
            stderr=stderr,
            exit_code=exit_code,
        )

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
