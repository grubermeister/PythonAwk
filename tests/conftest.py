from __future__ import annotations

import shutil

import pytest


@pytest.fixture(scope="session")
def gawk_path() -> str | None:
    return shutil.which("gawk")
