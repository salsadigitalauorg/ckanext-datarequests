import pytest

from ckan.cli.cli import ckan as ckan_cli


@pytest.fixture
def datarequest_tables(cli, clean_db):
    """Create the Data Request tables the same way a deploy does."""
    result = cli.invoke(ckan_cli, ["datarequests", "init-db"])
    assert result.exit_code == 0, result.output
