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


class Api:
    """Call actions through the API as one user, the way a client would."""

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
        self.sysadmin = Api(app, factories.SysadminWithToken())
        self.requester = Api(app, factories.UserWithToken())
        self.editor = Api(app, factories.UserWithToken())
        self.member = Api(app, factories.UserWithToken())
        self.outsider = Api(app, factories.UserWithToken())
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

    def fields(self, **overrides):
        return form_fields(self.dataset, self.other_org, **overrides)

    def create(self, api=None, **overrides):
        api = api or self.requester
        return api.call("create_datarequest", **self.fields(**overrides))


@pytest.fixture
def scenario(app):
    return Scenario(app)
