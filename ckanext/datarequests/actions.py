# -*- coding: utf-8 -*-

# Copyright (c) 2015-2016 CoNWeT Lab., Universidad Politécnica de Madrid

# This file is part of CKAN Data Requests Extension.

# CKAN Data Requests Extension is free software: you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# CKAN Data Requests Extension is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with CKAN Data Requests Extension. If not, see <http://www.gnu.org/licenses/>.


import datetime
import logging
try:
    from html import escape
except ImportError:
    from cgi import escape

from ckan import authz, model
from ckan.lib import mailer
from ckan.lib.redis import connect_to_redis
from ckan.plugins import toolkit as tk
from ckan.plugins.toolkit import h, config

from . import common, constants, db, validator


log = logging.getLogger(__name__)

# Avoid user_show lag
USERS_CACHE = {}

# Allow one request per account per five minutes
CREATION_THROTTLE_EXPIRY = 300
THROTTLE_ERROR = "Too many requests submitted, please wait {} minutes and try again"


def _get_user(user_id):
    try:
        if user_id in USERS_CACHE:
            return USERS_CACHE[user_id]
        else:
            user = tk.get_action('user_show')({'ignore_auth': True}, {'id': user_id})
            USERS_CACHE[user_id] = user
            return user
    except Exception as e:
        log.warning(e)


def _get_organization(organization_id):
    try:
        organization_show = tk.get_action('organization_show')
        return organization_show({'ignore_auth': True}, {'id': organization_id, 'include_users': True})
    except Exception as e:
        log.warning(e)


def _get_package(package_id):
    try:
        package_show = tk.get_action('package_show')
        return package_show({'ignore_auth': True}, {'id': package_id})
    except Exception as e:
        log.warning(e)


def _dictize_datarequest(datarequest):
    # Transform time
    open_time = str(datarequest.open_time)
    # Close time can be None and the transformation is only needed when the
    # fields contains a valid date
    close_time = datarequest.close_time
    close_time = str(close_time) if close_time else close_time

    # Convert the data request into a dict
    data_dict = {
        'id': datarequest.id,
        'user_id': datarequest.user_id,
        'title': datarequest.title,
        'description': datarequest.description,
        'organization_id': datarequest.organization_id,
        'open_time': open_time,
        'accepted_dataset_id': datarequest.accepted_dataset_id,
        'close_time': close_time,
        'closed': datarequest.closed,
        'user': _get_user(datarequest.user_id),
        'organization': None,
        'accepted_dataset': None,
        'followers': 0,
        'data_use_type': datarequest.data_use_type,
        'who_will_access_this_data': datarequest.who_will_access_this_data,
        'requesting_organisation': datarequest.requesting_organisation,
        'data_storage_environment': datarequest.data_storage_environment,
        'data_outputs_type': datarequest.data_outputs_type,
        'data_outputs_description': datarequest.data_outputs_description,
        'status': datarequest.status
    }

    if datarequest.organization_id:
        data_dict['organization'] = _get_organization(datarequest.organization_id)

    if datarequest.accepted_dataset_id:
        data_dict['accepted_dataset'] = _get_package(datarequest.accepted_dataset_id)

    data_dict['followers'] = db.DataRequestFollower.get_datarequest_followers_number(
        datarequest_id=datarequest.id)

    if h.closing_circumstances_enabled:
        data_dict['close_circumstance'] = datarequest.close_circumstance
        data_dict['approx_publishing_date'] = datarequest.approx_publishing_date

    return data_dict


def _undictize_datarequest_basic(datarequest, data_dict):
    datarequest.title = data_dict['title']
    datarequest.description = data_dict['description']
    organization = data_dict['organization_id']
    datarequest.organization_id = organization if organization else None
    _undictize_datarequest_closing_circumstances(datarequest, data_dict)

    datarequest.data_use_type = data_dict['data_use_type']
    datarequest.who_will_access_this_data = data_dict['who_will_access_this_data']
    datarequest.requesting_organisation = data_dict['requesting_organisation']
    datarequest.data_storage_environment = data_dict['data_storage_environment']
    datarequest.data_outputs_type = data_dict['data_outputs_type']
    datarequest.data_outputs_description = data_dict['data_outputs_description']
    datarequest.status = data_dict['status']


