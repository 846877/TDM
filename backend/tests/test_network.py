"""Simulateur IOS et exercices réseau."""

import pytest

from app.catalog import load_exercises
from app.network import grader
from app.network.ios import (Device, Session, apply_commands, classful_network, expand_range, is_error,
                             normalize_iface, normalize_nat_rule)

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


@pytest.mark.parametrize("exercise", EXERCISES, ids=[e["id"] for e in EXERCISES])
def test_solution_tapee_dans_le_terminal(exercise):
    """Les solutions passent aussi par la session interactive, depuis le mode utilisateur."""
    session = Session(grader.new_device(exercise))
    session.execute("enable")
    for line in exercise["solution"].splitlines():
        out = session.execute(line)
        assert not is_error(out), (line, out)
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


# -- commandes ajoutées au simulateur ---------------------------------------------


def _config(kind, commands, hostname=None):
    device = Device(kind, hostname)
    apply_commands(device, ["conf t", *commands, "end"])
    return device


def _show(device, command):
    session = Session(device)
    session.mode = "exec"
    return session.execute(command)


def test_vitesse_duplex_et_shutdown_en_plage():
    device = _config("switch", ["int range fa0/1 - 3", "speed 100", "duplex full", "shutdown"])
    assert all(device.intf(f"fa0/{n}").speed == "100" and device.intf(f"fa0/{n}").duplex == "full"
               and device.intf(f"fa0/{n}").shutdown for n in (1, 2, 3))
    assert not device.intf("fa0/4").shutdown
    assert "speed 100" in device.running_config() and "duplex full" in device.running_config()
    session = apply_commands(device, ["conf t", "int fa0/4"])
    assert is_error(session.execute("speed 1000"))  # FastEthernet : 1000 refusé
    assert is_error(session.execute("duplex moitie"))
    assert "full    100" in _show(device, "show interfaces status")


def test_description_et_show_interfaces_description():
    device = _config("switch", ["int g0/1", "description UPLINK CORE"])
    assert device.intf("g0/1").description == "UPLINK CORE"
    assert "UPLINK CORE" in _show(device, "show interfaces description")


def test_trunk_natif_nonegotiate():
    device = _config("switch", ["int g0/1", "sw mode trunk", "sw trunk native vlan 999", "sw nonegotiate"])
    iface = device.intf("g0/1")
    assert iface.native_vlan == 999 and iface.nonegotiate
    assert "switchport nonegotiate" in device.running_config()
    session = apply_commands(Device("switch"), ["conf t", "int fa0/1"])
    assert is_error(session.execute("switchport nonegotiate"))  # port encore dynamique


def test_etherchannel_lacp_cree_le_port_channel():
    device = _config("switch", ["int range g0/1 - 2", "channel-group 1 mode active",
                                "int po1", "sw mode trunk", "sw trunk allowed vlan 10,20"])
    assert device.channel_members(1) == ["Gi0/1", "Gi0/2"]
    assert all(device.intf(n).channel_protocol == "lacp" for n in ("g0/1", "g0/2"))
    po = device.intf("port-channel 1")
    assert po.name == "Port-channel1" and po.is_switchport and po.allowed_vlans() == {10, 20}
    out = _show(device, "show etherchannel summary")
    assert "Po1(SU)" in out and "LACP" in out and "Gi0/1(P)" in out
    assert "channel-group 1 mode active" in device.running_config()


def test_etherchannel_modes_pagp_on_et_incoherence():
    device = _config("switch", ["int range fa0/23 - 24", "channel-group 2 mode desirable",
                                "int range fa0/21 - 22", "channel-group 3 mode on"])
    assert device.intf("fa0/23").channel_protocol == "pagp"
    assert device.intf("fa0/21").channel_mode == "on" and device.intf("fa0/21").channel_protocol is None
    session = apply_commands(device, ["conf t", "int fa0/23"])
    assert is_error(session.execute("channel-group 2 mode active"))  # PAgP déjà choisi
    assert is_error(session.execute("channel-group 2 mode turbo"))
    apply_commands(device, ["conf t", "no interface port-channel 3"])
    assert not device.has_intf("po3") and device.intf("fa0/21").channel_group is None


