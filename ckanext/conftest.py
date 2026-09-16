"""Skip upstream tests that assert behaviour this fork deliberately changes.

The list lives in a fork-owned file so upstream's test modules are never
edited and the next upstream merge cannot conflict on them.
"""
import pathlib

DESELECTED_FILE = pathlib.Path(__file__).parent / "datarequests" / "tests" / "cdp" / "deselected-upstream-tests.txt"


def _deselected_ids():
    return {
        line.strip()
        for line in DESELECTED_FILE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }


def pytest_collection_modifyitems(config, items):
    wanted_out = _deselected_ids()
    # Node ids are relative to pytest's rootdir, which varies with how the
    # suite is invoked, so match on the suffix.
    deselected = [item for item in items if any(item.nodeid.endswith(entry) for entry in wanted_out)]
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = [item for item in items if item not in deselected]
