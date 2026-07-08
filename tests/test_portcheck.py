"""PortCheck parsers against real captured device outputs."""
from conftest import load_fixture
from PortCheck import (parse_nokia, parse_xr, parse_juniper, parse_ciena,
                       commands_for, VENDOR_ALIASES)


def test_parse_nokia_real_output():
    out = load_fixture('nokia_show_port.txt')
    r = parse_nokia({'show port 1/1/47': out}, '1/1/47')
    assert r['admin'] == 'up'
    assert r['oper'] == 'down'
    assert r['descr'].startswith('PHY|1G|L2|CCS-EDGE|type:BIZ-NNI')
    assert r['tx_dbm'] == '1.95'
    assert r['rx_dbm'] == '-40.00'
    assert 'SFP' in r['optic'] and 'GIGE-LX' in r['optic']
    assert '1537' in r['optic']  # TX laser wavelength, nm


def test_parse_xr_real_output():
    out = load_fixture('xr_show_interfaces.txt')
    port = 'GigabitEthernet0/0/0/12'
    r = parse_xr({f'show interfaces {port}': out}, port)
    # 'is down' without 'administratively' => admin up, oper down
    assert r['admin'] == 'up'
    assert r['oper'] == 'down'
    assert r['descr'].startswith('PHY|1G|BIZ-NNI|rhost:CLSPCOWS06W')


def test_parse_juniper_real_output():
    out = load_fixture('juniper_show_interfaces.txt')
    r = parse_juniper({'show interfaces ge-1/0/9': out}, 'ge-1/0/9')
    assert r['admin'] == 'up'      # Enabled
    assert r['oper'] == 'down'     # Physical link is Down
    assert r['descr'].startswith('PHY|1G|BIZ-NNI|rhost:WVCYUTWW01W')
    assert r['optic'].startswith('Fiber')


def test_parse_ciena_real_output():
    out = load_fixture('ciena_port_show.txt')
    r = parse_ciena({'port show port 1': out}, '1')
    assert r['admin'] == 'up'      # Ena
    assert r['oper'] == 'up'
    r2 = parse_ciena({'port show port 2': out}, '2')
    assert r2['admin'] == 'down'   # Dis
    assert r2['oper'] == 'down'


def test_commands_for_each_vendor():
    assert commands_for('nokia_sros', '1/1/10') == ['show port 1/1/10']
    xr = commands_for('cisco_xr', 'TenGigE0/4/0/9')
    assert xr[0] == 'show interfaces TenGigE0/4/0/9'
    assert xr[1] == 'show controllers optics 0/4/0/9'
    assert commands_for('juniper_junos', 'xe-0/1/3') == [
        'show interfaces xe-0/1/3',
        'show interfaces diagnostics optics xe-0/1/3']
    assert commands_for('ciena_saos', '3') == [
        'port show port 3', 'port xcvr show port 3']


def test_vendor_aliases_cover_shorthand():
    for alias, canonical in [('nokia', 'nokia_sros'), ('xr', 'cisco_xr'),
                             ('juniper', 'juniper_junos'),
                             ('ciena', 'ciena_saos'), ('9k', 'cisco_xr'),
                             ('5501', 'cisco_xr'), ('saos', 'ciena_saos')]:
        assert VENDOR_ALIASES[alias] == canonical
