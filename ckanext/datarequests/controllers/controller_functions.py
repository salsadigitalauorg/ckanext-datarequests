# encoding: utf-8

import functools
import logging
import re
import six

from six.moves.urllib.parse import urlencode

from ckan import model
from ckan.lib import helpers, captcha
from ckan.plugins import toolkit as tk
from ckan.plugins.toolkit import c, h, request, _, current_user

from ckanext.datarequests import constants, request_helpers

_link = re.compile(r'(?:(https?://)|(www\.))(\S+\b/?)([!"#$%&\'()*+,\-./:;<=>?@[\\\]^_`{|}~]*)(\s|$)', re.I)

log = logging.getLogger(__name__)


def _get_errors_summary(errors):
    errors_summary = {}

    for key, error in errors.items():
        errors_summary[key] = ', '.join(error)

    return errors_summary


def _encode_params(params):
    return [(k, v.encode('utf-8') if isinstance(v, six.string_types) else str(v))
            for k, v in params]


def url_with_params(url, params):
    params = _encode_params(params)
    return url + u'?' + urlencode(params)


def search_url(params):
    url = tk.url_for('datarequest.index')
    return url_with_params(url, params)


def org_datarequest_url(params, id):
    url = tk.url_for('datarequest.organization', id=id)
    return url_with_params(url, params)


def user_datarequest_url(params, id):
    url = tk.url_for('datarequest.user', id=id)
    return url_with_params(url, params)


def _get_context():
    return {'model': model, 'session': model.Session,
            'user': c.user, 'auth_user_obj': c.userobj}


def _show_index(user_id, requesting_organisation, include_organization_facet, url_func, file_to_render, extra_vars=None):
    def pager_url(status=None, sort=None, q=None, page=None):
        params = []

        if q:
            params.append(('q', q))

        if status is not None:
            params.append(('status', status))

        params.append(('sort', sort))
        params.append(('page', page))

        return url_func(params)

    try:
        context = _get_context()
        page = int(request_helpers.get_first_query_param('page', 1))
        limit = constants.DATAREQUESTS_PER_PAGE
        offset = (page - 1) * constants.DATAREQUESTS_PER_PAGE
        data_dict = {'offset': offset, 'limit': limit}

        status = request_helpers.get_first_query_param('status', None)
        if status:
            data_dict['status'] = status

        q = request_helpers.get_first_query_param('q', '')
        if q:
            data_dict['q'] = q

        if requesting_organisation:
            data_dict['requesting_organisation'] = requesting_organisation

        if user_id:
            data_dict['user_id'] = user_id

        sort = request_helpers.get_first_query_param('sort', 'desc')
        sort = sort if sort in ['asc', 'desc'] else 'desc'
        if sort is not None:
            data_dict['sort'] = sort

        tk.check_access(constants.LIST_DATAREQUESTS, context, data_dict)
        datarequests_list = tk.get_action(constants.LIST_DATAREQUESTS)(context, data_dict)

        c.filters = [(tk._('Newest'), 'desc'), (tk._('Oldest'), 'asc')]
        c.sort = sort
        c.q = q
        c.requesting_organisation = requesting_organisation
        c.status = status
        c.datarequest_count = datarequests_list['count']
        c.datarequests = datarequests_list['result']
        c.search_facets = datarequests_list['facets']
        c.page = helpers.Page(
            collection=datarequests_list['result'],
            page=page,
            url=functools.partial(pager_url, status, sort),
            item_count=datarequests_list['count'],
            items_per_page=limit
        )
        c.facet_titles = {
            'status': tk._('Status'),
        }

        # Organization facet cannot be shown when the user is viewing an org
        if include_organization_facet is True:
            c.facet_titles['requesting_organisation'] = tk._('Organizations')

        if not extra_vars:
            extra_vars = {}
        extra_vars['filters'] = c.filters
        extra_vars['sort'] = c.sort
        extra_vars['q'] = c.q
        extra_vars['requesting_organisation'] = c.requesting_organisation
        extra_vars['status'] = c.status
        extra_vars['datarequest_count'] = c.datarequest_count
        extra_vars['datarequests'] = c.datarequests
        extra_vars['search_facets'] = c.search_facets
        extra_vars['page'] = c.page
        extra_vars['facet_titles'] = c.facet_titles
        if 'user' not in extra_vars:
            extra_vars['user'] = None
        if 'user_dict' not in extra_vars:
            extra_vars['user_dict'] = None
        extra_vars['group_type'] = 'requesting_organisation'
        return tk.render(file_to_render, extra_vars=extra_vars)
    except ValueError as e:
        # This exception should only occur if the page value is not valid
        log.warning(e)
        return tk.abort(400, tk._('"page" parameter must be an integer'))
    except tk.NotAuthorized as e:
        log.warning(e)
        return tk.abort(403, tk._('Unauthorized to list Data Requests'))


