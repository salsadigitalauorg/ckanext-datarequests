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

import datetime

import ckan.plugins.toolkit as tk
from ckanext.datarequests import common, constants, helpers


def profanity_check_enabled():
    return tk.asbool(tk.config.get('ckan.comments.check_for_profanity', False))


def _add_error(errors, field_name, message):
    if field_name in errors:
        errors[field_name].append(message)
    else:
        errors[field_name] = [message]


def _has_alpha_chars(string, min_alpha_chars):
    alpha_chars = sum(1 for char in string if char.isalpha())
    return alpha_chars >= min_alpha_chars


def validate_datarequest(context, request_data):
    errors = {}

    default_title = ''
    default_org_id = ''

    ###################################
    # Validating hidden fields
    ###################################

    # Validate requested_dataset
    requested_dataset = request_data.get('requested_dataset', None)
    requested_dataset_field = tk._('Requested dataset')
    if not requested_dataset:
        _add_error(errors, requested_dataset_field, tk._('Requested dataset cannot be empty'))
    else:
        try:
            package = tk.get_action('package_show')(context, {'id': requested_dataset})
            default_title = package['title']
            default_org_id = package['organization']['id']
        except Exception:
            _add_error(errors, requested_dataset_field, tk._('Requested dataset not found'))

    # Check organization
    organization_id = request_data.get('organization_id', default_org_id)
    request_data['organization_id'] = organization_id
    organization_field = tk._('Organization')
    if not organization_id:
        _add_error(errors, organization_field, tk._('Organization cannot be empty'))

    if organization_id:
        try:
            tk.get_validator('group_id_exists')(request_data['organization_id'], context)
        except Exception:
            _add_error(errors, organization_field, tk._('Organization is not valid'))

    ###################################
    # Validating visible fields
    ###################################

    # Check name
    title = request_data.get('title', default_title)
    request_data['title'] = title
    title_field = tk._('Title')

    if len(title) > constants.NAME_MAX_LENGTH:
        _add_error(errors, title_field, tk._('Title must be a maximum of %d characters long') % constants.NAME_MAX_LENGTH)

    if not title:
        _add_error(errors, title_field, tk._('Title cannot be empty'))

    # Check description
    description = request_data.get('description', '')
    description_field = tk._('Purpose of data use')
    if not description:
        _add_error(errors, description_field, tk._('Purpose of data use cannot be empty'))

    if len(description) > constants.DESCRIPTION_MAX_LENGTH:
        _add_error(errors, description_field, tk._('Purpose of data use must be a maximum of %d characters long') % constants.DESCRIPTION_MAX_LENGTH)

    if description and not _has_alpha_chars(description, 2):
        _add_error(errors, description_field, tk._('Purpose of data use need to be longer than two characters and alphabetical'))

    # Run profanity check
    if profanity_check_enabled():
        if common.profanity_check(title):
            _add_error(errors, title_field, tk._("Blocked due to profanity"))
        if description_field not in errors and common.profanity_check(description):
            _add_error(errors, description_field, tk._("Blocked due to profanity"))

    # Check data_use_type data, it should not be empty.
    data_use_type = request_data.get('data_use_type', '')
    data_use_type_field = tk._('Data use type')
    if not data_use_type:
        _add_error(errors, data_use_type_field, tk._('Data use type cannot be empty'))

    # Check who_will_access_this_data, it should not be empty.
    who_will_access_this_data = request_data.get('who_will_access_this_data', '')
    who_will_access_this_data_field = tk._('Who will access this data')
    if not who_will_access_this_data:
        _add_error(errors, who_will_access_this_data_field, tk._('Who will access this data cannot be empty'))

    if who_will_access_this_data and not _has_alpha_chars(who_will_access_this_data, 2):
        _add_error(errors, who_will_access_this_data_field, tk._('Who will access this data need to be longer than two characters and alphabetical'))

    # Check requesting_organisation, it should not be empty.
    requesting_organisation = request_data.get('requesting_organisation', '')
    requesting_organisation_field = tk._('Requesting organisation')
    if not requesting_organisation:
        _add_error(errors, requesting_organisation_field, tk._('Requesting organisation cannot be empty'))

    # Check requesting_organisation is a valid organisation in database.
    if requesting_organisation:
        try:
            tk.get_validator('group_id_exists')(requesting_organisation, context)
        except Exception:
            _add_error(errors, requesting_organisation_field, tk._('Requesting organisation is not valid'))

    # Check data_storage_environment, it should not be empty.
    data_storage_environment = request_data.get('data_storage_environment', '')
    data_storage_environment_field = tk._('Data storage environment')
    if not data_storage_environment:
        _add_error(errors, data_storage_environment_field, tk._('Data storage environment cannot be empty'))

    if data_storage_environment and not _has_alpha_chars(data_storage_environment, 2):
        _add_error(errors, data_storage_environment_field, tk._('Data storage environment need to be longer than two characters and alphabetical'))

    # Check data_outputs_type, it should not be empty.
    data_outputs_type = request_data.get('data_outputs_type', '')
    data_outputs_type_field = tk._('Data outputs type')
    if not data_outputs_type:
        _add_error(errors, data_outputs_type_field, tk._('Data outputs type cannot be empty'))

    # Check data_outputs_description, it should be empty.
    data_outputs_description = request_data.get('data_outputs_description', '')
    data_outputs_description_field = tk._('Data outputs description')
    if not data_outputs_description:
        _add_error(errors, data_outputs_description_field, tk._('Data outputs description cannot be empty'))

    if data_outputs_description and not _has_alpha_chars(data_outputs_description, 2):
        _add_error(errors, data_outputs_description_field, tk._('Data outputs description need to be longer than two characters and alphabetical'))

    # Check status, it should not be empty and have valid value.
    valid_statuses = helpers.get_status_list()
    status = request_data.get('status', 'Assigned')
    request_data['status'] = status
    status_field = tk._('Status')
    if not status:
        _add_error(errors, status_field, tk._('Status cannot be empty'))

    if status not in [status['value'] for status in valid_statuses]:
        _add_error(errors, status_field, tk._('Status value is not valid'))

    if len(errors) > 0:
        raise tk.ValidationError(errors)