def test_vtp_et_mode_client():
    device = _config("switch", ["vtp domain TDM", "vtp version 2", "vtp password s3cret", "vtp mode client"])
    assert (device.vtp_domain, device.vtp_version, device.vtp_password, device.vtp_mode) == \
        ("TDM", 2, "s3cret", "client")
    session = apply_commands(device, ["conf t"])
    assert "CLIENT" in session.execute("vlan 50") and 50 not in device.vlans
    assert "VTP Operating Mode              : Client" in _show(device, "show vtp status")


def test_stp_listes_de_vlan_et_protections():
    device = _config("switch", ["spanning-tree vlan 10,20 root primary", "spanning-tree vlan 30 priority 4096",
                                "spanning-tree portfast default", "spanning-tree portfast bpduguard default",
                                "int fa0/24", "spanning-tree guard root", "spanning-tree cost 19",
                                "spanning-tree port-priority 64"])
    assert device.stp_priority == {10: 24576, 20: 24576, 30: 4096}
    assert device.stp_portfast_default and device.stp_bpduguard_default
    iface = device.intf("fa0/24")
    assert (iface.stp_guard, iface.stp_cost, iface.stp_port_priority) == ("root", 19, 64)
    assert "spanning-tree guard root" in device.running_config()
    session = apply_commands(device, ["conf t", "int fa0/1"])
    assert is_error(session.execute("spanning-tree port-priority 10"))
    assert "Root bridge for: VLAN0010, VLAN0020, VLAN0030" in _show(device, "show spanning-tree summary")


def test_dhcp_snooping_et_arp_inspection():
    device = _config("switch", ["ip dhcp snooping", "ip dhcp snooping vlan 10,20", "no ip dhcp snooping vlan 20",
                                "no ip dhcp snooping information option", "ip arp inspection vlan 10-11",
                                "int g0/1", "ip dhcp snooping trust", "ip arp inspection trust",
                                "int range fa0/1 - 2", "ip dhcp snooping limit rate 15"])
    assert device.dhcp_snooping and device.dhcp_snooping_vlans == {10}
    assert not device.dhcp_snooping_option82 and device.arp_inspection_vlans == {10, 11}
    assert device.intf("g0/1").dhcp_snooping_trust and device.intf("g0/1").arp_inspection_trust
    assert device.intf("fa0/2").dhcp_snooping_rate == 15
    out = _show(device, "show ip dhcp snooping")
    assert "Switch DHCP snooping is enabled" in out and "GigabitEthernet0/1         yes" in out
    assert "Vlans enabled              : 10-11" in _show(device, "show ip arp inspection")


def test_storm_control_et_errdisable():
    device = _config("switch", ["int fa0/1", "storm-control broadcast level 20", "storm-control action shutdown",
                                "exit", "errdisable recovery cause psecure-violation",
                                "errdisable recovery interval 300"])
    assert device.intf("fa0/1").storm_control == {"broadcast": "20.00", "action": "shutdown"}
    assert device.errdisable_recovery == {"psecure-violation"} and device.errdisable_interval == 300
    assert "storm-control broadcast level 20.00" in device.running_config()


def test_port_route_no_switchport():
    device = _config("switch", ["ip routing", "int g0/1", "no switchport", "ip address 10.0.0.2 255.255.255.252"])
    assert not device.intf("g0/1").is_switchport and device.intf("g0/1").ip == "10.0.0.2"
    assert " no switchport" in device.running_config()
    session = apply_commands(Device("switch"), ["conf t", "int fa0/1"])
    assert is_error(session.execute("ip address 10.0.0.1 255.255.255.0"))  # encore un port de niveau 2
    assert is_error(apply_commands(Device("router"), ["conf t", "int g0/0"]).execute("no switchport"))


def test_route_flottante_et_show_ip_route():
    device = _config("router", ["int g0/0", "ip address 203.0.113.2 255.255.255.252", "no shut",
                                "ip route 0.0.0.0 0.0.0.0 203.0.113.1",
                                "ip route 0.0.0.0 0.0.0.0 192.0.2.1 10",
                                "ip route 10.0.0.0 255.0.0.0 g0/0 203.0.113.1 name VPN permanent"])
    assert device.has_route("0.0.0.0", "0.0.0.0", "203.0.113.1", 1)
    assert device.has_route("0.0.0.0", "0.0.0.0", "192.0.2.1", 10)
    assert not device.has_route("0.0.0.0", "0.0.0.0", "192.0.2.1", 1)
    assert device.has_route("10.0.0.0", "255.0.0.0", "Gi0/0 203.0.113.1")
    assert "ip route 0.0.0.0 0.0.0.0 192.0.2.1 10" in device.running_config()
    table = _show(device, "show ip route")
    assert "[1/0] via 203.0.113.1" in table and "192.0.2.1" not in table  # la route flottante n'est pas installée
    apply_commands(device, ["conf t", "no ip route 0.0.0.0 0.0.0.0 203.0.113.1"])
    assert "[10/0] via 192.0.2.1" in _show(device, "show ip route")
    session = apply_commands(device, ["conf t"])
    assert is_error(session.execute("ip route 0.0.0.0 0.0.0.0 192.0.2.1 300"))