def index():
    return _show_index(None, request_helpers.get_first_query_param('requesting_organisation', ''), True, search_url,
                       'datarequests/index.html')


def _process_post(action, context):
    # If the user has submitted the form, the data request must be created
    if request_helpers.get_post_params():
        data_dict = {}
        data_dict['title'] = request_helpers.get_first_post_param('title', '')
        data_dict['description'] = request_helpers.get_first_post_param('description', '')
        data_dict['organization_id'] = request_helpers.get_first_post_param('organization_id', '')

        data_dict['data_use_type'] = request_helpers.get_first_post_param('data_use_type', '')
        data_dict['who_will_access_this_data'] = request_helpers.get_first_post_param('who_will_access_this_data', '')
        data_dict['requesting_organisation'] = request_helpers.get_first_post_param('requesting_organisation', '')
        data_dict['data_storage_environment'] = request_helpers.get_first_post_param('data_storage_environment', '')
        data_dict['data_outputs_type'] = request_helpers.get_first_post_param('data_outputs_type', '')
        data_dict['data_outputs_description'] = request_helpers.get_first_post_param('data_outputs_description', '')
        data_dict['status'] = request_helpers.get_first_post_param('status', 'Assigned')
        data_dict['requested_dataset'] = request_helpers.get_first_post_param('requested_dataset', None)

        if action == constants.UPDATE_DATAREQUEST:
            data_dict['id'] = request_helpers.get_first_post_param('id', '')

        try:
            captcha.check_recaptcha(request)
            result = tk.get_action(action)(context, data_dict)
            return tk.redirect_to(tk.url_for('datarequest.show', id=result['id']))

        except tk.ValidationError as e:
            log.warning(e)
            # Fill the fields that will display some information in the page
            c.datarequest = {
                'id': data_dict.get('id', ''),
                'title': data_dict.get('title', ''),
                'description': data_dict.get('description', ''),
                'organization_id': data_dict.get('organization_id', ''),
                'data_use_type': data_dict.get('data_use_type', ''),
                'who_will_access_this_data': data_dict.get('who_will_access_this_data', ''),
                'requesting_organisation': data_dict.get('requesting_organisation', ''),
                'data_storage_environment': data_dict.get('data_storage_environment', ''),
                'data_outputs_type': data_dict.get('data_outputs_type', ''),
                'data_outputs_description': data_dict.get('data_outputs_description', ''),
                'status': data_dict.get('status', ''),
                'requested_dataset': data_dict.get('requested_dataset', '')
            }
            c.errors = e.error_dict
            c.errors_summary = _get_errors_summary(c.errors)
        except captcha.CaptchaError:
            error_msg = _(u'Bad Captcha. Please try again.')
            h.flash_error(error_msg)
            # Fill the fields that will display some information in the page
            c.datarequest = {
                'id': data_dict.get('id', ''),
                'title': data_dict.get('title', ''),
                'description': data_dict.get('description', ''),
                'organization_id': data_dict.get('organization_id', ''),
                'data_use_type': data_dict.get('data_use_type', ''),
                'who_will_access_this_data': data_dict.get('who_will_access_this_data', ''),
                'requesting_organisation': data_dict.get('requesting_organisation', ''),
                'data_storage_environment': data_dict.get('data_storage_environment', ''),
                'data_outputs_type': data_dict.get('data_outputs_type', ''),
                'data_outputs_description': data_dict.get('data_outputs_description', ''),
                'status': data_dict.get('status', ''),
                'requested_dataset': data_dict.get('requested_dataset', '')
            }


