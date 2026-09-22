import pytest

from switch_qa.devices import Switch


@pytest.mark.test_id("TC-05")
def test_port_admin_down_and_up_transitions(
    switch1: Switch,
) -> None:
    switch1.set_admin_state("swp1", "down")

    assert switch1.get_admin_state("swp1") == "down"
    assert switch1.get_operational_state("swp1") == "down"

    switch1.set_admin_state("swp1", "up")

    assert switch1.get_admin_state("swp1") == "up"
    assert switch1.get_operational_state("swp1") == "up"


@pytest.mark.test_id("TC-06")
def test_trunk_operational_state_tracks_peer(
    switch1: Switch,
    switch2: Switch,
) -> None:
    assert switch1.get_operational_state("swp2") == "up"

    switch2.set_admin_state("swp1", "down")

    assert switch2.get_operational_state("swp1") == "down"
    assert switch1.get_operational_state("swp2") == "down"
