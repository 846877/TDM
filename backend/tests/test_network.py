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


# -- extension du simulateur : gestion, commutation, routage avancé, VPN, QoS ------


def test_bannieres_horloge_hotes_services():
    device = _config("router", ["banner login #Acces reserve#", "banner exec ^Bienvenue^",
                                "service timestamps log datetime localtime msec", "clock timezone CET 1",
                                "clock summer-time CEST recurring last Sun Mar 2:00 last Sun Oct 3:00",
                                "ip host SRV-WEB 192.168.1.10", "no ip source-route", "service tcp-keepalives-in",
                                "logging console warnings", "privilege exec level 5 show running-config"])
    assert device.banner_login == "Acces reserve" and device.banner_exec == "Bienvenue"
    assert device.service_timestamps["log"] == "datetime msec localtime"
    assert device.clock_summer_time.startswith("CEST recurring")
    assert device.ip_hosts == {"SRV-WEB": "192.168.1.10"} and not device.source_route
    assert device.tcp_keepalives_in and device.logging_console == "warnings"
    assert ("exec", 5, "show running-config") in device.privileges
    cfg = device.running_config()
    for line in ("banner login ^CAcces reserve^C", "no ip source-route", "ip host SRV-WEB 192.168.1.10",
                 "service timestamps log datetime msec localtime", "logging console warnings"):
        assert line in cfg
    assert "SRV-WEB" in _show(device, "show hosts") and "CEST" in _show(device, "show clock")
    apply_commands(device, ["conf t", "no logging console"])
    assert device.logging_console is None and "no logging console" in device.running_config()


def test_table_mac_et_archive():
    device = _config("switch", ["mac address-table static 0011.2233.4455 vlan 1 interface fa0/5",
                                "mac address-table aging-time 600", "archive", "path flash:sw-$h",
                                "write-memory", "maximum 5"], hostname="SW1")
    assert device.mac_static == [("0011.2233.4455", 1, "FastEthernet0/5")] and device.mac_aging == 600
    assert device.archive == {"path": "flash:sw-$h", "write_memory": True, "maximum": 5}
    assert "STATIC      Fa0/5" in _show(device, "show mac address-table")
    assert "sw-SW1-1" in _show(device, "archive config")
    out = _show(device, "copy running-config tftp://192.168.1.50/SW1-confg")
    assert "bytes copied" in out and device.backups == ["tftp://192.168.1.50/SW1-confg"]
    assert is_error(_show(device, "copy running-config tftp://serveur/SW1"))
    session = apply_commands(device, ["conf t"])
    assert is_error(session.execute("mac address-table static 0011.2233 vlan 1 interface fa0/5"))


def test_ntp_authentifie_et_sources():
    device = _config("router", ["interface loopback0", "ip address 10.255.0.1 255.255.255.255", "exit",
                                "ntp authenticate", "ntp authentication-key 1 md5 NtpK3y", "ntp trusted-key 1",
                                "ntp server 10.0.0.1 key 1 prefer", "ntp source lo0",
                                "logging source-interface loopback0", "ip ssh source-interface lo0"])
    assert device.ntp_authenticate and device.ntp_keys == {1: "NtpK3y"} and device.ntp_trusted == {1}
    assert device.ntp_server_options["10.0.0.1"] == "key 1 prefer"
    assert device.ntp_source == device.logging_source == device.ssh_source == "Loopback0"
    assert "ntp server 10.0.0.1 key 1 prefer" in device.running_config()


def test_mst_et_span():
    device = _config("switch", ["spanning-tree mode mst", "spanning-tree mst configuration", "name CAMPUS",
                                "revision 2", "instance 1 vlan 10,20", "instance 2 vlan 30-40", "exit",
                                "spanning-tree mst 1 priority 24576", "spanning-tree mst 2 root secondary",
                                "monitor session 1 source interface fa0/1 - 2 rx",
                                "monitor session 1 destination interface fa0/24"])
    assert device.mst_name == "CAMPUS" and device.mst_revision == 2
    assert device.mst_instances == {1: {10, 20}, 2: set(range(30, 41))}
    assert device.mst_priority == {1: 24576, 2: 28672}
    mon = device.monitor_sessions[1]
    assert mon["dest"] == "FastEthernet0/24" and ("FastEthernet0/1", "rx") in mon["sources"]
    assert "instance 1 vlan 10,20" in device.running_config()
    assert "Fa0/24" in _show(device, "show monitor")
    assert "CAMPUS" in _show(device, "show spanning-tree mst configuration")
    session = apply_commands(device, ["conf t"])
    assert is_error(session.execute("monitor session 1 source interface fa0/24"))
    apply_commands(device, ["conf t", "no monitor session 1"])
    assert device.monitor_sessions == {}


