# -*- coding: utf-8 -*-

# Copyright (c) 2015 CoNWeT Lab., Universidad Politécnica de Madrid

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

from ckan import authz
from ckan.plugins.toolkit import current_user, h
from ckan.plugins.toolkit import asbool, auth_allow_anonymous_access, config, get_action

from . import constants, db
from .actions import _dictize_datarequest


def create_datarequest(context, data_dict):
    return {
        'success': asbool(config.get("ckanext.auth.create_datarequest_if_not_in_organization", "True"))
        or _is_any_group_member(context)
    }


def _is_any_group_member(context):
    user_name = context.get('user')
    if not user_name:
        user_obj = context.get('auth_user_obj')
        if user_obj:
            user_name = user_obj.name
    return user_name and authz.has_user_permission_for_some_org(user_name, 'read')


@auth_allow_anonymous_access
def show_datarequest(context, data_dict):
    # Sysadmins can see all data requests, other users can only see their own organization's data requests.
    if not current_user.sysadmin:
        result = db.DataRequest.get(id=data_dict.get('id'))
        data_req = result[0]
        data_dict = _dictize_datarequest(data_req)

        current_user_orgs = [org['id'] for org in h.organizations_available('read')] or []
        if data_dict.get('requesting_organisation', None) not in current_user_orgs:
            return {'success': False}

    return {'success': True}


def auth_if_creator(context, data_dict, show_function):
    # Sometimes data_dict only contains the 'id'
    if 'user_id' not in data_dict:
        function = get_action(show_function)
        data_dict = function({'ignore_auth': True}, {'id': data_dict.get('id')})

    return {'success': data_dict['user_id'] == context.get('auth_user_obj').id}


def auth_if_editor_or_admin(context, data_dict, show_function):
    # Sometimes data_dict only contains the 'id'
    if 'user_id' not in data_dict:
        function = get_action(show_function)
        data_dict = function({'ignore_auth': True}, {'id': data_dict.get('id')})

    is_editor_or_admin = False
    current_user_id = current_user.id if current_user else None
    for user in data_dict['organization']['users']:
        if user['id'] == current_user_id and user['capacity'] in ['editor', 'admin']:
            is_editor_or_admin = True
            break

    return {'success': is_editor_or_admin}


def update_datarequest(context, data_dict):
    is_current_creator = auth_if_creator(context, data_dict, constants.SHOW_DATAREQUEST)
    if (is_current_creator['success'] is True):
        return is_current_creator

    return auth_if_editor_or_admin(context, data_dict, constants.SHOW_DATAREQUEST)


@auth_allow_anonymous_access
def list_datarequests(context, data_dict):
    return {'success': True}


def delete_datarequest(context, data_dict):
    return auth_if_creator(context, data_dict, constants.SHOW_DATAREQUEST)


def close_datarequest(context, data_dict):
    return auth_if_creator(context, data_dict, constants.SHOW_DATAREQUEST)


def comment_datarequest(context, data_dict):
    return {'success': True}


@auth_allow_anonymous_access
def list_datarequest_comments(context, data_dict):
    new_data_dict = {'id': data_dict['datarequest_id']}
    return show_datarequest(context, new_data_dict)


@auth_allow_anonymous_access
def show_datarequest_comment(context, data_dict):
    return {'success': True}


def update_datarequest_comment(context, data_dict):
    return auth_if_creator(context, data_dict, constants.SHOW_DATAREQUEST_COMMENT)


def delete_datarequest_comment(context, data_dict):
    return auth_if_creator(context, data_dict, constants.SHOW_DATAREQUEST_COMMENT)


def follow_datarequest(context, data_dict):
    return {'success': True}


def unfollow_datarequest(context, data_dict):
    return {'success': True}


def purge_datarequests(context, data_dict):
    """ Sysadmins only """
    return {'success': False}
