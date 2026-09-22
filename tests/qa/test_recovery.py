import pytest

from switch_qa.devices import Host, Switch
from switch_qa.simulation import SimulatedTopologyState


@pytest.mark.test_id("TC-12")
@pytest.mark.simulation_only
def test_saved_configuration_survives_reload(
    switch1: Switch,
) -> None:
    switch1.set_admin_state("swp1", "down")
    switch1.save_configuration()

    switch1.set_admin_state("swp1", "up")
    assert switch1.get_admin_state("swp1") == "up"

    switch1.run_command(
        "__simulate_reload__",
        check=True,
    )

    assert switch1.get_admin_state("swp1") == "down"


@pytest.mark.test_id("TC-13")
def test_connectivity_recovers_after_defect_correction(
    buggy_state: SimulatedTopologyState,
    buggy_switch1: Switch,
    buggy_switch2: Switch,
    buggy_host_a: Host,
) -> None:
    host_b_address = buggy_state.config.hosts["host_b"].ip_address

    before_fix = buggy_host_a.ping(host_b_address)

    assert not before_fix.reachable
    assert not buggy_state.can_hosts_reach(
        "host_a",
        "host_b",
    )

    buggy_switch1.configure_access_vlan(
        "swp1",
        10,
    )
    buggy_switch2.configure_trunk_vlan(
        "swp1",
        10,
    )

    after_fix = buggy_host_a.ping(host_b_address)

    assert after_fix.reachable
    assert after_fix.packet_loss_percent == 0.0
    assert buggy_state.can_hosts_reach(
        "host_a",
        "host_b",
    )