def _undictize_datarequest_closing_circumstances(datarequest, data_dict):
    if h.closing_circumstances_enabled:
        datarequest.close_circumstance = data_dict.get('close_circumstance') or None
        datarequest.approx_publishing_date = data_dict.get('approx_publishing_date') or None


def _dictize_comment(comment):

    return {
        'id': comment.id,
        'datarequest_id': comment.datarequest_id,
        'user_id': comment.user_id,
        'comment': comment.comment,
        'time': str(comment.time),
        'user': _get_user(comment.user_id)
    }


def _undictize_comment_basic(comment, data_dict):
    comment.comment = escape(data_dict.get('comment', ''))
    comment.datarequest_id = data_dict.get('datarequest_id', '')


def _get_datarequest_involved_users(context, datarequest_dict):

    datarequest_id = datarequest_dict['id']
    new_context = {'ignore_auth': True, 'model': context['model']}

    # Creator + Followers + People who has commented + Organization Staff
    users = set()
    users.add(datarequest_dict['user_id'])
    users.update([follower.user_id for follower in db.DataRequestFollower.get(datarequest_id=datarequest_id)])
    users.update([comment['user_id'] for comment in list_datarequest_comments(new_context, {'datarequest_id': datarequest_id})])

    org = datarequest_dict.get('organization')
    if org:
        users.update(_get_admin_users_from_organisation(org))

    # Notifications are not sent to the user that performs the action
    users.discard(context['auth_user_obj'].id)

    return users


def _send_mail(user_ids, action_type, datarequest, job_title=None):
    for user_id in user_ids:
        try:
            user_data = model.User.get(user_id)
            extra_vars = {
                'datarequest': datarequest,
                'user': user_data,
                'site_title': config.get('ckan.site_title'),
                'site_url': config.get('ckan.site_url')
            }

            subject = tk.render('emails/subjects/{0}.txt'.format(action_type), extra_vars)
            body = tk.render('emails/bodies/{0}.txt'.format(action_type), extra_vars)

            tk.enqueue_job(mailer.mail_user, [user_data, subject, body], title=job_title)
        except Exception:
            log.exception("Error sending notification to {0}".format(user_id))


def _get_admin_users_from_organisation(org_dict):
    all_users = org_dict.get('users', [])
    if common.get_config_bool_value('ckanext.datarequests.notify_all_members', True):
        return {user['id'] for user in all_users}
    else:
        return {user['id'] for user in all_users if user.get('capacity') == 'admin'}


def throttle_datarequest(creator):
    """ Check that the account is not creating requests too quickly.
    This should happen after validation, so a request that fails
    validation can be immediately corrected and resubmitted.
    """
    if creator.sysadmin or authz.has_user_permission_for_some_org(creator.name, 'create_dataset'):
        # privileged users can skip the throttle
        return

    # check cache to see if there's a record of a recent creation
    cache_key = '{}.ckanext.datarequest.creation_attempts.{}'.format(
        tk.config.get('ckan.site_id'), creator.id)
    redis_conn = connect_to_redis()
    try:
        creation_attempts = int(redis_conn.get(cache_key) or 0)
    except ValueError:
        # shouldn't happen but let's play it safe
        creation_attempts = 0

    if creation_attempts:
        # Increase the delay every time someone tries too soon
        expiry = creation_attempts * CREATION_THROTTLE_EXPIRY
    else:
        expiry = CREATION_THROTTLE_EXPIRY
    log.debug("Account %s has submitted %s request(s) recently, next allowed in %s seconds",
              creator.id, creation_attempts, expiry)
    # put a cap on the maximum delay
    recorded_attempts = creation_attempts if creation_attempts >= 100 else creation_attempts + 1
    redis_conn.set(cache_key, recorded_attempts, ex=expiry)
    if creation_attempts:
        raise tk.ValidationError({"": [THROTTLE_ERROR.format(int(expiry / 60))]})