def test_rip_v2():
    device = _config("router", ["router rip", "version 2", "network 10.1.2.0", "network 192.168.50.0",
                                "no auto-summary", "passive-interface g0/0", "default-information originate"])
    rip = device.rip
    assert rip.version == 2 and rip.networks == ["10.0.0.0", "192.168.50.0"] and not rip.auto_summary
    assert device.rip_has_network("10.200.0.0") and rip.is_passive("Gi0/0") and rip.default_originate
    assert classful_network("172.20.1.0") == "172.20.0.0"
    assert 'Routing Protocol is "rip"' in _show(device, "show ip protocols")
    apply_commands(device, ["conf t", "no router rip"])
    assert device.rip is None


def test_eigrp():
    device = _config("router", ["router eigrp 100", "eigrp router-id 2.2.2.2", "network 192.168.20.0 0.0.0.255",
                                "network 10.0.0.0", "passive-interface default", "no passive-interface s0/0/0",
                                "no auto-summary", "redistribute static"])
    proc = device.eigrp[100]
    assert proc.router_id == "2.2.2.2" and not proc.auto_summary and proc.redistribute == ["static"]
    assert device.eigrp_has_network(100, "192.168.20.0", "0.0.0.255") and device.eigrp_has_network(100, "10.0.0.0")
    assert proc.is_passive("g0/0") and not proc.is_passive("se0/0/0")
    config = device.running_config()
    assert " passive-interface default" in config and " no passive-interface Serial0/0/0" in config
    session = apply_commands(device, ["conf t", "router eigrp 100"])
    assert session.prompt.endswith("(config-router)#")
    assert is_error(session.execute("network 10.0.0.0 0.0.0.3 area 0"))  # syntaxe OSPF refusée en EIGRP


def test_ospf_avance():
    device = _config("router", ["int g0/1", "ip ospf cost 100", "ip ospf priority 0", "ip ospf 1 area 10",
                                "router ospf 1", "passive-interface default", "no passive-interface g0/1",
                                "auto-cost reference-bandwidth 10000", "area 10 stub",
                                "default-information originate always", "network 10.0.0.0 0.0.0.3 area 0.0.0.0"])
    proc = device.ospf[1]
    assert proc.is_passive("g0/0") and not proc.is_passive("g0/1")
    assert proc.reference_bandwidth == 10000 and proc.area_types == {"10": "stub"}
    assert proc.default_originate and proc.default_originate_always
    assert device.ospf_has_network("10.0.0.0", "0.0.0.3", "0.0.0.0")
    iface = device.intf("g0/1")
    assert (iface.ospf_cost, iface.ospf_priority, iface.ospf_area) == (100, 0, (1, "10"))
    session = apply_commands(device, ["conf t", "router ospf 1"])
    assert is_error(session.execute("area 0 stub"))
    # Rétrocompatibilité : les anciennes vérifications lisent encore « passive »
    legacy = _config("router", ["router ospf 1", "passive-interface g0/0"])
    assert "GigabitEthernet0/0" in legacy.ospf[1].passive