def new():
    context = _get_context()

    # Basic initialization
    c.datarequest = {}
    c.errors = {}
    c.errors_summary = {}
    c.requesting_organisation_options = []

    # Check access
    try:
        tk.check_access(constants.CREATE_DATAREQUEST, context, None)
        post_result = _process_post(constants.CREATE_DATAREQUEST, context)

        dataset_id = request.args.get('id')
        if dataset_id:
            dataset = tk.get_action('package_show')(context, {'id': dataset_id})
            c.datarequest['title'] = dataset.get('title', '')
            c.datarequest['requested_dataset'] = dataset.get('id', '')
            c.datarequest['organization_id'] = dataset.get('organization', {}).get('id')

        # Get organizations, with empty value for first option
        organizations = h.organizations_available('read')
        c.requesting_organisation_options = [{'value': '', 'text': ''}] + [{'value': org['id'], 'text': org['name']} for org in organizations]

        return post_result or tk.render('datarequests/new.html')
    except tk.NotAuthorized as e:
        log.warning(e)
        return tk.abort(403, tk._('Unauthorized to create a Data Request'))


def show(id):
    data_dict = {'id': id}
    context = _get_context()

    try:
        tk.check_access(constants.SHOW_DATAREQUEST, context, data_dict)
        c.datarequest = tk.get_action(constants.SHOW_DATAREQUEST)(context, data_dict)

        context_ignore_auth = context.copy()
        context_ignore_auth['ignore_auth'] = True

        return tk.render('datarequests/show.html')
    except tk.ObjectNotFound:
        return tk.abort(404, tk._('Data Request %s not found') % id)
    except tk.NotAuthorized as e:
        log.warning(e)
        return tk.abort(403, tk._('You are not authorized to view the Data Request %s' % id))


def update(id):
    data_dict = {'id': id}
    context = _get_context()

    # Basic initialization
    c.datarequest = {}
    c.errors = {}
    c.errors_summary = {}
    c.requesting_organisation_options = []
    c.access_to_status_field = True if current_user.sysadmin else False

    try:
        tk.check_access(constants.UPDATE_DATAREQUEST, context, data_dict)
        c.datarequest = tk.get_action(constants.SHOW_DATAREQUEST)(context, data_dict)
        c.original_title = c.datarequest.get('title')
        post_result = _process_post(constants.UPDATE_DATAREQUEST, context)

        # Get organizations, with empty value for first option
        organizations = h.organizations_available('read')
        c.requesting_organisation_options = [{'value': '', 'text': ''}] + [{'value': org['id'], 'text': org['name']} for org in organizations]

        current_user_id = current_user.id if current_user else None
        if c.datarequest.get('organization') is not None:
            for user in c.datarequest['organization'].get('users', []):
                if user['id'] == current_user_id and user['capacity'] in ['editor', 'admin']:
                    c.access_to_status_field = True
                    break

        return post_result or tk.render('datarequests/edit.html')
    except tk.ObjectNotFound as e:
        log.warning(e)
        return tk.abort(404, tk._('Data Request %s not found') % id)
    except tk.NotAuthorized as e:
        log.warning(e)
        return tk.abort(403, tk._('You are not authorized to update the Data Request %s' % id))


def delete(id):
    data_dict = {'id': id}
    context = _get_context()

    try:
        tk.check_access(constants.DELETE_DATAREQUEST, context, data_dict)
        datarequest = tk.get_action(constants.DELETE_DATAREQUEST)(context, data_dict)
        h.flash_notice(tk._('Data Request %s has been deleted') % datarequest.get('title', ''))
        return tk.redirect_to(tk.url_for('datarequest.index'))
    except tk.ObjectNotFound as e:
        log.warning(e)
        return tk.abort(404, tk._('Data Request %s not found') % id)
    except tk.NotAuthorized as e:
        log.warning(e)
        return tk.abort(403, tk._('You are not authorized to delete the Data Request %s' % id))


