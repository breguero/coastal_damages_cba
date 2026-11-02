"""Regression tests need reference outputs: the lab share, or the Santa Cruz sample data with
COSMOS_DATA_ROOT=<sample> and COSMOS_REFERENCE_DIR=<sample>/reference_results. Otherwise they are skipped."""

import pytest

from coastal_risk_cba.config import Config


def pytest_collection_modifyitems(config, items):
    if Config.load().available_regression_sites:
        return
    skip = pytest.mark.skip(reason="no reference outputs (set COSMOS_DATA_ROOT and COSMOS_REFERENCE_DIR)")
    for item in items:
        if "regression" in item.keywords:
            item.add_marker(skip)
