"""Which mail each Data Request event enqueues, and the switch that stops all of it.

Recipients are read from the background job queue, which is where CKAN's
mailer picks them up. The Dataset Point of Contact recipient depends on a
scheming field the project adds to datasets, so it is not exercised here.
"""
import pytest

from ckan.lib import jobs

SUPPORT_EMAIL = "support@example.com"


class MailQueue:
    """The background job queue as the mailer sees it: one job per recipient."""

    def clear(self):
        for queue in jobs.get_all_queues():
            queue.empty()

    def recipients(self):
        return sorted(job.args[1] for queue in jobs.get_all_queues() for job in queue.jobs)


@pytest.fixture
def mail_queue():
    queue = MailQueue()
    queue.clear()
    return queue


def _new_comment(client, datarequest, comment="A comment"):
    return client.call("comment_datarequest", datarequest_id=datarequest["id"], comment=comment)


@pytest.mark.ckan_config("ckan.plugins", "activity datarequests")
@pytest.mark.usefixtures("with_plugins", "datarequest_tables")
class TestNotificationRecipients:

    def test_create_notifies_support(self, scenario, mail_queue):
        scenario.create(scenario.requester)

        assert mail_queue.recipients() == [SUPPORT_EMAIL]

    def test_update_by_someone_else_notifies_support_requester_and_followers(self, scenario, mail_queue):
        datarequest = scenario.create(scenario.requester)
        scenario.follow(datarequest)
        mail_queue.clear()

        scenario.update(scenario.editor, datarequest, status="Processing")

        assert mail_queue.recipients() == sorted([SUPPORT_EMAIL, scenario.requester.user["email"], scenario.follower.user["email"]])

    def test_update_by_requester_notifies_support_and_followers_only(self, scenario, mail_queue):
        datarequest = scenario.create(scenario.requester)
        scenario.follow(datarequest)
        mail_queue.clear()

        scenario.update(scenario.requester, datarequest, description="Purpose, reworded")

        assert mail_queue.recipients() == sorted([SUPPORT_EMAIL, scenario.follower.user["email"]])

    def test_comment_by_someone_else_notifies_support_followers_and_requester(self, scenario, mail_queue):
        datarequest = scenario.create(scenario.requester)
        scenario.follow(datarequest)
        mail_queue.clear()

        _new_comment(scenario.editor, datarequest)

        assert mail_queue.recipients() == sorted([SUPPORT_EMAIL, scenario.requester.user["email"], scenario.follower.user["email"]])

    def test_comment_by_requester_notifies_support_and_followers(self, scenario, mail_queue):
        datarequest = scenario.create(scenario.requester)
        scenario.follow(datarequest)
        mail_queue.clear()

        _new_comment(scenario.requester, datarequest)

        assert mail_queue.recipients() == sorted([SUPPORT_EMAIL, scenario.follower.user["email"]])

    def test_delete_notifies_support_and_followers(self, scenario, mail_queue):
        datarequest = scenario.create(scenario.requester)
        scenario.follow(datarequest)
        mail_queue.clear()

        scenario.requester.call("delete_datarequest", id=datarequest["id"])

        assert mail_queue.recipients() == sorted([SUPPORT_EMAIL, scenario.follower.user["email"]])


@pytest.mark.ckan_config("ckan.plugins", "activity datarequests")
@pytest.mark.ckan_config("ckanext.datarequests.send_notifications", False)
@pytest.mark.usefixtures("with_plugins", "datarequest_tables")
class TestNotificationsSwitchedOff:

    def test_no_event_enqueues_mail(self, scenario, mail_queue):
        datarequest = scenario.create(scenario.requester)
        scenario.follow(datarequest)
        scenario.update(scenario.editor, datarequest, status="Processing")
        _new_comment(scenario.editor, datarequest)
        _new_comment(scenario.requester, datarequest)
        scenario.requester.call("delete_datarequest", id=datarequest["id"])

        assert mail_queue.recipients() == []
