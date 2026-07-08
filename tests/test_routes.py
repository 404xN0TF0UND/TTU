"""Flask route tests: every GET route serves, confirm gates hold.

No SSH happens: guard paths are exercised with missing fields, bad
tokens, off-grid frequencies, and unticked confirmations only.
"""
import pytest


def test_every_parameterless_get_route_serves(app, client):
    rules = [r.rule for r in app.url_map.iter_rules()
             if 'GET' in r.methods and '<' not in r.rule]
    assert len(rules) > 30
    for rule in rules:
        code = client.get(rule).status_code
        assert code in (200, 302), f'{rule} -> {code}'


def test_blueprints_registered(app):
    assert {'main', 'notes', 'devices', 'automation', 'library',
            'logs', 'tools'} <= set(app.blueprints)


class TestPortDisableGates:
    def test_bad_token_rejected(self, client):
        r = client.post('/scripts/port-disable',
                        data={'action': 'execute', 'token': 'bogus',
                              'confirm': 'DISABLE'})
        assert b'Preview expired' in r.data

    def test_missing_fields_rejected(self, client):
        r = client.post('/scripts/port-disable',
                        data={'action': 'preview', 'targets': '',
                              'username': '', 'password': ''})
        assert b'required!' in r.data

    def test_bad_vendor_flagged(self, client):
        r = client.post('/scripts/port-disable',
                        data={'action': 'preview',
                              'targets': 'h,1/1/1,fakevendor',
                              'username': 'u', 'password': 'p'})
        assert b'unknown vendor' in r.data


class TestRetuneGates:
    def test_off_grid_frequency_refused_before_ssh(self, client):
        r = client.post('/scripts/nokia-retune',
                        data={'action': 'preview', 'host': 'h',
                              'port': '1/1/1', 'frequency': '193.35',
                              'username': 'u', 'password': 'p'})
        assert b'not on the ITU' in r.data

    def test_garbage_frequency_refused(self, client):
        r = client.post('/scripts/nokia-retune',
                        data={'action': 'preview', 'host': 'h',
                              'port': '1/1/1', 'frequency': 'garbage',
                              'username': 'u', 'password': 'p'})
        assert b'Pre-check failed' in r.data

    def test_bad_token_rejected(self, client):
        r = client.post('/scripts/nokia-retune',
                        data={'action': 'execute', 'token': 'nope',
                              'confirm': 'RETUNE'})
        assert b'Preview expired' in r.data


class TestCienaBenchGates:
    def test_setup_without_confirm_blocked(self, client):
        r = client.post('/scripts/ciena-cfm',
                        data={'mode': 'bench_setup', 'device_ip': 'x',
                              'username': 'u', 'password': 'p',
                              'bench_port': '1'})
        assert b'tick the confirmation box' in r.data

    def test_setup_without_port_blocked(self, client):
        r = client.post('/scripts/ciena-cfm',
                        data={'mode': 'bench_setup', 'device_ip': 'x',
                              'username': 'u', 'password': 'p',
                              'confirm_bench': 'on'})
        assert b'Reflector port is required' in r.data


class TestSessionCredentials:
    def test_set_use_and_clear(self, client):
        r = client.post('/credentials',
                        data={'username': 'tester', 'password': 'pw'},
                        follow_redirects=True)
        assert b'held in memory' in r.data
        # scripts page shows the active banner
        assert b'Session credentials active' in client.get('/scripts').data
        # blank form creds now pass validation (fails later at parse/SSH
        # stage, not on the required-fields check)
        r = client.post('/scripts/port-check',
                        data={'targets': '', 'username': '', 'password': ''})
        assert b'Targets, username, and password are required!' in r.data
        r = client.post('/credentials', data={'action': 'clear'},
                        follow_redirects=True)
        assert b'cleared' in r.data
        assert b'Session credentials active' not in client.get('/scripts').data

    def test_missing_fields_rejected(self, client):
        r = client.post('/credentials', data={'username': '', 'password': ''},
                        follow_redirects=True)
        assert b'required!' in r.data


class TestItuGrid:
    def test_all_72_channels_rendered(self, client):
        html = client.get('/tools/itu-grid').data.decode()
        for ch in (1, 33, 72):
            assert f'id="ch{ch}"' in html
        assert '193300000' in html      # ch33 MHz
        assert '1550.92' in html        # ch33 nm
        assert '1577.03' in html and '1520.25' in html  # band edges