def test_ipv6_adresses_et_routes():
    device = _config("router", ["ipv6 unicast-routing", "int g0/0", "ipv6 address 2001:DB8:ACAD:10::1/64",
                                "ipv6 address FE80::1 link-local", "ipv6 address 2001:db8:acad:11::/64 eui-64",
                                "no shut", "exit", "ipv6 route 2001:db8:acad:30::/64 2001:db8:acad:ff::2",
                                "ipv6 route ::/0 g0/0 fe80::2", "ipv6 route ::/0 2001:db8:b::1 20"])
    iface = device.intf("g0/0")
    assert device.ipv6_routing and iface.has_ipv6("2001:db8:acad:10:0:0:0:1/64") and iface.ipv6_link_local == "fe80::1"
    assert "2001:db8:acad:11::/64 eui-64" in iface.ipv6_addresses
    assert device.has_route6("2001:DB8:ACAD:30::/64", "2001:db8:acad:ff::2")
    assert device.has_route6("::/0", "GigabitEthernet0/0 fe80::2", 1) and device.has_route6("::/0", "2001:db8:b::1", 20)
    assert "ipv6 address 2001:DB8:ACAD:10::1/64" in device.running_config()
    assert "FE80::1" in _show(device, "show ipv6 interface brief")
    routes = _show(device, "show ipv6 route")
    assert "S   2001:DB8:ACAD:30::/64 [1/0]" in routes and "2001:DB8:B::1" not in routes
    session = apply_commands(device, ["conf t", "int g0/1"])
    assert is_error(session.execute("ipv6 address 2001:db8::1"))  # longueur de préfixe manquante
    assert is_error(session.execute("ipv6 address 2001:db8::1 link-local"))  # pas une adresse fe80::/10


def test_hsrp():
    device = _config("router", ["int g0/0", "ip address 192.168.10.2 255.255.255.0", "no shutdown", "standby version 2",
                                "standby 10 ip 192.168.10.1", "standby 10 priority 110", "standby 10 preempt"])
    group = device.intf("g0/0").standby[10]
    assert (group.ip, group.priority, group.preempt) == ("192.168.10.1", 110, True)
    assert "standby 10 priority 110" in device.running_config()
    assert "110 P Active" in _show(device, "show standby brief")
    session = apply_commands(device, ["conf t", "int g0/1"])
    assert is_error(session.execute("standby 1 ip 10.0.0.1"))  # pas d'adresse IP sur l'interface


def test_ntp_syslog_snmp():
    device = _config("router", ["ntp server 10.0.0.10", "ntp server 10.0.0.11 prefer", "clock timezone CET 1",
                                "logging host 10.0.0.20", "logging 10.0.0.21", "logging trap 4",
                                "logging buffered 16384", "service timestamps log datetime msec",
                                "snmp-server community public RW", "snmp-server community Tdm RO SNMP-ACL",
                                "no snmp-server community public", "snmp-server location Lyon",
                                "snmp-server contact noc@tdm.local", "snmp-server host 10.0.0.30 version 2c Tdm"])
    assert device.ntp_servers == ["10.0.0.10", "10.0.0.11"] and device.clock_timezone == ("CET", 1)
    assert device.logging_hosts == ["10.0.0.20", "10.0.0.21"] and device.logging_trap == "warnings"
    assert device.snmp_communities == {"Tdm": ("RO", "SNMP-ACL")}
    assert device.snmp_location == "Lyon" and device.snmp_hosts == ["10.0.0.30 version 2c Tdm"]
    assert "10.0.0.10" in _show(device, "show ntp associations")
    assert "Trap logging: level warnings" in _show(device, "show logging")
    assert "read-only" in _show(device, "show snmp community")
    session = apply_commands(device, ["conf t"])
    assert is_error(session.execute("logging trap bavard"))


def test_aaa_et_politique_de_mots_de_passe():
    device = _config("router", ["security passwords min-length 10", "aaa new-model",
                                "aaa authentication login default local",
                                "username admin privilege 15 algorithm-type scrypt secret Tr3sL0ngSecret",
                                "login block-for 120 attempts 3 within 60", "no ip http server",
                                "no ip http secure-server", "ip ssh time-out 60", "ip ssh authentication-retries 2",
                                "line vty 0 4", "login authentication default"])
    assert device.aaa_new_model and device.aaa_authentication == {"login default": "local"}
    assert device.users["admin"]["secret"] == "Tr3sL0ngSecret" and device.login_block == (120, 3, 60)
    assert not device.http_server and not device.https_server
    assert (device.ssh_timeout, device.ssh_retries) == (60, 2)
    assert device.lines["vty"].login_authentication == "default"
    session = apply_commands(device, ["conf t"])
    assert "too short" in session.execute("enable secret court")
    assert "too short" in session.execute("username bob secret court")
    assert device.enable_secret is None and "bob" not in device.users
    no_aaa = apply_commands(Device("router"), ["conf t"])
    assert is_error(no_aaa.execute("aaa authentication login default local"))  # aaa new-model d'abord