def create_datarequest(context, data_dict):
    '''
    Action to create a new data request. The function checks the access rights
    of the user before creating the data request. If the user is not allowed
    a NotAuthorized exception will be risen.

    In addition, you should note that the parameters will be checked and an
    exception (ValidationError) will be risen if some of these parameters are
    not valid.

    :param title: The title of the data request
    :type title: string

    :param description: A brief description for your data request
    :type description: string

    :param organization_id: The ID of the organization you want to asign the
        data request (optional).
    :type organization_id: string

    :returns: A dict with the data request (id, user_id, title, description,
        organization_id, open_time, accepted_dataset, close_time, closed,
        followers)
    :rtype: dict
    '''

    session = context['session']

    # Check access
    tk.check_access(constants.CREATE_DATAREQUEST, context, data_dict)

    # Validate data
    validator.validate_datarequest(context, data_dict)

    # Ensure account isn't creating requests too fast
    creator = context['auth_user_obj']
    throttle_datarequest(creator)

    # Store the data
    data_req = db.DataRequest()
    _undictize_datarequest_basic(data_req, data_dict)
    data_req.user_id = creator.id
    data_req.open_time = datetime.datetime.utcnow()

    session.add(data_req)
    session.commit()

    datarequest_dict = _dictize_datarequest(data_req)

    org = datarequest_dict.get('organization')
    if org:
        users = _get_admin_users_from_organisation(org)
        users.discard(creator.id)
        _send_mail(users, 'new_datarequest', datarequest_dict, 'Data Request Created Email')

    return datarequest_dict


def show_datarequest(context, data_dict):
    '''
    Action to retrieve the information of a data request. The only required
    parameter is the id of the data request. A NotFound exception will be
    risen if the given id is not found.

    Access rights will be checked before returning the information and an
    exception will be risen (NotAuthorized) if the user is not authorized.

    :param id: The id of the data request to be shown
    :type id: string

    :returns: A dict with the data request (id, user_id, title, description,
        organization_id, open_time, accepted_dataset, close_time, closed,
        followers)
    :rtype: dict
    '''

    datarequest_id = data_dict.get('id', '')

    if not datarequest_id:
        raise tk.ValidationError(tk._('Data Request ID has not been included'))

    # Check access
    tk.check_access(constants.SHOW_DATAREQUEST, context, data_dict)

    # Get the data request
    result = db.DataRequest.get(id=datarequest_id)
    if not result:
        raise tk.ObjectNotFound(tk._('Data Request %s not found in the data base') % datarequest_id)

    data_req = result[0]
    data_dict = _dictize_datarequest(data_req)

    return data_dict


def update_datarequest(context, data_dict):
    '''
    Action to update a data request. The function checks the access rights of
    the user before updating the data request. If the user is not allowed
    a NotAuthorized exception will be risen.

    In addition, you should note that the parameters will be checked and an
    exception (ValidationError) will be risen if some of these parameters are
    invalid.

    :param id: The ID of the data request to be updated
    :type id: string

    :param title: The title of the data request
    :type title: string

    :param description: A brief description for your data request
    :type description: string

    :param organization_id: The ID of the organization you want to asign the
        data request.
    :type organization_id: string

    :returns: A dict with the data request (id, user_id, title, description,
        organization_id, open_time, accepted_dataset, close_time, closed,
        followers)
    :rtype: dict
    '''

    session = context['session']
    datarequest_id = data_dict.get('id', '')

    if not datarequest_id:
        raise tk.ValidationError(tk._('Data Request ID has not been included'))

    # Check access
    tk.check_access(constants.UPDATE_DATAREQUEST, context, data_dict)

    # Get the initial data
    result = db.DataRequest.get(id=datarequest_id)
    if not result:
        raise tk.ObjectNotFound(tk._('Data Request %s not found in the data base') % datarequest_id)

    data_req = result[0]

    # Avoid the validator to return an error when the user does not change the title
    context['avoid_existing_title_check'] = data_req.title == data_dict['title']

    # Validate data
    validator.validate_datarequest(context, data_dict)

    # Determine whether organisation has changed
    organisation_updated = data_req.organization_id != data_dict['organization_id']
    if organisation_updated:
        unassigned_organisation_id = data_req.organization_id

    # Set the data provided by the user in the data_red
    _undictize_datarequest_basic(data_req, data_dict)

    session.add(data_req)
    session.commit()

    datarequest_dict = _dictize_datarequest(data_req)

    if organisation_updated and common.get_config_bool_value('ckanext.datarequests.notify_on_update'):
        org = datarequest_dict['organization']
        # Email Admin users of the assigned organisation
        if org:
            users = _get_admin_users_from_organisation(org)
            users.discard(context['auth_user_obj'].id)
            _send_mail(users, 'new_datarequest_organisation',
                       datarequest_dict, 'Data Request Assigned Email')
        # Email Admin users of unassigned organisation
        users = _get_admin_users_from_organisation(_get_organization(unassigned_organisation_id))
        users.discard(context['auth_user_obj'].id)
        _send_mail(users, 'unassigned_datarequest_organisation',
                   datarequest_dict, 'Data Request Unassigned Email')

    return datarequest_dict


