"""Editing, commenting on and deleting a Data Request through its pages."""
import pytest

from ckan import model
from ckanext.datarequests import db
from ckanext.datarequests.tests.cdp.conftest import STATUS_VALUES, redirect_target

STATUS_SELECT = 'id="field-status"'


def _edit_url(datarequest):
    return "/datarequest/edit/{}".format(datarequest["id"])


@pytest.mark.ckan_config("ckan.plugins", "activity datarequests")
@pytest.mark.usefixtures("with_plugins", "datarequest_tables")
class TestEditPage:

    def test_requester_outside_owning_organisation_cannot_see_status(self, scenario):
        datarequest = scenario.create(scenario.requester)

        response = scenario.requester.get(_edit_url(datarequest))

        assert response.status_code == 200
        assert STATUS_SELECT not in response.body

    @pytest.mark.parametrize("who", ["editor", "sysadmin"])
    def test_owning_organisation_editor_and_sysadmin_can_set_status(self, scenario, who):
        datarequest = scenario.create(scenario.requester)

        response = getattr(scenario, who).get(_edit_url(datarequest))

        assert response.status_code == 200
        assert STATUS_SELECT in response.body
        for status in STATUS_VALUES:
            assert '<option value="{}"'.format(status) in response.body

    def test_editor_changes_status_from_the_form(self, scenario):
        datarequest = scenario.create(scenario.requester)
        submitted = scenario.fields(id=datarequest["id"], status="Processing")

        response = scenario.editor.post(_edit_url(datarequest), submitted)

        assert redirect_target(response) == "datarequest/" + datarequest["id"]
        assert scenario.editor.call("show_datarequest", id=datarequest["id"])["status"] == "Processing"
        listing = scenario.editor.get("/datarequest")
        assert "Processing" in listing.body
        edit_page = scenario.editor.get(_edit_url(datarequest))
        assert '<option value="Processing" selected' in edit_page.body

    @pytest.mark.parametrize("url_template", ["/datarequest/{id}", "/datarequest/edit/{id}"])
    def test_outsider_is_refused(self, scenario, url_template):
        datarequest = scenario.create(scenario.requester)

        response = scenario.outsider.get(url_template.format(id=datarequest["id"]))

        assert response.status_code == 403


@pytest.mark.ckan_config("ckan.plugins", "activity datarequests")
@pytest.mark.usefixtures("with_plugins", "datarequest_tables")
class TestCommentPage:

    def test_posting_a_comment_lands_back_on_the_comment_page(self, scenario):
        datarequest = scenario.create(scenario.requester)
        url = "/datarequest/comment/{}".format(datarequest["id"])

        response = scenario.editor.post(url, {"comment": "Please confirm the reporting period", "comment-id": ""})

        assert redirect_target(response) == url.lstrip("/")
        page = scenario.editor.get(url)
        assert page.status_code == 200
        assert "Please confirm the reporting period" in page.body


@pytest.mark.ckan_config("ckan.plugins", "activity datarequests")
@pytest.mark.usefixtures("with_plugins", "datarequest_tables")
class TestDelete:

    def test_deleting_hides_the_request_but_keeps_the_row(self, scenario):
        datarequest = scenario.create(scenario.requester, title="Request to withdraw")

        response = scenario.requester.post("/datarequest/delete/{}".format(datarequest["id"]), {})

        assert redirect_target(response) == "datarequest"
        listing = scenario.sysadmin.get("/datarequest")
        assert 'href="/datarequest/{}"'.format(datarequest["id"]) not in listing.body
        assert scenario.listing_ids(scenario.sysadmin) == []
        row = model.Session.query(db.DataRequest).filter_by(id=datarequest["id"]).one()
        assert row.state == "deleted"
