from pathlib import Path

import pytest

LAB_ROOT = Path("/Volumes/cccr-lab")
REFERENCE_DIR = LAB_ROOT / "001_projects" / "003_cosmos-adapt" / "011_DAMAGES_results_final"


def pytest_collection_modifyitems(config, items):
    if REFERENCE_DIR.is_dir():
        return
    skip = pytest.mark.skip(reason=f"reference outputs not mounted: {REFERENCE_DIR}")
    for item in items:
        if "regression" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def reference_dir():
    return REFERENCE_DIR