def list_datarequests(context, data_dict):
    '''
    Returns a list with the existing data requests. Rights access will be
    checked before returning the results. If the user is not allowed, a
    NotAuthorized exception will be risen.

    :param organization_id: This parameter is optional and allows users
        to filter the results by organization
    :type organization_id: string

    :param user_id: This parameter is optional and allows users
        to filter the results by user
    :type user_id: string

    :param closed: This parameter is optional and allows users to filter
        the result by the data request status (open or closed)
    :type closed: bool

    :param q: This parameter is optional and allows users to filter
        datarequests based on a free text
    :type q: string

    :param sort: This parameter is optional and allows users to sort
        data requests. You can choose 'desc' for retrieving data requests
        in descending order or 'asc' for retrieving data requests in
        ascending order. Data Requests are returned in ascending order
        by default.
    :type sort: string

    :param offset: The first element to be returned (0 by default)
    :type offset: int

    :param limit: The max number of data requests to be returned (10 by
        default)
    :type limit: int

    :returns: A dict with three fields: result (a list of data requests),
        facets (a list of the facets that can be used) and count (the total
        number of existing data requests)
    :rtype: dict
    '''

    organization_show = tk.get_action('organization_show')
    user_show = tk.get_action('user_show')

    # Check access
    tk.check_access(constants.LIST_DATAREQUESTS, context, data_dict)

    # Get the organization
    organization_id = data_dict.get('organization_id', None)
    if organization_id:
        # Get organization ID (organization name is received sometimes)
        organization_id = organization_show({'ignore_auth': True}, {'id': organization_id}).get('id')

    user_id = data_dict.get('user_id', None)
    if user_id:
        # Get user ID (user name is received sometimes)
        user_id = user_show({'ignore_auth': True}, {'id': user_id}).get('id')

    # Filter by status
    status = data_dict.get('status', None)

    # Free text filter
    q = data_dict.get('q', None)

    # Sort. By default, data requests are returned in the order they are created
    # This is something new in version 0.3.0. In previous versions, requests were
    # returned in inverse order
    desc = False
    if data_dict.get('sort', None) == 'desc':
        desc = True

    # Call the function
    db_datarequests = db.DataRequest.get_ordered_by_date(organization_id=organization_id,
                                                         user_id=user_id, status=status,
                                                         q=q, desc=desc)

    # Dictize the results
    datarequests = []
    offset = data_dict.get('offset', 0)
    limit = data_dict.get('limit', constants.DATAREQUESTS_PER_PAGE)
    for data_req in db_datarequests[offset:offset + limit]:
        datarequests.append(_dictize_datarequest(data_req))

    # Facets
    no_processed_organization_facet = {}
    no_processed_status_facet = {
        'Assigned': 0,
        'Processing': 0,
        'Finalised - Approved': 0,
        'Finalised - Not Approved': 0,
        'Assign to Internal Data Catalogue Support': 0
    }
    for data_req in db_datarequests:
        organization_id = data_req.organization_id
        status = data_req.status

        if organization_id:
            no_processed_organization_facet[organization_id] = no_processed_organization_facet.get(organization_id, 0) + 1

        if status in no_processed_status_facet:
            no_processed_status_facet[status] += 1

    # Format facets
    organization_facet = []
    for organization_id in no_processed_organization_facet:
        try:
            organization = organization_show({'ignore_auth': True}, {'id': organization_id})
            organization_facet.append({
                'name': organization.get('name'),
                'display_name': organization.get('display_name'),
                'count': no_processed_organization_facet[organization_id]
            })
        except Exception:
            pass

    status_facet = []
    for status in no_processed_status_facet:
        if no_processed_status_facet[status]:
            status_facet.append({
                'name': status,
                'display_name': tk._(status),
                'count': no_processed_status_facet[status]
            })

    result = {
        'count': len(db_datarequests),
        'facets': {},
        'result': datarequests
    }

    # Facets can only be included if they contain something
    if organization_facet:
        result['facets']['organization'] = {'items': organization_facet}

    if status_facet:
        result['facets']['status'] = {'items': status_facet}

    return result


