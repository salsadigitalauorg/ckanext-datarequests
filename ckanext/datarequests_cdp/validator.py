import ckan.plugins.toolkit as tk

from ckanext.datarequests import common, constants
from ckanext.datarequests.validator import profanity_check_enabled

from . import helpers


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
    valid_statuses = helpers.STATUS_LIST
    status = request_data.get('status', 'Assigned')
    request_data['status'] = status
    status_field = tk._('Status')
    if not status:
        _add_error(errors, status_field, tk._('Status cannot be empty'))

    if status not in [status['value'] for status in valid_statuses]:
        _add_error(errors, status_field, tk._('Status value is not valid'))

    if errors:
        raise tk.ValidationError(errors)
