"""Simulateur IOS et exercices réseau."""

import pytest

from app.catalog import load_exercises
from app.network import grader
from app.network.ios import Device, Session, apply_commands, normalize_iface, expand_range

EXERCISES = load_exercises("network")


@pytest.mark.parametrize("exercise", EXERCISES, ids=[e["id"] for e in EXERCISES])
def test_solution_validee(exercise):
    device = grader.new_device(exercise)
    apply_commands(device, exercise["solution"])
    result = grader.check(exercise, device)
    assert result["success"], [r for r in result["results"] if not r["passed"]]


@pytest.mark.parametrize("exercise", EXERCISES, ids=[e["id"] for e in EXERCISES])
def test_etat_initial_refuse(exercise):
    result = grader.check(exercise, grader.new_device(exercise))
    assert not result["success"]


def test_solution_tapee_dans_le_terminal():
    """Les solutions passent aussi par la session interactive, depuis le mode utilisateur."""
    exercise = next(e for e in EXERCISES if e["id"] == "304-projet-switch")
    session = Session(grader.new_device(exercise))
    session.execute("enable")
    for line in exercise["solution"].splitlines():
        out = session.execute(line)
        assert "Invalid" not in out and "Incomplete" not in out, (line, out)
    assert grader.check(exercise, session.device)["success"]


def test_abreviations():
    session = Session(Device("switch"))
    for line in ["en", "conf t", "ho SW9", "int fa0/3", "sw mo acc", "sw acc vl 30", "do sh vl br"]:
        out = session.execute(line)
        assert "%" not in out or "Creating vlan" in out, (line, out)
    assert session.device.hostname == "SW9"
    assert session.device.intf("Fa0/3").access_vlan == 30


def test_modes_et_prompts():
    session = Session(Device("router"))
    assert session.prompt == "Router>"
    session.execute("enable")
    assert session.prompt == "Router#"
    session.execute("configure terminal")
    assert session.prompt == "Router(config)#"
    session.execute("interface g0/0.10")
    assert session.prompt == "Router(config-subif)#"
    session.execute("end")
    assert session.prompt == "Router#"


def test_erreurs():
    session = Session(Device("switch"))
    assert session.execute("configure terminal").startswith("%")  # pas encore en mode privilégié
    session.execute("enable")
    session.execute("conf t")
    assert "Ambiguous" in session.execute("s")
    assert "Invalid" in session.execute("vlan 5000")
    assert "Incomplete" in session.execute("hostname")


def test_aide():
    session = Session(Device("switch"))
    session.execute("en")
    assert "configure" in session.execute("?")
    assert "terminal" in session.execute("configure ?")


def test_negation_et_sous_mode_global():
    device = Device("switch")
    session = apply_commands(device, ["conf t", "vlan 10", "hostname X", "no vlan 10"])
    assert device.hostname == "X" and 10 not in device.vlans
    assert session.mode == "config"


def test_noms_interfaces():
    assert normalize_iface("fa0/1") == "FastEthernet0/1"
    assert normalize_iface("Gi0/0.10") == "GigabitEthernet0/0.10"
    assert normalize_iface("vlan 99") == "Vlan99"
    assert expand_range("fa0/1 - 3, g0/1") == ["FastEthernet0/1", "FastEthernet0/2", "FastEthernet0/3",
                                              "GigabitEthernet0/1"]


def test_trunk_add_remove():
    device = Device("switch")
    apply_commands(device, ["conf t", "int g0/1", "sw mode trunk", "sw trunk allowed vlan 10-12",
                            "sw trunk allowed vlan add 20", "sw trunk allowed vlan remove 11"])
    assert device.intf("g0/1").allowed_vlans() == {10, 12, 20}


def test_sauvegarde_invalidee_par_modification():
    device = Device("switch")
    apply_commands(device, ["write memory"])
    assert device.saved
    apply_commands(device, ["conf t", "hostname Y"])
    assert not device.saved
