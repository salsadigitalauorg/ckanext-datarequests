"""Who sees which Data Requests in listings, and how the Status filter behaves."""
import pytest
from sqlalchemy import text

from ckan import model


def _facet_names(listing, facet):
    return {item["name"]: item["count"] for item in listing["facets"].get(facet, {}).get("items", [])}


@pytest.mark.ckan_config("ckan.plugins", "activity datarequests")
@pytest.mark.usefixtures("with_plugins", "datarequest_tables")
class TestVisibleRules:

    def test_sysadmin_sees_every_active_request(self, scenario):
        against_owning_org = scenario.create(scenario.requester)
        against_other_org = scenario.create(scenario.outsider, dataset=scenario.other_dataset)

        assert set(scenario.listing_ids(scenario.sysadmin)) == {against_owning_org["id"], against_other_org["id"]}

    def test_member_sees_own_and_owning_organisation_requests_only(self, scenario):
        own = scenario.create(scenario.member, dataset=scenario.other_dataset, requesting_org=scenario.owning_org)
        against_owning_org = scenario.create(scenario.requester)
        scenario.create(scenario.outsider, dataset=scenario.other_dataset)

        assert set(scenario.listing_ids(scenario.member)) == {own["id"], against_owning_org["id"]}

    def test_filter_by_foreign_organisation_returns_only_own_requests(self, scenario):
        own = scenario.create(scenario.member, dataset=scenario.other_dataset, requesting_org=scenario.owning_org)
        scenario.create(scenario.outsider, dataset=scenario.other_dataset)

        assert scenario.listing_ids(scenario.member, organization_id=scenario.other_org["id"]) == [own["id"]]

    def test_facets_match_visible_requests_and_callers_organisations(self, scenario):
        scenario.create(scenario.member, dataset=scenario.other_dataset, requesting_org=scenario.owning_org)
        against_owning_org = scenario.create(scenario.requester)
        scenario.create(scenario.outsider, dataset=scenario.other_dataset)
        scenario.update(scenario.editor, against_owning_org, status="Processing")

        listing = scenario.member.call("list_datarequests")

        assert _facet_names(listing, "status") == {"Assigned": 1, "Processing": 1}
        assert _facet_names(listing, "organization") == {scenario.owning_org["name"]: 1}

    def test_sysadmin_organisation_facet_covers_every_organisation(self, scenario):
        scenario.create(scenario.requester)
        scenario.create(scenario.outsider, dataset=scenario.other_dataset)

        listing = scenario.sysadmin.call("list_datarequests")

        assert _facet_names(listing, "organization") == {scenario.owning_org["name"]: 1, scenario.other_org["name"]: 1}

    def test_own_requests_come_first_when_sorting_newest_first(self, scenario):
        own = scenario.create(scenario.member, dataset=scenario.other_dataset, requesting_org=scenario.owning_org)
        newer = scenario.create(scenario.requester)

        assert scenario.listing_ids(scenario.member, sort="desc") == [own["id"], newer["id"]]

    def test_own_requests_come_first_when_sorting_oldest_first(self, scenario):
        older = scenario.create(scenario.requester)
        own = scenario.create(scenario.member, dataset=scenario.other_dataset, requesting_org=scenario.owning_org)

        assert scenario.listing_ids(scenario.member, sort="asc") == [own["id"], older["id"]]

    def test_request_with_null_state_is_listed_as_active(self, scenario):
        # Rows written before the state column existed have no State at all.
        legacy = scenario.create(scenario.requester)
        model.Session.execute(text("UPDATE datarequests SET state = NULL WHERE id = :id"), {"id": legacy["id"]})
        model.Session.commit()

        assert scenario.listing_ids(scenario.sysadmin) == [legacy["id"]]


@pytest.mark.ckan_config("ckan.plugins", "activity datarequests")
@pytest.mark.usefixtures("with_plugins", "datarequest_tables")
class TestListingPages:

    def test_listing_page_has_status_facet_and_status_filter_narrows_results(self, scenario):
        assigned = scenario.create(scenario.requester, title="Request still assigned")
        processing = scenario.create(scenario.editor, title="Request being processed")
        scenario.update(scenario.editor, processing, title=processing["title"], status="Processing")

        unfiltered = scenario.sysadmin.get("/datarequest")
        filtered = scenario.sysadmin.get("/datarequest", query_string={"status": "Processing"})

        assert unfiltered.status_code == 200
        assert "status=Processing" in unfiltered.body
        assert "status=Assigned" in unfiltered.body
        assert assigned["title"] in unfiltered.body and processing["title"] in unfiltered.body
        assert processing["title"] in filtered.body
        assert assigned["title"] not in filtered.body

    @pytest.mark.parametrize("url_template", [
        "/datarequest",
        "/organization/datarequest/{org}",
        "/user/datarequest/{user}",
    ])
    def test_every_listing_keeps_the_status_filter_in_its_search_form(self, scenario, url_template):
        scenario.create(scenario.requester)
        url = url_template.format(org=scenario.owning_org["name"], user=scenario.requester.user["name"])

        response = scenario.sysadmin.get(url, query_string={"status": "Assigned"})

        assert response.status_code == 200
        assert '<input type="hidden" name="status" value="Assigned"' in response.body