def delete_datarequest(context, data_dict):
    '''
    Action to delete a new data request. The function checks the access rights
    of the user before deleting the data request. If the user is not allowed
    a NotAuthorized exception will be risen.

    :param id: The ID of the data request to be deleted
    :type id: string

    :returns: A dict with the data request (id, user_id, title, description,
        organization_id, open_time, accepted_dataset, close_time, closed,
        followers)
    :rtype: dict
    '''

    session = context['session']
    datarequest_id = data_dict.get('id', '')

    # Check id
    if not datarequest_id:
        raise tk.ValidationError(tk._('Data Request ID has not been included'))

    # Check access
    tk.check_access(constants.DELETE_DATAREQUEST, context, data_dict)

    # Get the data request
    result = db.DataRequest.get(id=datarequest_id)
    if not result:
        raise tk.ObjectNotFound(tk._('Data Request %s not found in the data base') % datarequest_id)

    data_req = result[0]
    session.delete(data_req)
    session.commit()

    return _dictize_datarequest(data_req)


def close_datarequest(context, data_dict):
    '''
    Action to close a data request. Access rights will be checked before
    closing the data request. If the user is not allowed, a NotAuthorized
    exception will be risen.

    :param id: The ID of the data request to be closed
    :type id: string

    :param accepted_dataset_id: The ID of the dataset accepted as solution
        for this data request
    :type accepted_dataset_id: string

    :returns: A dict with the data request (id, user_id, title, description,
        organization_id, open_time, accepted_dataset, close_time, closed,
        followers)
    :rtype: dict

    '''

    session = context['session']
    datarequest_id = data_dict.get('id', '')

    # Check id
    if not datarequest_id:
        raise tk.ValidationError(tk._('Data Request ID has not been included'))

    # Check access
    tk.check_access(constants.CLOSE_DATAREQUEST, context, data_dict)

    # Get the data request
    result = db.DataRequest.get(id=datarequest_id)
    if not result:
        raise tk.ObjectNotFound(tk._('Data Request %s not found in the data base') % datarequest_id)

    # Validate data
    validator.validate_datarequest_closing(context, data_dict)

    data_req = result[0]

    # Was the data request previously closed?
    if data_req.closed:
        raise tk.ValidationError([tk._('This Data Request is already closed')])

    data_req.closed = True
    data_req.accepted_dataset_id = data_dict.get('accepted_dataset_id') or None
    data_req.close_time = datetime.datetime.utcnow()
    _undictize_datarequest_closing_circumstances(data_req, data_dict)

    session.add(data_req)
    session.commit()

    datarequest_dict = _dictize_datarequest(data_req)

    # Mailing
    users = _get_datarequest_involved_users(context, datarequest_dict)
    _send_mail(users, 'close_datarequest',
               datarequest_dict, 'Data Request Closed Send Email')

    return datarequest_dict


