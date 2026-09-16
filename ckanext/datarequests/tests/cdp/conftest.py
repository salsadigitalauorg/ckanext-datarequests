import pytest

from ckan.cli.cli import ckan as ckan_cli


@pytest.fixture
def datarequest_tables(cli, clean_db, migrate_db_for):
    """Create the Data Request tables the same way a deploy does."""
    # clean_db only runs core migrations; the activity plugin needs its own.
    migrate_db_for("activity")
    result = cli.invoke(ckan_cli, ["datarequests", "init-db"])
    assert result.exit_code == 0, result.output