def test_port_security_vieillissement_et_ip_source_guard():
    device = _config("switch", ["int fa0/3", "switchport mode access", "switchport port-security",
                                "switchport port-security maximum 2",
                                "switchport port-security mac-address 0011.2233.4455",
                                "switchport port-security aging time 10",
                                "switchport port-security aging type inactivity",
                                "ip verify source port-security", "exit",
                                "ip source binding 00aa.bbcc.ddee vlan 1 192.168.1.20 interface fa0/3"])
    iface = device.intf("fa0/3")
    assert iface.port_security_macs == ["0011.2233.4455"] and iface.port_security_aging_time == 10
    assert iface.port_security_aging_type == "inactivity" and iface.ip_verify_source == "port-security"
    assert device.ip_source_bindings == [("00aa.bbcc.ddee", 1, "192.168.1.20", "FastEthernet0/3")]
    assert "192.168.1.20" in _show(device, "show ip verify source")


def test_dhcpv6_slaac_ospfv3():
    session = apply_commands(Device("router"), ["conf t"])
    assert is_error(session.execute("ipv6 router ospf 1"))  # ipv6 unicast-routing d'abord
    device = _config("router", ["ipv6 unicast-routing", "ipv6 dhcp pool LAN6", "dns-server 2001:DB8::53",
                                "domain-name tdm.local", "exit", "interface g0/0",
                                "ipv6 address 2001:db8:1::1/64", "ipv6 nd other-config-flag",
                                "ipv6 dhcp server LAN6", "ipv6 ospf 1 area 0", "interface g0/1",
                                "ipv6 address autoconfig", "exit", "ipv6 router ospf 1", "router-id 1.1.1.1",
                                "passive-interface g0/0"])
    assert device.dhcpv6_pools["LAN6"] == {"dns": ["2001:db8::53"], "domain": "tdm.local", "address_prefix": None}
    g0 = device.intf("g0/0")
    assert g0.ipv6_nd_other and g0.ipv6_dhcp_server == "LAN6" and g0.ospfv3_area == (1, "0")
    assert device.intf("g0/1").ipv6_autoconfig
    assert device.ospfv3[1].router_id == "1.1.1.1" and device.ospfv3[1].is_passive("g0/0")
    assert "ipv6 router ospf 1" in device.running_config() and "ipv6 ospf 1 area 0" in device.running_config()
    assert "GigabitEthernet0/0 (Area 0)" in _show(device, "show ipv6 protocols")


def test_acl_ipv6():
    device = _config("router", ["ipv6 access-list FILTRE6", "permit tcp 2001:DB8:1::/64 any eq 443",
                                "deny ipv6 any any log", "int g0/0", "ipv6 traffic-filter FILTRE6 in"])
    assert device.ipv6_acls["FILTRE6"] == ["permit tcp 2001:db8:1::/64 any eq 443", "deny ipv6 any any log"]
    assert device.intf("g0/0").ipv6_traffic_filter == {"in": "FILTRE6"}


def test_ospf_reseau_timers_authentification():
    device = _config("router", ["int g0/1", "ip address 10.0.0.1 255.255.255.252", "ip ospf network point-to-point",
                                "ip ospf hello-interval 5", "ip ospf dead-interval 20",
                                "ip ospf authentication message-digest", "ip ospf message-digest-key 1 md5 S3cr3t",
                                "exit", "router ospf 1", "network 10.0.0.0 0.0.0.3 area 0",
                                "area 0 authentication message-digest"])
    g1 = device.intf("g0/1")
    assert (g1.ospf_network, g1.ospf_hello, g1.ospf_dead) == ("point-to-point", 5, 20)
    assert g1.ospf_auth == "message-digest" and g1.ospf_md5_keys == {1: "S3cr3t"}
    assert device.ospf[1].area_auth == {"0": "message-digest"}
    out = _show(device, "show ip ospf interface brief")
    assert "point-to-point" in out and "md5" in out


