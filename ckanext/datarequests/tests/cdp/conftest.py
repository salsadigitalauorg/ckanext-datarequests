import pytest

import ckan.plugins.toolkit as tk
from ckan.cli.cli import ckan as ckan_cli


@pytest.fixture
def datarequest_tables(cli, clean_db, migrate_db_for):
    """Create the Data Request tables the same way a deploy does."""
    # clean_db only runs core migrations. From CKAN 2.11 the activity plugin
    # carries its own; on 2.10 its tables are still in core and asking alembic
    # for plugin migrations fails and breaks the CLI call below.
    if tk.check_ckan_version(min_version="2.11"):
        migrate_db_for("activity")
    result = cli.invoke(ckan_cli, ["datarequests", "init-db"])
    assert result.exit_code == 0, result.output
