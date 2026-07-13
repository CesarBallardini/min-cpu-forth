"""Placeholder end-to-end test -- wire up Playwright against a running
instance once there's a server to point it at."""

import pytest


@pytest.mark.e2e
def test_placeholder() -> None:
    pytest.skip('no running instance to test against yet')