def comment_datarequest(context, data_dict):
    '''
    Action to create a comment in a data request. Access rights will be checked
    before creating the comment and a NotAuthorized exception will be risen if
    the user is not allowed to create the comment

    :param datarequest_id: The ID of the datarequest to be commented
    :type id: string

    :param comment: The comment to be added to the data request
    :type comment: string

    :returns: A dict with the data request comment (id, user_id, datarequest_id,
       time and comment)
    :rtype: dict

    '''

    session = context['session']
    datarequest_id = data_dict.get('datarequest_id', '')

    # Check id
    if not datarequest_id:
        raise tk.ValidationError([tk._('Data Request ID has not been included')])

    # Check access
    tk.check_access(constants.COMMENT_DATAREQUEST, context, data_dict)

    # Validate comment
    datarequest_dict = validator.validate_comment(context, data_dict)

    # Store the data
    comment = db.Comment()
    _undictize_comment_basic(comment, data_dict)
    comment.user_id = context['auth_user_obj'].id
    comment.time = datetime.datetime.utcnow()

    session.add(comment)
    session.commit()

    # Mailing
    users = _get_datarequest_involved_users(context, datarequest_dict)
    _send_mail(users, 'new_comment', datarequest_dict)

    return _dictize_comment(comment)


def show_datarequest_comment(context, data_dict):
    '''
    Action to retrieve a comment. Access rights will be checked before getting
    the comment and a NotAuthorized exception will be risen if the user is not
    allowed to get the comment

    :param id: The ID of the comment to be retrieved
    :type id: string

    :returns: A dict with the following fields: id, user_id, datarequest_id,
        time and comment
    :rtype: dict
    '''

    comment_id = data_dict.get('id', '')

    # Check id
    if not comment_id:
        raise tk.ValidationError([tk._('Comment ID has not been included')])

    # Check access
    tk.check_access(constants.SHOW_DATAREQUEST_COMMENT, context, data_dict)

    # Get comments
    result = db.Comment.get(id=comment_id)
    if not result:
        raise tk.ObjectNotFound(tk._('Comment %s not found in the data base') % comment_id)

    return _dictize_comment(result[0])


def list_datarequest_comments(context, data_dict):
    '''
    Action to retrieve all the comments of a data request. Access rights will
    be checked before getting the comments and a NotAuthorized exception will
    be risen if the user is not allowed to read the comments

    :param datarequest_id: The ID of the datarequest whose comments want to be
        retrieved
    :type id: string

    :param sort: This parameter is optional and allows users to sort
        comments. You can choose 'desc' for retrieving comments in
        descending order or 'asc' for retrieving comments in ascending
        order. Comments are returned in ascending order by default.
    :type sort: string

    :param sort: The ID of the datarequest whose comments want to be retrieved
    :type sort: string

    :returns: A list with all the comments of a data request. Every comment is
        a dict with the following fields: id, user_id, datarequest_id, time and
        comment
    :rtype: list
    '''

    datarequest_id = data_dict.get('datarequest_id', '')

    # Check id
    if not datarequest_id:
        raise tk.ValidationError(tk._('Data Request ID has not been included'))

    # Sort. By default, comments are returned in the order they are created
    # This is something new in version 0.3.0. In previous versions, comments
    # were returned in inverse order
    desc = False
    if data_dict.get('sort', None) == 'desc':
        desc = True

    # Check access
    tk.check_access(constants.LIST_DATAREQUEST_COMMENTS, context, data_dict)

    # Get comments
    comments_db = db.Comment.get_ordered_by_date(datarequest_id=datarequest_id, desc=desc)

    comments_list = []
    for comment in comments_db:
        comments_list.append(_dictize_comment(comment))

    return comments_list


def update_datarequest_comment(context, data_dict):
    '''
    Action to update a comment of a data request. Access rights will be checked
    before updating the comment and a NotAuthorized exception will be risen if
    the user is not allowed to update the comment

    :param id: The ID of the comment to be updated
    :type id: string

    :param comment: The updated comment
    :type comment: string

    :returns: A dict with the data request comment (id, user_id, datarequest_id,
        time and comment)
    :rtype: dict
    '''

    session = context['session']
    comment_id = data_dict.get('id', '')

    if not comment_id:
        raise tk.ValidationError([tk._('Comment ID has not been included')])

    # Check access
    tk.check_access(constants.UPDATE_DATAREQUEST_COMMENT, context, data_dict)

    # Get the data request
    result = db.Comment.get(id=comment_id)
    if not result:
        raise tk.ObjectNotFound(tk._('Comment %s not found in the data base') % comment_id)

    comment = result[0]

    # Validate data
    validator.validate_comment(context, data_dict)

    # Set the data provided by the user in the data_red
    _undictize_comment_basic(comment, data_dict)

    session.add(comment)
    session.commit()

    return _dictize_comment(comment)


