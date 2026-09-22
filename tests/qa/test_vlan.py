import pytest

from switch_qa.devices import Host, Switch


@pytest.mark.test_id("TC-01")
def test_access_ports_use_expected_pvid(
    switch1: Switch,
    switch2: Switch,
) -> None:
    assert switch1.get_pvid("swp1") == 10
    assert switch2.get_pvid("swp2") == 10


@pytest.mark.test_id("TC-02")
def test_switch1_trunk_carries_required_vlans(
    switch1: Switch,
) -> None:
    assert switch1.get_allowed_vlans("swp2") == [10, 20]


@pytest.mark.test_id("TC-03")
def test_switch2_trunk_carries_required_vlans(
    switch2: Switch,
) -> None:
    assert switch2.get_allowed_vlans("swp1") == [10, 20]


@pytest.mark.test_id("TC-04")
def test_vlan_isolation_blocks_cross_vlan_traffic(
    switch2: Switch,
    host_a: Host,
    host_b: Host,
) -> None:
    switch2.configure_access_vlan("swp2", 20)

    result = host_a.ping(host_b.ip_address)

    assert not result.reachable
    assert result.packet_loss_percent == 100.0
