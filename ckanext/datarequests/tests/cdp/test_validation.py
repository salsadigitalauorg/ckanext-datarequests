"""Field rules enforced when a Data Request is created or updated through the API."""
import pytest

from ckanext.datarequests.tests.cdp.conftest import cdp_plugins

REQUIRED_FIELDS = {
    "description": "Purpose of data use",
    "requested_dataset": "Requested dataset",
    "data_use_type": "Data use type",
    "who_will_access_this_data": "Who will access this data",
    "requesting_organisation": "Requesting organisation",
    "data_storage_environment": "Data storage environment",
    "data_outputs_type": "Data outputs type",
    "data_outputs_description": "Data outputs description",
}


def _errors(client, action, **data):
    response = client.app.post("/api/action/" + action, json=data, headers=client.headers, status=409)
    return response.json["error"]


@cdp_plugins
@pytest.mark.usefixtures("with_plugins", "datarequest_tables")
class TestValidation:

    @pytest.mark.parametrize("field,label", sorted(REQUIRED_FIELDS.items()))
    def test_each_required_field_is_reported_by_its_form_label(self, scenario, field, label):
        errors = _errors(scenario.requester, "create_datarequest", **scenario.fields(**{field: ""}))

        assert label in errors

    def test_unknown_status_is_rejected_on_update(self, scenario):
        datarequest = scenario.create()

        errors = _errors(scenario.editor, "update_datarequest", id=datarequest["id"], **scenario.fields(status="Closed"))

        assert errors["Status"] == ["Status value is not valid"]

    def test_two_requests_can_share_a_title(self, scenario):
        # One user each: a requester may only create one request every few minutes.
        first = scenario.create(scenario.requester, title="Same title")
        second = scenario.create(scenario.member, title="Same title", requesting_org=scenario.owning_org)
        third = scenario.create(scenario.editor, title="Another title", requesting_org=scenario.owning_org)

        renamed = scenario.update(scenario.editor, third, title="Same title")

        assert {first["title"], second["title"], renamed["title"]} == {"Same title"}