def test_eigrp_stub_resume_variance():
    device = _config("router", ["router eigrp 100", "network 10.0.0.0", "eigrp stub", "variance 2", "exit",
                                "int s0/0/0", "ip summary-address eigrp 100 10.1.0.0 255.255.252.0"])
    assert device.eigrp[100].stub == "connected summary" and device.eigrp[100].variance == 2
    assert device.intf("s0/0/0").eigrp_summaries == [(100, "10.1.0.0", "255.255.252.0")]
    apply_commands(device, ["conf t", "router eigrp 100", "eigrp stub receive-only"])
    assert device.eigrp[100].stub == "receive-only"


def test_bgp_prefix_list_route_map():
    session = apply_commands(Device("router"), ["conf t", "router bgp 65001"])
    assert is_error(session.execute("neighbor 203.0.113.1 description FAI"))  # remote-as d'abord
    device = _config("router", ["ip route 198.51.100.0 255.255.255.0 null0",
                                "ip prefix-list SORTIE seq 5 permit 198.51.100.0/24",
                                "ip prefix-list RFC1918 permit 10.0.0.0/8 le 32",
                                "route-map LP-FAI1 permit 10", "set local-preference 200", "exit",
                                "router bgp 65001", "bgp router-id 1.1.1.1",
                                "neighbor 203.0.113.1 remote-as 65000", "neighbor 203.0.113.1 description FAI-1",
                                "neighbor 203.0.113.1 prefix-list SORTIE out",
                                "neighbor 203.0.113.1 route-map LP-FAI1 in",
                                "network 198.51.100.0 mask 255.255.255.0"])
    bgp = device.bgp
    nb = bgp.neighbors["203.0.113.1"]
    assert bgp.asn == 65001 and nb.remote_as == 65000 and nb.description == "FAI-1"
    assert nb.prefix_lists == {"out": "SORTIE"} and nb.route_maps == {"in": "LP-FAI1"}
    assert bgp.has_network("198.51.100.0", "255.255.255.0")
    assert device.plist("SORTIE") == ["permit 198.51.100.0/24"]
    assert device.plist("RFC1918") == ["permit 10.0.0.0/8 le 32"]
    assert device.rmap("LP-FAI1", 10).sets == ["local-preference 200"]
    assert device.has_route("198.51.100.0", "255.255.255.0", "null0")
    assert "*>" in _show(device, "show ip bgp") and "65000" in _show(device, "show ip bgp summary")
    session = apply_commands(device, ["conf t"])
    assert is_error(session.execute("ip prefix-list X permit 10.0.0.0/8 ge 4"))


def test_pbr_et_redistribution_avec_route_map():
    device = _config("router", ["access-list 101 permit ip 192.168.20.0 0.0.0.255 any",
                                "route-map PBR-INVITES permit 10", "match ip address 101",
                                "set ip next-hop 10.0.0.6", "exit", "int g0/0", "ip policy route-map PBR-INVITES",
                                "exit", "router ospf 1", "redistribute static subnets route-map STATIQUES"])
    entry = device.rmap("PBR-INVITES")
    assert entry.matches == ["ip address 101"] and entry.sets == ["ip next-hop 10.0.0.6"]
    assert device.intf("g0/0").policy_route_map == "PBR-INVITES"
    assert device.ospf[1].redist("static") == "static subnets route-map STATIQUES"
    apply_commands(device, ["conf t", "route-map PBR-INVITES permit 10", "set ip next-hop 10.0.0.10"])
    assert device.rmap("PBR-INVITES").sets == ["ip next-hop 10.0.0.10"]


