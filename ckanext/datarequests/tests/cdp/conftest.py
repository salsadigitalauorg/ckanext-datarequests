import pytest

import ckan.plugins.toolkit as tk
from ckan.cli.cli import ckan as ckan_cli
from ckan.tests import factories

STATUS_VALUES = (
    "Assigned",
    "Processing",
    "Finalised - Approved",
    "Finalised - Not Approved",
    "Assign to Internal Data Catalogue Support",
)


def migrate_plugin_tables(migrate_db_for):
    # clean_db only runs core migrations. From CKAN 2.11 the activity plugin
    # carries its own; on 2.10 its tables are still in core and asking alembic
    # for plugin migrations fails and breaks the CLI calls that follow.
    if tk.check_ckan_version(min_version="2.11"):
        migrate_db_for("activity")


def run_datarequests_command(cli, command):
    result = cli.invoke(ckan_cli, ["datarequests", command])
    assert result.exit_code == 0, result.output


def redirect_target(response):
    """The path a redirect response points at, without the leading slash."""
    assert response.status_code == 302, response.body
    return response.headers["Location"].split("://", 1)[-1].split("/", 1)[-1]


@pytest.fixture
def datarequest_tables(cli, clean_db, migrate_db_for):
    """Create the Data Request tables the same way a deploy does."""
    migrate_plugin_tables(migrate_db_for)
    run_datarequests_command(cli, "init-db")


class Client:
    """One user's view of the site: pages through the test app, actions through the API."""

    def __init__(self, app, user):
        self.app = app
        self.user = user
        self.headers = {"Authorization": user["token"]}

    def call(self, action, **data):
        response = self.app.post("/api/action/" + action, json=data, headers=self.headers)
        body = response.json
        assert body["success"], body
        return body["result"]

    def get(self, url, **kwargs):
        return self.app.get(url, headers=self.headers, **kwargs)

    def post(self, url, data, **kwargs):
        # CKAN's test client follows redirects by default, which hides the
        # redirect a successful form post answers with.
        kwargs.setdefault("follow_redirects", False)
        return self.app.post(url, data=data, headers=self.headers, **kwargs)


def form_fields(dataset, requesting_org, **overrides):
    """A complete Data Request form submission, Status left to its default."""
    fields = {
        "title": dataset["title"],
        "description": "Purpose of the request",
        "organization_id": dataset["owner_org"],
        "requested_dataset": dataset["id"],
        "data_use_type": "Service delivery",
        "who_will_access_this_data": "Data analysts on the project",
        "requesting_organisation": requesting_org["id"],
        "data_storage_environment": "Departmental secure cloud",
        "data_outputs_type": "Report",
        "data_outputs_description": "Quarterly summary report",
    }
    fields.update(overrides)
    return fields


class Scenario:
    """One Owning Organisation with a dataset, the people around it, and a second organisation."""

    def __init__(self, app):
        self.app = app
        self.sysadmin = Client(app, factories.SysadminWithToken())
        self.requester = Client(app, factories.UserWithToken())
        self.editor = Client(app, factories.UserWithToken())
        self.member = Client(app, factories.UserWithToken())
        self.outsider = Client(app, factories.UserWithToken())
        self.follower = Client(app, factories.UserWithToken())
        self.owning_org = factories.Organization(users=[
            {"name": self.editor.user["name"], "capacity": "editor"},
            {"name": self.member.user["name"], "capacity": "member"},
        ])
        # The Requesting Organisation options come from the organisations the
        # requester belongs to, so a requester with none cannot submit the form.
        self.other_org = factories.Organization(users=[
            {"name": self.outsider.user["name"], "capacity": "editor"},
            {"name": self.requester.user["name"], "capacity": "member"},
        ])
        self.dataset = factories.Dataset(owner_org=self.owning_org["id"])
        self.other_dataset = factories.Dataset(owner_org=self.other_org["id"])

    def fields(self, dataset=None, requesting_org=None, **overrides):
        return form_fields(dataset or self.dataset, requesting_org or self.other_org, **overrides)

    def create(self, client=None, dataset=None, requesting_org=None, **overrides):
        """Create a Data Request as `client` (the requester by default) and return it."""
        client = client or self.requester
        return client.call("create_datarequest", **self.fields(dataset, requesting_org, **overrides))

    def update(self, client, datarequest, **overrides):
        """Resubmit a Data Request's fields as `client`, with `overrides` changed."""
        return client.call("update_datarequest", id=datarequest["id"], **self.fields(**overrides))

    def listing_ids(self, client, **params):
        return [item["id"] for item in client.call("list_datarequests", **params)["result"]]

    def follow(self, datarequest):
        self.follower.call("follow_datarequest", id=datarequest["id"])


@pytest.fixture
def scenario(app):
    return Scenario(app)