def delete_datarequest_comment(context, data_dict):
    '''
    Action to delete a comment of a data request. Access rights will be checked
    before deleting the comment and a NotAuthorized exception will be risen if
    the user is not allowed to delete the comment

    :param id: The ID of the comment to be deleted
    :type id: string

    :returns: A dict with the data request comment (id, user_id, datarequest_id,
        time and comment)
    :rtype: dict
    '''

    session = context['session']
    comment_id = data_dict.get('id', '')

    if not comment_id:
        raise tk.ValidationError([tk._('Comment ID has not been included')])

    # Check access
    tk.check_access(constants.DELETE_DATAREQUEST_COMMENT, context, data_dict)

    # Get the comment
    result = db.Comment.get(id=comment_id)
    if not result:
        raise tk.ObjectNotFound(tk._('Comment %s not found in the data base') % comment_id)

    comment = result[0]

    session.delete(comment)
    session.commit()

    return _dictize_comment(comment)


def follow_datarequest(context, data_dict):
    '''
    Action to follow a data request. Access rights will be cheked before
    following a datarequest and a NotAuthorized exception will be risen if the
    user is not allowed to follow the given datarequest. ValidationError will
    be risen if the datarequest ID is not included or if the user is already
    following the datarequest. ObjectNotFound will be risen if the given
    datarequest does not exist.

    :param id: The ID of the datarequest to be followed
    :type id: string

    :returns: True
    :rtype: bool
    '''

    session = context['session']
    datarequest_id = data_dict.get('id', '')

    if not datarequest_id:
        raise tk.ValidationError([tk._('Data Request ID has not been included')])

    # Check access
    tk.check_access(constants.FOLLOW_DATAREQUEST, context, data_dict)

    # Get the data request
    result = db.DataRequest.get(id=datarequest_id)
    if not result:
        raise tk.ObjectNotFound(tk._('Data Request %s not found in the data base') % datarequest_id)

    # Is already following?
    user_id = context['auth_user_obj'].id
    result = db.DataRequestFollower.get(datarequest_id=datarequest_id, user_id=user_id)
    if result:
        raise tk.ValidationError([tk._('The user is already following the given Data Request')])

    # Store the data
    follower = db.DataRequestFollower()
    follower.datarequest_id = datarequest_id
    follower.user_id = user_id
    follower.time = datetime.datetime.now()

    session.add(follower)
    session.commit()

    return True


def unfollow_datarequest(context, data_dict):
    '''
    Action to unfollow a data request. Access rights will be cheked before
    unfollowing a datarequest and a NotAuthorized exception will be risen if
    the user is not allowed to unfollow the given datarequest. ValidationError
    will be risen if the datarequest ID is not included in the request.
    ObjectNotFound will be risen if the user is not following the given
    datarequest.

    :param id: The ID of the datarequest to be unfollowed
    :type id: string

    :returns: True
    :rtype: bool
    '''

    session = context['session']
    datarequest_id = data_dict.get('id', '')

    if not datarequest_id:
        raise tk.ValidationError([tk._('Data Request ID has not been included')])

    # Check access
    tk.check_access(constants.UNFOLLOW_DATAREQUEST, context, data_dict)

    # Is already following?
    user_id = context['auth_user_obj'].id
    result = db.DataRequestFollower.get(datarequest_id=datarequest_id, user_id=user_id)
    if not result:
        raise tk.ObjectNotFound([tk._('The user is not following the given Data Request')])

    follower = result[0]

    session.delete(follower)
    session.commit()

    return True


def purge_datarequests(context, data_dict):
    """ Delete all data requests associated with the specified account.
    This is intended for cleanup of spam.
    """
    tk.check_access(constants.PURGE_DATAREQUESTS, context, data_dict)

    datarequests_list = tk.get_action(constants.LIST_DATAREQUESTS)(context, data_dict)
    for target_datarequest in datarequests_list['result']:
        tk.get_action(constants.DELETE_DATAREQUEST)(context, {'id': target_datarequest['id']})

    return True