def test_vrf_lite():
    device = _config("router", ["int g0/1", "ip address 10.1.1.1 255.255.255.0", "no shutdown"])
    session = apply_commands(device, ["conf t", "int g0/1"])
    assert is_error(session.execute("vrf forwarding CLIENT-A"))  # VRF absente
    apply_commands(device, ["conf t", "vrf definition CLIENT-A", "rd 65000:1", "address-family ipv4",
                            "exit-address-family", "exit"])
    out = session.execute("vrf forwarding CLIENT-A")
    assert "removed due to enabling VRF CLIENT-A" in out and device.intf("g0/1").ip is None
    session.execute("ip address 10.1.1.1 255.255.255.0")
    apply_commands(device, ["conf t", "ip route vrf CLIENT-A 0.0.0.0 0.0.0.0 10.1.1.254"])
    assert device.has_vrf_route("CLIENT-A", "0.0.0.0", "0.0.0.0", "10.1.1.254")
    assert "10.1.1.0/24" not in _show(device, "show ip route")
    assert "10.1.1.0/24" in _show(device, "show ip route vrf CLIENT-A")
    assert "vrf forwarding CLIENT-A" in device.running_config()


def test_aaa_radius_tacacs():
    device = _config("router", ["aaa new-model", "radius server ISE-1",
                                "address ipv4 10.0.0.20 auth-port 1812 acct-port 1813",
                                "key R4d1usK3y", "exit", "aaa group server radius ISE", "server name ISE-1", "exit",
                                "aaa authentication login default group ISE local",
                                "aaa authorization exec default group ISE local",
                                "aaa accounting exec default start-stop group ISE",
                                "line vty 0 4", "authorization exec default"])
    assert device.radius_servers["ISE-1"] == {"address": "10.0.0.20", "auth_port": 1812, "acct_port": 1813,
                                              "key": "R4d1usK3y"}
    assert device.aaa_groups["ISE"] == {"type": "radius", "servers": ["ISE-1"]}
    assert device.aaa_authentication["login default"] == "group ISE local"
    assert device.aaa_authorization["exec default"] == "group ISE local"
    assert device.aaa_accounting["exec default"] == "start-stop group ISE"
    assert device.lines["vty"].authorization_exec == "default"


def test_snmpv3():
    device = _config("router", ["snmp-server view SUPERVISION iso included",
                                "snmp-server group NOC v3 priv read SUPERVISION access 10",
                                "snmp-server user zabbix NOC v3 auth sha AuthPass1 priv aes 128 PrivPass1",
                                "snmp-server host 10.0.0.50 version 3 priv zabbix", "snmp-server enable traps"])
    assert device.snmp_groups["NOC"] == {"level": "priv", "read": "SUPERVISION", "access": "10"}
    assert device.snmp_users["zabbix"] == {"group": "NOC", "auth": "sha", "priv": "aes 128", "access": None}
    assert "zabbix NOC" not in device.running_config()  # comme IOS, les utilisateurs v3 n'y apparaissent pas
    assert "zabbix" in _show(device, "show snmp user")
    session = apply_commands(device, ["conf t"])
    assert is_error(session.execute("snmp-server user bob NOC v3 auth sha court"))


def test_tunnel_gre_et_ipsec():
    device = _config("router", ["access-list 110 permit ip 192.168.1.0 0.0.0.255 192.168.2.0 0.0.0.255",
                                "crypto isakmp policy 10", "encr aes 256", "hash sha256", "authentication pre-share",
                                "group 14", "lifetime 3600", "exit",
                                "crypto isakmp key 0 V3ryS3cr3t address 198.51.100.2",
                                "crypto ipsec transform-set TS esp-aes 256 esp-sha256-hmac", "mode tunnel", "exit",
                                "crypto map VPN 10 ipsec-isakmp", "set peer 198.51.100.2", "set transform-set TS",
                                "match address 110", "exit", "int g0/1", "crypto map VPN", "exit",
                                "interface tunnel 0", "ip address 172.16.0.1 255.255.255.252", "tunnel source g0/1",
                                "tunnel destination 198.51.100.2", "ip mtu 1400", "ip tcp adjust-mss 1360"])
    assert device.isakmp_policies[10] == {"encryption": "aes 256", "hash": "sha256", "authentication": "pre-share",
                                          "group": "14", "lifetime": "3600"}
    assert device.isakmp_keys == {"198.51.100.2": "V3ryS3cr3t"}
    assert device.transform_sets["TS"] == {"transforms": ["esp-aes 256", "esp-sha256-hmac"], "mode": "tunnel"}
    assert device.crypto_maps["VPN"][10] == {"peers": ["198.51.100.2"], "transform_set": "TS", "acl": "110"}
    tu = device.intf("tu0")
    assert tu.tunnel_source == "GigabitEthernet0/1" and tu.tunnel_destination == "198.51.100.2" and tu.ip_mtu == 1400
    assert device.intf("g0/1").crypto_map == "VPN"
    assert "Tunnel source GigabitEthernet0/1" in _show(device, "show interfaces tunnel 0")
    assert "crypto map VPN 10 ipsec-isakmp" in device.running_config()
    session = apply_commands(device, ["conf t", "crypto map VPN 10"])
    assert is_error(session.execute("set transform-set INCONNU"))


