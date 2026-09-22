import pytest

from switch_qa.devices import Host, Switch


@pytest.mark.test_id("TC-09")
def test_missing_trunk_vlan_is_detected(
    buggy_switch2: Switch,
) -> None:
    expected_vlans = {10, 20}
    actual_vlans = set(
        buggy_switch2.get_allowed_vlans("swp1")
    )

    missing_vlans = expected_vlans - actual_vlans

    assert missing_vlans == {10}


@pytest.mark.test_id("TC-10")
def test_incorrect_access_pvid_is_detected(
    buggy_switch1: Switch,
) -> None:
    expected_pvid = 10
    actual_pvid = buggy_switch1.get_pvid("swp1")

    assert actual_pvid != expected_pvid
    assert actual_pvid == 20


@pytest.mark.test_id("TC-11")
def test_down_access_port_prevents_connectivity(
    switch1: Switch,
    host_a: Host,
    host_b: Host,
) -> None:
    switch1.set_admin_state("swp1", "down")

    result = host_a.ping(host_b.ip_address)

    assert not result.reachable
    assert result.received == 0
    assert result.packet_loss_percent == 100.0
