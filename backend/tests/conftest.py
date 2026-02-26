import os

import pytest


@pytest.fixture(autouse=True)
def _disable_ingestion_env(monkeypatch):
    monkeypatch.setenv("DISABLE_INGESTION", "1")
    yield
