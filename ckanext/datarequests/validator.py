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
from ckanext.datarequests import db, common, constants


def profanity_check_enabled():
    return tk.asbool(tk.config.get('ckan.comments.check_for_profanity', False))


def _add_error(errors, field_name, message):
    if field_name in errors:
        errors[field_name].append(message)
    else:
        errors[field_name] = [message]


def validate_datarequest(context, request_data):

    errors = {}

    # Check name
    title = request_data['title']
    title_field = tk._('Title')
    if len(title) > constants.NAME_MAX_LENGTH:
        _add_error(errors, title_field, tk._('Title must be a maximum of %d characters long') % constants.NAME_MAX_LENGTH)

    if not title:
        _add_error(errors, title_field, tk._('Title cannot be empty'))

    # Title is only checked in the database when it's correct
    avoid_existing_title_check = context['avoid_existing_title_check'] if 'avoid_existing_title_check' in context else False

    if title_field not in errors and not avoid_existing_title_check:
        if db.DataRequest.datarequest_exists(title):
            _add_error(errors, title_field, tk._('That title is already in use'))

    # Check description
    description = request_data['description']
    description_field = tk._('Description')
    if common.get_config_bool_value('ckan.datarequests.description_required', False) and not description:
        _add_error(errors, description_field, tk._('Description cannot be empty'))

    if len(description) > constants.DESCRIPTION_MAX_LENGTH:
        _add_error(errors, description_field, tk._('Description must be a maximum of %d characters long') % constants.DESCRIPTION_MAX_LENGTH)

    # Run profanity check
    if profanity_check_enabled():
        if common.profanity_check(title):
            _add_error(errors, title_field, tk._("Blocked due to profanity"))
        if description_field not in errors and common.profanity_check(description):
            _add_error(errors, description_field, tk._("Blocked due to profanity"))

    # Check organization
    if request_data['organization_id']:
        try:
            tk.get_validator('group_id_exists')(request_data['organization_id'], context)
        except Exception:
            _add_error(errors, tk._('Organization'), tk._('Organization is not valid'))

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