def organization(id):
    context = _get_context()
    c.group_dict = tk.get_action('organization_show')(context, {'id': id})
    url_func = functools.partial(org_datarequest_url, id=id)
    return _show_index(None, id, False, url_func, 'organization/datarequests.html',
                       extra_vars={'group_dict': c.group_dict})


def user(id):
    context = _get_context()
    try:
        c.user_dict = tk.get_action('user_show')(context, {'id': id, 'include_num_followers': True})
    except tk.NotAuthorized:
        tk.abort(403, tk._(u'Not authorized to see this page'))
    url_func = functools.partial(user_datarequest_url, id=id)
    return _show_index(id, request_helpers.get_first_query_param('organization', ''), True, url_func,
                       'user/datarequests.html',
                       extra_vars={'user': c.user_dict, 'user_dict': c.user_dict})


def close(id):
    data_dict = {'id': id}
    context = _get_context()

    # Basic initialization
    c.datarequest = {}

    def _return_page(errors=None, errors_summary=None):
        errors = errors or {}
        errors_summary = errors_summary or {}
        # Get datasets (if the data req belongs to an organization,
        # only the ones that belong to the organization are shown)
        # FIXME: At this time, only the 500 last modified/created datasets are retrieved.
        # We assume that a user will close their data request with a recently added or modified dataset
        # In the future, we should fix this with an autocomplete form...
        search_data_dict = {'rows': 500}
        organization_id = c.datarequest.get('organization_id', '')
        if organization_id:
            log.debug("Loading datasets for organisation %s", organization_id)
            search_data_dict['q'] = 'owner_org:' + organization_id
        else:
            # Expected for CKAN 2.3
            log.debug("Loading first 500 datasets...")
        base_datasets = tk.get_action('package_search')({'ignore_auth': True}, search_data_dict)['results']

        log.debug("Dataset candidates for closing data request: %s", base_datasets)
        c.datasets = []
        c.errors = errors
        c.errors_summary = errors_summary
        for dataset in base_datasets:
            c.datasets.append({'name': dataset.get('name'), 'title': dataset.get('title')})

        if h.closing_circumstances_enabled:
            # This is required so the form can set the currently selected close_circumstance option in the select dropdown
            c.datarequest['close_circumstance'] = request_helpers.get_first_post_param('close_circumstance', None)

        return tk.render('datarequests/close.html')

    try:
        tk.check_access(constants.CLOSE_DATAREQUEST, context, data_dict)
        c.datarequest = tk.get_action(constants.SHOW_DATAREQUEST)(context, data_dict)

        if c.datarequest.get('closed', False):
            return tk.abort(403, tk._('This data request is already closed'))
        elif request_helpers.get_post_params():
            data_dict = {}
            data_dict['accepted_dataset_id'] = request_helpers.get_first_post_param('accepted_dataset_id', None)
            data_dict['id'] = id
            if h.closing_circumstances_enabled:
                data_dict['close_circumstance'] = request_helpers.get_first_post_param('close_circumstance', None)
                data_dict['approx_publishing_date'] = request_helpers.get_first_post_param('approx_publishing_date',
                                                                                           None)
                data_dict['condition'] = request_helpers.get_first_post_param('condition', None)

            tk.get_action(constants.CLOSE_DATAREQUEST)(context, data_dict)
            return tk.redirect_to(tk.url_for('datarequest.show', id=data_dict['id']))
        else:  # GET
            return _return_page()

    except tk.ValidationError as e:  # Accepted Dataset is not valid
        log.warning(e)
        errors_summary = _get_errors_summary(e.error_dict)
        return _return_page(e.error_dict, errors_summary)
    except tk.ObjectNotFound as e:
        log.warning(e)
        return tk.abort(404, tk._('Data Request %s not found') % id)
    except tk.NotAuthorized as e:
        log.warning(e)
        return tk.abort(403, tk._('You are not authorized to close the Data Request %s' % id))