def validate_datarequest_closing(context, request_data):
    if tk.h.closing_circumstances_enabled:
        close_circumstance = request_data.get('close_circumstance', None)
        if not close_circumstance:
            raise tk.ValidationError({tk._('Circumstances'): [tk._('Circumstances cannot be empty')]})
        condition = request_data.get('condition', None)
        if condition:
            if condition == 'nominate_dataset' and request_data.get('accepted_dataset_id', '') == '':
                raise tk.ValidationError({tk._('Accepted dataset'): [tk._('Accepted dataset cannot be empty')]})
            elif condition == 'nominate_approximate_date':
                if request_data.get('approx_publishing_date', '') == '':
                    raise tk.ValidationError({tk._('Approximate publishing date'): [tk._('Approximate publishing date cannot be empty')]})
                try:
                    # This validation is required for the Safari browser as the date type input is not supported and falls back to using a text type input
                    # SQLAlchemy throws an error if the date value is not in the format yyyy-mm-dd
                    datetime.datetime.strptime(request_data.get('approx_publishing_date', ''), '%Y-%m-%d')
                except ValueError:
                    raise tk.ValidationError({tk._('Approximate publishing date'): [tk._('Approximate publishing date must be in format yyyy-mm-dd')]})

    accepted_dataset_id = request_data.get('accepted_dataset_id', '')
    if accepted_dataset_id:
        try:
            tk.get_validator('package_name_exists')(accepted_dataset_id, context)
        except Exception:
            raise tk.ValidationError({tk._('Accepted Dataset'): [tk._('Dataset not found')]})


def validate_comment(context, request_data):
    comment = request_data.get('comment', '')

    # Check if the data request exists
    try:
        datarequest = tk.get_action(constants.SHOW_DATAREQUEST)(context, {'id': request_data['datarequest_id']})
    except Exception:
        raise tk.ValidationError({tk._('Data Request'): [tk._('Data Request not found')]})

    errors = {}
    comment_field = tk._('Comment')
    if not comment or len(comment) <= 0:
        _add_error(errors, comment_field, tk._('Comments must be a minimum of 1 character long'))

    if len(comment) > constants.COMMENT_MAX_LENGTH:
        _add_error(errors, comment_field, tk._('Comments must be a maximum of %d characters long') % constants.COMMENT_MAX_LENGTH)

    if profanity_check_enabled() and common.profanity_check(comment):
        _add_error(errors, comment_field, tk._("Comment blocked due to profanity."))

    if errors:
        raise tk.ValidationError(errors)

    return datarequest