def test_qos_mqc_et_copp():
    device = _config("router", ["class-map match-any VOIX", "match dscp EF", "exit",
                                "policy-map WAN", "class VOIX", "priority percent 30", "class class-default",
                                "fair-queue", "exit", "exit", "int g0/1", "service-policy output WAN", "exit",
                                "policy-map COPP", "class class-default",
                                "police 64000 conform-action transmit exceed-action drop", "exit", "exit",
                                "control-plane", "service-policy input COPP"])
    assert device.class_maps["VOIX"] == {"type": "match-any", "matches": ["dscp ef"]}
    assert device.policy_maps["WAN"] == {"VOIX": ["priority percent 30"], "class-default": ["fair-queue"]}
    assert device.intf("g0/1").service_policies == {"output": "WAN"}
    assert device.control_plane_policy == "COPP"
    session = apply_commands(device, ["conf t", "policy-map WAN"])
    assert is_error(session.execute("class INCONNUE"))
    assert session.prompt.endswith("(config-pmap)#")
    session.execute("class VOIX")
    assert session.prompt.endswith("(config-pmap-c)#")
    session.execute("exit")
    assert session.prompt.endswith("(config-pmap)#")


@pytest.mark.parametrize("exercise", EXERCISES, ids=[e["id"] for e in EXERCISES])
def test_cours_et_documentation(exercise):
    """Chaque exercice réseau a un vrai cours et 1 à 3 liens de documentation."""
    words = len(exercise.get("cours", "").split())
    assert 180 <= words <= 650, words
    docs = exercise.get("docs", [])
    assert 1 <= len(docs) <= 3 and all(d["url"].startswith("https://") and d["title"] for d in docs)


def test_dtp_dynamique_et_sources_en_deux_mots():
    device = _config("switch", ["int g0/1", "switchport mode dynamic auto", "int g0/2",
                                "switchport mode dynamic desirable", "exit", "interface loopback 0",
                                "ip address 10.255.0.9 255.255.255.255", "exit", "ntp source loopback 0",
                                "logging source-interface Loopback 0", "ip ssh source-interface lo0"])
    assert device.intf("g0/1").mode is None and device.intf("g0/2").mode is None
    assert device.ntp_source == device.logging_source == device.ssh_source == "Loopback0"
    session = apply_commands(device, ["conf t", "int g0/1"])
    assert is_error(session.execute("switchport mode dynamic toujours"))


def test_negation_sans_valeur_et_clear():
    device = _config("router", ["int g0/1", "ip ospf hello-interval 30", "ip ospf cost 50",
                                "no ip ospf hello-interval", "no ip ospf cost"])
    assert device.intf("g0/1").ospf_hello is None and device.intf("g0/1").ospf_cost is None
    session = apply_commands(device, ["conf t", "int g0/1"])
    assert is_error(session.execute("ip ospf hello-interval"))  # sans « no », la valeur reste exigée
    session = apply_commands(_config("router", ["router ospf 1"]), [])
    assert "Reset ALL OSPF" in session.execute("clear ip ospf process")
    assert is_error(session.execute("clear ip bgp *"))  # BGP non configuré