def comment(id):
    try:
        context = _get_context()
        data_dict_comment_list = {'datarequest_id': id}
        data_dict_dr_show = {'id': id}
        tk.check_access(constants.LIST_DATAREQUEST_COMMENTS, context, data_dict_comment_list)

        # Raises 404 Not Found if the data request does not exist
        c.datarequest = tk.get_action(constants.SHOW_DATAREQUEST)(context, data_dict_dr_show)

        comment_text = request_helpers.get_first_post_param('comment', '')
        comment_id = request_helpers.get_first_post_param('comment-id', '')
        updated_comment = None

        if request_helpers.get_post_params():
            action = constants.COMMENT_DATAREQUEST
            action_text = 'comment'

            if comment_id:
                action = constants.UPDATE_DATAREQUEST_COMMENT
                action_text = 'update comment'

            try:
                comment_data_dict = {'datarequest_id': id, 'comment': comment_text, 'id': comment_id}
                updated_comment = tk.get_action(action)(context, comment_data_dict)

                if not comment_id:
                    flash_message = tk._('Comment has been published')
                else:
                    flash_message = tk._('Comment has been updated')

                h.flash_notice(flash_message)

            except tk.NotAuthorized as e:
                log.warning(e)
                return tk.abort(403, tk._('You are not authorized to %s' % action_text))
            except tk.ValidationError as e:
                log.warning(e)
                c.errors = e.error_dict
                c.errors_summary = _get_errors_summary(c.errors)
            except tk.ObjectNotFound as e:
                log.warning(e)
                return tk.abort(404, tk._(str(e)))
            # Other exceptions are not expected. Otherwise, the request will fail.

            # This is required to scroll the user to the appropriate comment
            if not updated_comment:
                updated_comment = {
                    'id': comment_id,
                    'comment': comment_text
                }

        c.updated_comment = {
            'comment': updated_comment
        }
        # Comments should be retrieved once that the comment has been created
        get_comments_data_dict = {'datarequest_id': id}
        c.comments = tk.get_action(constants.LIST_DATAREQUEST_COMMENTS)(context, get_comments_data_dict)

        return tk.render('datarequests/comment.html')

    except tk.ObjectNotFound as e:
        log.warning(e)
        return tk.abort(404, tk._('Data Request %s not found' % id))

    except tk.NotAuthorized as e:
        log.warning(e)
        return tk.abort(403, tk._('You are not authorized to list the comments of the Data Request %s' % id))


def delete_comment(datarequest_id, comment_id):
    try:
        context = _get_context()
        data_dict = {'id': comment_id}
        tk.check_access(constants.DELETE_DATAREQUEST_COMMENT, context, data_dict)
        tk.get_action(constants.DELETE_DATAREQUEST_COMMENT)(context, data_dict)
        h.flash_notice(tk._('Comment has been deleted'))
        return tk.redirect_to(tk.url_for('datarequest.comment', id=datarequest_id))
    except tk.ObjectNotFound as e:
        log.warning(e)
        return tk.abort(404, tk._('Comment %s not found') % comment_id)
    except tk.NotAuthorized as e:
        log.warning(e)
        return tk.abort(403, tk._('You are not authorized to delete this comment'))


def follow(id):
    # Method is not called
    pass


def unfollow(id):
    # Method is not called
    pass


def purge(user_id):
    """ Delete all data requests associated with the specified account.
    This is intended for cleanup of spam.
    """
    data_dict = {'user_id': user_id}
    context = _get_context()

    post_params = request_helpers.get_post_params()
    if post_params:
        if 'cancel' in post_params:
            return tk.redirect_to('datarequest.index')

        try:
            tk.get_action(constants.PURGE_DATAREQUESTS)(context, data_dict)
            h.flash_notice(tk._('Deleted data request(s) for user'))
            return tk.redirect_to('datarequest.index')
        except tk.ObjectNotFound as e:
            log.warning(e)
            return tk.abort(404, tk._('User %s not found') % user_id)
    else:
        return tk.render('datarequests/confirm_delete_all.html', extra_vars={'user_id': user_id})
