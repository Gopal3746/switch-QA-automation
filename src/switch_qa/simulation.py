"""In-memory model of the two-switch Cumulus Linux topology."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from switch_qa.config import TopologyConfig


@dataclass
class SimulatedPortState:
    """Mutable runtime state for one simulated switch port."""

    name: str
    role: str
    pvid: int
    allowed_vlans: set[int]
    admin_state: str = "up"
    peer_switch: str | None = None
    peer_port: str | None = None


@dataclass
class SimulatedTopologyState:
    """Shared state used by all simulated switch transports."""

    config: TopologyConfig
    switches: dict[str, dict[str, SimulatedPortState]]
    scenario: str = "fixed"
    _saved_switches: dict[str, dict[str, SimulatedPortState]] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if self.scenario not in {"fixed", "buggy"}:
            raise ValueError(
                "scenario must be either 'fixed' or 'buggy'"
            )

        if self.scenario == "buggy":
            self.inject_missing_trunk_vlan()
            self.inject_incorrect_access_pvid()

        self.save_config()

    @classmethod
    def from_config(
        cls,
        config: TopologyConfig,
        *,
        scenario: str = "fixed",
    ) -> SimulatedTopologyState:
        """Build simulated runtime state from validated topology data."""

        switches: dict[str, dict[str, SimulatedPortState]] = {}

        for switch_name, switch_config in config.switches.items():
            ports: dict[str, SimulatedPortState] = {}

            for port_name, port_config in switch_config.ports.items():
                if port_config.role == "access":
                    assert port_config.expected_pvid is not None
                    pvid = port_config.expected_pvid
                    allowed_vlans = {pvid}
                else:
                    pvid = 1
                    allowed_vlans = set(
                        port_config.expected_allowed_vlans
                    )

                ports[port_name] = SimulatedPortState(
                    name=port_name,
                    role=port_config.role,
                    pvid=pvid,
                    allowed_vlans=allowed_vlans,
                    peer_switch=port_config.peer_switch,
                    peer_port=port_config.peer_port,
                )

            switches[switch_name] = ports

        return cls(
            config=config,
            switches=switches,
            scenario=scenario,
        )

    def port(
        self,
        switch_name: str,
        port_name: str,
    ) -> SimulatedPortState:
        """Return the current state of a particular switch port."""

        return self.switches[switch_name][port_name]

    def inject_missing_trunk_vlan(self) -> None:
        """Inject BUG-001 by removing VLAN 10 from switch2's trunk."""

        self.port("switch2", "swp1").allowed_vlans.discard(10)

    def inject_incorrect_access_pvid(self) -> None:
        """Inject BUG-002 by assigning Host A's port to VLAN 20."""

        port = self.port("switch1", "swp1")
        port.pvid = 20
        port.allowed_vlans = {20}

    def add_trunk_vlan(
        self,
        switch_name: str,
        port_name: str,
        vlan: int,
    ) -> None:
        """Add an allowed VLAN to a trunk port."""

        port = self.port(switch_name, port_name)

        if port.role != "trunk":
            raise ValueError(
                f"{switch_name}.{port_name} is not a trunk port"
            )

        port.allowed_vlans.add(vlan)

    def set_access_vlan(
        self,
        switch_name: str,
        port_name: str,
        vlan: int,
    ) -> None:
        """Set the PVID and untagged VLAN of an access port."""

        port = self.port(switch_name, port_name)

        if port.role != "access":
            raise ValueError(
                f"{switch_name}.{port_name} is not an access port"
            )

        port.pvid = vlan
        port.allowed_vlans = {vlan}

    def set_admin_state(
        self,
        switch_name: str,
        port_name: str,
        state: str,
    ) -> None:
        """Set a port's administrative state."""

        if state not in {"up", "down"}:
            raise ValueError("administrative state must be 'up' or 'down'")

        self.port(switch_name, port_name).admin_state = state

    def operational_state(
        self,
        switch_name: str,
        port_name: str,
    ) -> str:
        """Calculate a port's operational state."""

        port = self.port(switch_name, port_name)

        if port.admin_state == "down":
            return "down"

        if port.peer_switch is None or port.peer_port is None:
            return "up"

        peer = self.port(port.peer_switch, port.peer_port)
        return "up" if peer.admin_state == "up" else "down"

    def can_hosts_reach(
        self,
        source_name: str,
        target_name: str,
    ) -> bool:
        """Determine whether two configured hosts have layer-2 reachability."""

        source = self.config.hosts[source_name]
        target = self.config.hosts[target_name]

        source_port = self.port(source.switch, source.port)
        target_port = self.port(target.switch, target.port)

        if source_port.admin_state != "up":
            return False

        if target_port.admin_state != "up":
            return False

        if source.expected_vlan != target.expected_vlan:
            return False

        vlan = source.expected_vlan

        if source_port.pvid != vlan or target_port.pvid != vlan:
            return False

        if source.switch == target.switch:
            return True

        source_trunk = self._find_trunk(
            source.switch,
            target.switch,
        )
        target_trunk = self._find_trunk(
            target.switch,
            source.switch,
        )

        if source_trunk is None or target_trunk is None:
            return False

        if source_trunk.admin_state != "up":
            return False

        if target_trunk.admin_state != "up":
            return False

        return (
            vlan in source_trunk.allowed_vlans
            and vlan in target_trunk.allowed_vlans
        )

    def _find_trunk(
        self,
        switch_name: str,
        peer_switch: str,
    ) -> SimulatedPortState | None:
        for port in self.switches[switch_name].values():
            if (
                port.role == "trunk"
                and port.peer_switch == peer_switch
            ):
                return port

        return None

    def save_config(self) -> None:
        """Persist a snapshot of the current simulated configuration."""

        self._saved_switches = copy.deepcopy(self.switches)

    def reload(self) -> None:
        """Restore the most recently saved simulated configuration."""

        self.switches = copy.deepcopy(self._saved_switches)
