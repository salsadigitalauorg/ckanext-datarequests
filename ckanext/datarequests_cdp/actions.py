import ckan.plugins.toolkit as tk

from . import notifications, validator


def _validated(action, context, data_dict):
    # Authorise first so an unauthorised caller is refused rather than shown field errors.
    tk.check_access(action, context, data_dict)
    validator.validate_datarequest(context, data_dict)
    # Requests for the same dataset share its title, so titles are not unique here.
    context['avoid_existing_title_check'] = True


def _show(datarequest_id):
    return tk.get_action('show_datarequest')({'ignore_auth': True}, {'id': datarequest_id})


@tk.chained_action
def create_datarequest(next_action, context, data_dict):
    _validated('create_datarequest', context, data_dict)
    datarequest = next_action(context, data_dict)
    notifications.created(context, datarequest)
    return datarequest


@tk.chained_action
def update_datarequest(next_action, context, data_dict):
    _validated('update_datarequest', context, data_dict)
    before = _show(data_dict['id'])
    datarequest = next_action(context, data_dict)
    # Saving the form without changing anything is not worth an email.
    if any(before.get(key) != value for key, value in data_dict.items()):
        notifications.updated(context, datarequest)
    return datarequest


@tk.chained_action
def comment_datarequest(next_action, context, data_dict):
    comment = next_action(context, data_dict)
    notifications.commented(context, _show(comment['datarequest_id']), comment)
    return comment


@tk.chained_action
def delete_datarequest(next_action, context, data_dict):
    datarequest = next_action(context, data_dict)
    notifications.deleted(context, datarequest)
    return datarequest
