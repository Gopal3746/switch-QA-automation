import pytest

from switch_qa.config import load_topology
from switch_qa.devices import Host, Switch
from switch_qa.simulated_transport import SimulatedTransport
from switch_qa.simulation import SimulatedTopologyState


def build_switch(
    switch_name: str,
    state: SimulatedTopologyState,
) -> Switch:
    switch_config = state.config.switches[switch_name]
    transport = SimulatedTransport(switch_name, state)

    switch = Switch(
        name=switch_name,
        display_name=switch_config.display_name,
        transport=transport,
    )
    switch.connect()
    return switch


def test_switch_reads_vlan_and_link_state() -> None:
    state = SimulatedTopologyState.from_config(load_topology())
    switch1 = build_switch("switch1", state)

    assert switch1.get_pvid("swp1") == 10
    assert switch1.get_allowed_vlans("swp2") == [10, 20]
    assert switch1.get_admin_state("swp1") == "up"
    assert switch1.get_operational_state("swp1") == "up"


def test_switch_commands_correct_both_defects() -> None:
    state = SimulatedTopologyState.from_config(
        load_topology(),
        scenario="buggy",
    )
    switch1 = build_switch("switch1", state)
    switch2 = build_switch("switch2", state)

    assert not state.can_hosts_reach("host_a", "host_b")

    switch1.configure_access_vlan("swp1", 10)
    switch2.configure_trunk_vlan("swp1", 10)

    assert switch1.get_pvid("swp1") == 10
    assert switch2.get_allowed_vlans("swp1") == [10, 20]
    assert state.can_hosts_reach("host_a", "host_b")


def test_switch_changes_port_admin_state() -> None:
    state = SimulatedTopologyState.from_config(load_topology())
    switch1 = build_switch("switch1", state)

    switch1.set_admin_state("swp1", "down")

    assert switch1.get_admin_state("swp1") == "down"
    assert switch1.get_operational_state("swp1") == "down"

    switch1.set_admin_state("swp1", "up")

    assert switch1.get_admin_state("swp1") == "up"
    assert switch1.get_operational_state("swp1") == "up"


def test_switch_exposes_linux_diagnostics() -> None:
    state = SimulatedTopologyState.from_config(load_topology())
    switch1 = build_switch("switch1", state)

    bridge_output = switch1.bridge_vlan_show()
    link_output = switch1.ip_link_show("swp1")
    address_output = switch1.ip_address_show("eth0")
    route_output = switch1.ip_route_show()

    assert "swp1" in bridge_output
    assert "PVID Egress Untagged" in bridge_output
    assert "state UP" in link_output
    assert "192.0.2.10/24" in address_output
    assert "default via 192.0.2.1" in route_output


@pytest.mark.parametrize(
    ("scenario", "expected_received", "expected_loss"),
    [
        ("fixed", 4, 0.0),
        ("buggy", 0, 100.0),
    ],
)
def test_host_ping_reflects_network_state(
    scenario: str,
    expected_received: int,
    expected_loss: float,
) -> None:
    topology = load_topology()
    state = SimulatedTopologyState.from_config(
        topology,
        scenario=scenario,
    )
    transport = SimulatedTransport("switch1", state)
    transport.connect()

    host_a_config = topology.hosts["host_a"]
    host_b_config = topology.hosts["host_b"]

    host_a = Host(
        name="host_a",
        display_name=host_a_config.display_name,
        ip_address=host_a_config.ip_address,
        transport=transport,
    )

    result = host_a.ping(
        host_b_config.ip_address,
        count=4,
    )

    assert result.transmitted == 4
    assert result.received == expected_received
    assert result.packet_loss_percent == expected_loss
    assert result.reachable is (expected_received > 0)
