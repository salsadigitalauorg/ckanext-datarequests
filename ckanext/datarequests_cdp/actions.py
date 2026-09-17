import ckan.plugins.toolkit as tk

from . import validator


def _validated(action, context, data_dict):
    # Authorise first so an unauthorised caller is refused rather than shown field errors.
    tk.check_access(action, context, data_dict)
    validator.validate_datarequest(context, data_dict)
    # Requests for the same dataset share its title, so titles are not unique here.
    context['avoid_existing_title_check'] = True


@tk.chained_action
def create_datarequest(next_action, context, data_dict):
    _validated('create_datarequest', context, data_dict)
    return next_action(context, data_dict)


@tk.chained_action
def update_datarequest(next_action, context, data_dict):
    _validated('update_datarequest', context, data_dict)
    return next_action(context, data_dict)
