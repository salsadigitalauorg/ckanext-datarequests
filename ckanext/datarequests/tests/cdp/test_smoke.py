import pytest

from ckan.tests import factories
from ckanext.datarequests.tests.cdp.conftest import cdp_plugins


@cdp_plugins
@pytest.mark.usefixtures("with_plugins", "datarequest_tables")
class TestDataRequestPages:

    def test_sysadmin_can_open_data_requests_listing(self, app):
        sysadmin = factories.SysadminWithToken()

        response = app.get("/datarequest", headers={"Authorization": sysadmin["token"]})

        assert response.status_code == 200
