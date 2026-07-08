"""Ciena_CFM extension: MEP table parsing and benchmark sequences."""
from conftest import load_fixture
from Ciena_CFM import (parse_cfm_mep_table, benchmark_setup_sequence,
                       benchmark_teardown_sequence, cfm_status_commands,
                       BENCH_REFLECTOR, BENCH_TEST)


def test_parse_cfm_mep_table_real_output():
    meps = parse_cfm_mep_table(load_fixture('ciena_cfm_mep_show.txt'))
    assert len(meps) == 1
    m = meps[0]
    assert m['service'].startswith('ME-EVC-NNI_20.VLXM.014024')
    assert m['port'] == '8'
    assert m['vid'] == '1507'
    assert m['mepid'] == '25'
    assert m['type'] == 'down'
    assert m['mac'] == '04:79:FD:16:C1:E9'
    assert m['admin'] == 'en' and m['ccm'] == 'on'
    assert m['sd_mode'] == 'near-end'


def test_parse_cfm_mep_table_empty_output():
    assert parse_cfm_mep_table('') == []
    assert parse_cfm_mep_table('no meps configured') == []


def test_benchmark_setup_matches_mined_sessions():
    assert benchmark_setup_sequence('1', 'EDIA-3994-ref') == [
        f'benchmark create reflector name {BENCH_REFLECTOR} port 1',
        f'benchmark reflector set name {BENCH_REFLECTOR} mode out-of-service',
        f'benchmark test create name {BENCH_TEST} vtag-stack *',
        f'benchmark reflector clear name {BENCH_REFLECTOR} statistics',
        'benchmark enable',
        'benchmark reflector enable',
        f'benchmark test enable name {BENCH_TEST}',
        'interface enable ip-interface EDIA-3994-ref',
        'bench sh',
    ]


def test_benchmark_setup_without_interface():
    seq = benchmark_setup_sequence('2')
    assert not any('ip-interface' in c for c in seq)
    assert seq[-1] == 'bench sh'


def test_benchmark_teardown_variants():
    plain = benchmark_teardown_sequence()
    assert plain == [f'benchmark test disable name {BENCH_TEST}',
                     'benchmark disable', 'benchmark reflector disable',
                     'bench sh']
    full = benchmark_teardown_sequence('EDIA-3994-ref', delete=True)
    assert 'interface disable ip-interface EDIA-3994-ref' in full
    assert any('all-test-instances' in c for c in full)
    assert full[-1] == 'bench sh'


def test_status_commands_are_readonly():
    for cmd in cfm_status_commands():
        assert cmd.split()[-1] == 'show' or ' show' in cmd
