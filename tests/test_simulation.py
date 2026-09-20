import pytest

from switch_qa.config import TopologyConfig, load_topology
from switch_qa.simulation import SimulatedTopologyState


@pytest.fixture
def topology_config() -> TopologyConfig:
    return load_topology()


def test_fixed_state_matches_expected_topology(
    topology_config: TopologyConfig,
) -> None:
    state = SimulatedTopologyState.from_config(topology_config)

    switch1_access = state.port("switch1", "swp1")
    switch1_trunk = state.port("switch1", "swp2")
    switch2_trunk = state.port("switch2", "swp1")
    switch2_access = state.port("switch2", "swp2")

    assert switch1_access.pvid == 10
    assert switch1_access.allowed_vlans == {10}
    assert switch1_trunk.allowed_vlans == {10, 20}
    assert switch2_trunk.allowed_vlans == {10, 20}
    assert switch2_access.pvid == 10


def test_fixed_topology_has_end_to_end_connectivity(
    topology_config: TopologyConfig,
) -> None:
    state = SimulatedTopologyState.from_config(topology_config)

    assert state.can_hosts_reach("host_a", "host_b")


def test_buggy_state_injects_two_independent_defects(
    topology_config: TopologyConfig,
) -> None:
    state = SimulatedTopologyState.from_config(
        topology_config,
        scenario="buggy",
    )

    assert state.port("switch1", "swp1").pvid == 20
    assert state.port("switch2", "swp1").allowed_vlans == {20}
    assert not state.can_hosts_reach("host_a", "host_b")


def test_correcting_both_defects_restores_connectivity(
    topology_config: TopologyConfig,
) -> None:
    state = SimulatedTopologyState.from_config(
        topology_config,
        scenario="buggy",
    )

    state.set_access_vlan("switch1", "swp1", 10)
    assert not state.can_hosts_reach("host_a", "host_b")

    state.add_trunk_vlan("switch2", "swp1", 10)
    assert state.can_hosts_reach("host_a", "host_b")


def test_admin_down_port_blocks_connectivity(
    topology_config: TopologyConfig,
) -> None:
    state = SimulatedTopologyState.from_config(topology_config)

    state.set_admin_state("switch1", "swp1", "down")

    assert state.operational_state("switch1", "swp1") == "down"
    assert not state.can_hosts_reach("host_a", "host_b")


def test_peer_admin_state_controls_trunk_operational_state(
    topology_config: TopologyConfig,
) -> None:
    state = SimulatedTopologyState.from_config(topology_config)

    state.set_admin_state("switch2", "swp1", "down")

    assert state.operational_state("switch1", "swp2") == "down"
    assert state.operational_state("switch2", "swp1") == "down"


def test_reload_discards_unsaved_changes(
    topology_config: TopologyConfig,
) -> None:
    state = SimulatedTopologyState.from_config(topology_config)

    state.set_access_vlan("switch1", "swp1", 20)
    assert not state.can_hosts_reach("host_a", "host_b")

    state.reload()

    assert state.port("switch1", "swp1").pvid == 10
    assert state.can_hosts_reach("host_a", "host_b")


def test_saved_changes_survive_reload(
    topology_config: TopologyConfig,
) -> None:
    state = SimulatedTopologyState.from_config(topology_config)

    state.set_admin_state("switch1", "swp1", "down")
    state.save_config()
    state.set_admin_state("switch1", "swp1", "up")

    state.reload()

    assert state.port("switch1", "swp1").admin_state == "down"
