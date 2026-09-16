"""init-db and update-db over a database whose Data Request table predates the CDP columns."""
import datetime
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import text

import ckan.plugins.toolkit as tk
from ckan import model
from ckan.cli.cli import ckan as ckan_cli
from ckan.tests import factories
from ckanext.datarequests import constants
from ckanext.datarequests.tests.cdp.conftest import Api

CDP_COLUMNS = {
    "data_use_type",
    "who_will_access_this_data",
    "requesting_organisation",
    "data_storage_environment",
    "data_outputs_type",
    "data_outputs_description",
    "status",
    "requested_dataset",
}

# The table as the original extension created it, before this fork added anything.
LEGACY_TABLE = """
CREATE TABLE datarequests (
    user_id text,
    id text NOT NULL,
    title varchar(100) NOT NULL,
    description varchar(1000),
    organization_id text,
    open_time timestamp,
    accepted_dataset_id text,
    close_time timestamp,
    closed boolean,
    PRIMARY KEY (id, title)
)
"""


def _columns():
    inspector = sa.inspect(model.meta.engine)
    return {column["name"]: column for column in inspector.get_columns("datarequests")}


def _run(cli, command):
    result = cli.invoke(ckan_cli, ["datarequests", command])
    assert result.exit_code == 0, result.output


@pytest.fixture
def legacy_database(clean_db, migrate_db_for):
    """A CKAN database holding one Data Request in the pre-fork table shape."""
    if tk.check_ckan_version(min_version="2.11"):
        migrate_db_for("activity")
    requester = factories.User()
    legacy_id = str(uuid.uuid4())
    model.Session.remove()
    with model.meta.engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS datarequests_followers, datarequests_comments, datarequests"))
        connection.execute(text(LEGACY_TABLE))
        connection.execute(
            text("INSERT INTO datarequests (user_id, id, title, description, open_time, closed) "
                 "VALUES (:user_id, :id, :title, :description, :open_time, false)"),
            {"user_id": requester["id"], "id": legacy_id, "title": "Legacy request",
             "description": "Made before the CDP columns existed", "open_time": datetime.datetime(2024, 1, 15, 9, 0)},
        )
    return legacy_id


@pytest.mark.ckan_config("ckan.plugins", "activity datarequests")
@pytest.mark.usefixtures("with_plugins")
class TestMigration:

    def test_init_db_and_update_db_bring_a_legacy_table_up_to_date(self, app, cli, legacy_database):
        _run(cli, "init-db")
        _run(cli, "update-db")

        columns = _columns()
        assert CDP_COLUMNS | {"state"} <= set(columns)
        assert columns["title"]["type"].length == constants.NAME_MAX_LENGTH
        assert sa.inspect(model.meta.engine).has_table("datarequests_comments")
        assert sa.inspect(model.meta.engine).has_table("datarequests_followers")

        listing = Api(app, factories.SysadminWithToken()).call("list_datarequests")
        assert [item["id"] for item in listing["result"]] == [legacy_database]
        assert listing["result"][0]["title"] == "Legacy request"

    def test_update_db_is_idempotent(self, cli, legacy_database):
        _run(cli, "init-db")
        _run(cli, "update-db")
        after_first = {name: str(column["type"]) for name, column in _columns().items()}

        _run(cli, "update-db")

        after_second = {name: str(column["type"]) for name, column in _columns().items()}
        assert after_second == after_first
