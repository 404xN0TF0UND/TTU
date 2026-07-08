"""Port_Disable: target parsing, sequences, verification, safety guards."""
import logging

from Port_Disable import (parse_targets_text, disable_sequence, _post_ok,
                          disable_target, verify_command)


def test_parse_targets_all_vendors_and_errors():
    targets, errors = parse_targets_text("""# comment
soag06.cinco.tx.houston.comcast.net,1/1/10,nokia
ssag02.area4.il.chicago.comcast.net,GigabitEthernet0/0/0/5,xr
ag-set05w.seatac.wa.seattle.comcast.net,ge-0/2/2,juniper
nid-cpe-x.fl.comcast.net,3,ciena
badline
host2,1/1/2,fakevendor
autodetect.host.net,1/1/3
""")
    assert [t[2] for t in targets] == [
        'nokia_sros', 'cisco_xr', 'juniper_junos', 'ciena_saos', None]
    assert len(errors) == 2


def test_disable_sequences_match_mined_workflows():
    assert disable_sequence('nokia_sros', '1/1/10') == [
        'configure exclusive', 'port 1/1/10 admin-state disable',
        'validate', 'compare', 'commit', 'quit-config']
    assert disable_sequence('cisco_xr', 'GigabitEthernet0/0/0/5') == [
        'configure exclusive', 'interface GigabitEthernet0/0/0/5',
        'shutdown', 'commit', 'end']
    assert disable_sequence('juniper_junos', 'ge-0/2/2') == [
        'configure exclusive', 'set interfaces ge-0/2/2 disable',
        'commit and-quit']
    assert disable_sequence('ciena_saos', '3') == [
        'port disable port 3', 'configuration save']


def test_verify_command_is_readonly_show():
    for vendor, port in [('nokia_sros', '1/1/10'), ('cisco_xr', 'TenGigE0/1/0/1'),
                         ('juniper_junos', 'ge-0/2/2'), ('ciena_saos', '3')]:
        assert verify_command(vendor, port).split()[0] in ('show', 'port')


def test_post_ok_logic():
    assert _post_ok('nokia_sros', {'admin': 'Down', 'oper': 'Down'})
    assert _post_ok('cisco_xr', {'admin': 'down', 'oper': 'down'})
    assert _post_ok('ciena_saos', {'admin': 'down', 'oper': 'disabled'})
    assert not _post_ok('nokia_sros', {'admin': 'Up', 'oper': 'Up'})
    assert not _post_ok('nokia_sros', {})


def test_guard_no_commands_on_precheck_failure():
    logger = logging.getLogger('t')
    r = disable_target('h', '1/1/1', 'nokia_sros', 'u', 'p', logger,
                       pre={'error': 'unreachable', 'vendor': 'nokia_sros'})
    assert not r['success']
    assert 'pre-check failed' in r['error']
    assert r['outputs'] == {}          # nothing was sent


def test_guard_skip_when_already_admin_down():
    logger = logging.getLogger('t')
    r = disable_target('h', '1/1/1', 'nokia_sros', 'u', 'p', logger,
                       pre={'error': '', 'vendor': 'nokia_sros',
                            'admin': 'Down'})
    assert r['skipped'] and r['success']
    assert r['outputs'] == {}          # nothing was sent


def test_guard_unknown_vendor_refused():
    logger = logging.getLogger('t')
    r = disable_target('h', '1/1/1', 'bogus', 'u', 'p', logger,
                       pre={'error': '', 'vendor': 'bogus', 'admin': 'up'})
    assert not r['success'] and 'unknown vendor' in r['error']
    assert r['outputs'] == {}
