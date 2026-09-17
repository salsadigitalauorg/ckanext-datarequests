"""The Data Request form, submitted through the page like a requester does."""
import pytest

from ckanext.datarequests.tests.cdp.conftest import cdp_plugins, redirect_target

NEW_URL = "/datarequest/new"


def _created_id(response):
    return redirect_target(response).rsplit("/", 1)[-1]


@cdp_plugins
@pytest.mark.usefixtures("with_plugins", "datarequest_tables")
class TestDataRequestForm:

    def test_full_submission_stores_every_cdp_field(self, scenario):
        submitted = scenario.fields()

        response = scenario.requester.post(NEW_URL, submitted)

        stored = scenario.requester.call("show_datarequest", id=_created_id(response))
        assert {name: stored[name] for name in submitted} == submitted
        assert stored["user_id"] == scenario.requester.user["id"]

    def test_submission_without_status_field_is_assigned(self, scenario):
        submitted = scenario.fields()
        assert "status" not in submitted

        response = scenario.requester.post(NEW_URL, submitted)

        stored = scenario.requester.call("show_datarequest", id=_created_id(response))
        assert stored["status"] == "Assigned"

    def test_missing_required_field_rerenders_with_error_and_values(self, scenario):
        submitted = scenario.fields(data_use_type="")

        response = scenario.requester.post(NEW_URL, submitted)

        assert response.status_code == 200
        assert "Data use type cannot be empty" in response.body
        for name in ("title", "description", "who_will_access_this_data", "data_storage_environment", "data_outputs_description"):
            assert submitted[name] in response.body, name
        assert '<option value="{}" selected'.format(submitted["data_outputs_type"]) in response.body
        assert 'value="{}"'.format(submitted["requested_dataset"]) in response.body
        assert 'value="{}"'.format(submitted["organization_id"]) in response.body
        assert '<option value="{}" selected'.format(submitted["requesting_organisation"]) in response.body
        assert scenario.sysadmin.call("list_datarequests")["count"] == 0

    def test_form_opened_from_a_dataset_is_prefilled(self, scenario):
        response = scenario.requester.get(NEW_URL, query_string={"id": scenario.dataset["name"]})

        assert response.status_code == 200
        assert 'value="{}"'.format(scenario.dataset["title"]) in response.body
        assert 'value="{}"'.format(scenario.dataset["id"]) in response.body
        assert scenario.other_org["name"] in response.body