def test_access_class_sur_les_vty():
    device = _config("router", ["ip access-list standard ADMIN", "permit 192.168.99.0 0.0.0.255",
                                "line vty 0 4", "access-class ADMIN in"])
    assert device.lines["vty"].access_class == {"in": "ADMIN"}
    assert " access-class ADMIN in" in device.running_config()
    session = apply_commands(device, ["conf t", "line vty 0 4"])
    assert is_error(session.execute("access-class ADMIN sideways"))


def test_acl_numeros_de_sequence():
    device = _config("router", ["ip access-list extended WEB", "permit tcp any any eq 80",
                                "permit tcp any any eq 22", "deny ip any any", "no 20",
                                "15 permit tcp any any eq 443", "permit icmp any any echo"])
    assert device.acl_seqs("WEB") == [10, 15, 30, 40]
    assert [e for e in device.acls["WEB"] if e != "__ext__"] == [
        "permit tcp any any eq 80", "permit tcp any any eq 443", "deny ip any any", "permit icmp any any echo"]
    assert "    15 permit tcp any any eq 443" in _show(device, "show access-lists")
    session = apply_commands(device, ["conf t", "ip access-list extended WEB"])
    assert is_error(session.execute("15 deny ip any any"))  # numéro déjà utilisé
    session.execute("interface g0/0")  # commande globale acceptée depuis le sous-mode ACL
    assert session.mode == "if"


def test_nat_normalise_et_traductions():
    device = _config("router", ["access-list 1 permit 192.168.1.0 0.0.0.255",
                                "ip nat inside source list 1 interface gi0/1 overload",
                                "ip nat inside source static 192.168.1.10 203.0.113.5",
                                "ip nat pool PUB 203.0.113.17 203.0.113.30 netmask 255.255.255.240"])
    assert "ip nat inside source list 1 interface GigabitEthernet0/1 overload" in device.nat_rules
    assert device.has_nat("ip nat inside source list 1 interface g0/1 overload")
    assert device.has_nat("IP NAT pool PUB 203.0.113.17 203.0.113.30 netmask 255.255.255.240")
    assert normalize_nat_rule("inside source static 1.1.1.1 2.2.2.2") == "ip nat inside source static 1.1.1.1 2.2.2.2"
    assert "203.0.113.5" in _show(device, "show ip nat translations")
    assert is_error(apply_commands(Device("router"), ["conf t"]).execute("ip nat bidule"))


def test_cdp_lldp():
    device = _config("router", ["lldp run", "no cdp run", "int g0/1", "no cdp enable", "no lldp transmit"])
    assert device.lldp_run and not device.cdp_run
    assert not device.intf("g0/1").cdp_enabled and not device.intf("g0/1").lldp_transmit
    assert device.intf("g0/1").lldp_receive
    assert _show(device, "show cdp") == "% CDP is not enabled"
    assert "ACTIVE" in _show(device, "show lldp")


def test_dhcp_plusieurs_dns_et_bail():
    device = _config("router", ["ip dhcp pool LAN", "network 192.168.1.0 255.255.255.0",
                                "dns-server 8.8.8.8 1.1.1.1", "lease 0 8"])
    pool = device.dhcp_pools["LAN"]
    assert pool.dns_servers == ["8.8.8.8", "1.1.1.1"] and pool.lease == "0 8"


def test_filtres_show():
    device = _config("switch", ["hostname SW-FILTRE", "vlan 10", "name ADMIN", "int fa0/1", "description PC-1"])
    session = Session(device)
    session.mode = "exec"
    assert session.execute("show running-config | include hostname") == "hostname SW-FILTRE"
    section = session.execute("sh run | sec FastEthernet0/1$")
    assert section.splitlines() == ["interface FastEthernet0/1", " description PC-1"]
    assert session.execute("show vlan brief | begin ADMIN").startswith("10   ADMIN")
    assert "hostname" not in session.execute("show run | exclude hostname")
    assert is_error(session.execute("show run | grep x"))
    assert "Incomplete" in session.execute("show run | include")


def test_port_channel_et_noms_interfaces():
    assert normalize_iface("po1") == "Port-channel1"
    assert normalize_iface("Port-channel 12") == "Port-channel12"
    assert normalize_iface("port-channel1") == "Port-channel1"
