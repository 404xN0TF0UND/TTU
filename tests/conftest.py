"""Shared pytest setup: import paths + Flask test client.

Run from the repo root with:  python -m pytest tests/ -v
No SSH connections are made anywhere in this suite — parsers get real
captured outputs from tests/fixtures/, and route tests use Flask's
test client with unreachable-host guard paths only.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'fixtures')


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as f:
        return f.read()


@pytest.fixture(scope='session')
def app():
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()
