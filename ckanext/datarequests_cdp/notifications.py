"""Who is emailed for each Data Request event. One function per event."""
import logging

import ckan.plugins.toolkit as tk
from ckan import model
from ckan.lib import mailer

from ckanext.datarequests import db

log = logging.getLogger(__name__)


def _support():
    return [{
        'email': tk.config.get('ckanext.datarequests.internal_data_catalogue_support_team_email'),
        'name': tk.config.get('ckanext.datarequests.internal_data_catalogue_support_team_name'),
    }]


def _user(user_id):
    user = model.User.get(user_id)
    return [{'email': user.email, 'name': user.name}] if user and user.email else []


def _requester(datarequest):
    return _user(datarequest['user_id'])


def _followers(context, datarequest):
    """Followers other than the person acting."""
    follower_ids = [follower.user_id for follower in db.DataRequestFollower.get(datarequest_id=datarequest['id'])]
    acting_user_id = context['auth_user_obj'].id
    return [recipient for user_id in follower_ids if user_id != acting_user_id for recipient in _user(user_id)]


def _dataset_point_of_contact(datarequest):
    try:
        dataset = tk.get_action('package_show')({'ignore_auth': True}, {'id': datarequest.get('requested_dataset')})
    except (tk.ObjectNotFound, tk.ValidationError):
        return []
    if not dataset.get('point_of_contact_email'):
        return []
    return [{'email': dataset['point_of_contact_email'], 'name': dataset.get('point_of_contact')}]


def _send(template, recipients, datarequest, job_title, comment=None):
    if not tk.asbool(tk.config.get('ckanext.datarequests.send_notifications', True)):
        return

    requesting_organisation = model.Group.get(datarequest.get('requesting_organisation'))
    if requesting_organisation:
        datarequest = dict(datarequest, requesting_organisation_dict={'name': requesting_organisation.name})

    for recipient in recipients:
        try:
            extra_vars = {
                'datarequest': datarequest,
                'comment': comment,
                'user': recipient,
                'site_title': tk.config.get('ckan.site_title'),
                'site_url': tk.config.get('ckan.site_url'),
            }
            subject = tk.render('emails/subjects/{0}.txt'.format(template), extra_vars)
            body = tk.render('emails/bodies/{0}.txt'.format(template), extra_vars)
            tk.enqueue_job(mailer.mail_recipient, [recipient['name'], recipient['email'], subject, body], title=job_title)
        except Exception:
            log.exception("Error sending notification to %s", recipient['email'])


def created(context, datarequest):
    recipients = _support() + _dataset_point_of_contact(datarequest)
    _send('new_datarequest', recipients, datarequest, 'Data Request Created Email')


def updated(context, datarequest):
    recipients = _support()
    if context['auth_user_obj'].id != datarequest['user_id']:
        recipients += _requester(datarequest)
    _send('update_datarequest', recipients, datarequest, 'Data Request Status Change Email')
    _send('update_datarequest_follower', _followers(context, datarequest), datarequest, 'Data Request Updated Email')


def commented(context, datarequest, comment):
    recipients = _support() + _followers(context, datarequest)
    if comment['user_id'] == datarequest['user_id']:
        recipients += _dataset_point_of_contact(datarequest)
    else:
        recipients += _requester(datarequest)
    _send('comment_datarequest', recipients, datarequest, 'Data Request Comment Email', comment)


def deleted(context, datarequest):
    recipients = _support() + _followers(context, datarequest)
    _send('delete_datarequest', recipients, datarequest, 'Data Request Deletion Email')
