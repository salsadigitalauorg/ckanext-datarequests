import ckan.plugins.toolkit as tk
from ckan import authz


def _datarequest(data_dict):
    # Callers often pass only the id.
    if 'user_id' in data_dict and 'organization_id' in data_dict:
        return data_dict
    return tk.get_action('show_datarequest')({'ignore_auth': True}, {'id': data_dict.get('id')})


def _has_owning_organisation_permission(user, datarequest, permission):
    organization_id = datarequest.get('organization_id')
    return bool(organization_id) and authz.has_user_permission_for_group_or_org(organization_id, user.name, permission)


def can_change_status(user, datarequest):
    """Sysadmins, and editors and admins of the Owning Organisation, may change Status."""
    return bool(user) and (user.sysadmin or _has_owning_organisation_permission(user, datarequest, 'update_dataset'))


@tk.chained_auth_function
def show_datarequest(next_auth, context, data_dict):
    """A Data Request is Visible to its requester and to members of the Owning Organisation."""
    user = context.get('auth_user_obj')
    if not user or user.is_anonymous:
        return {'success': False}
    datarequest = _datarequest(data_dict)
    visible = datarequest.get('user_id') == user.id or _has_owning_organisation_permission(user, datarequest, 'read')
    return {'success': visible}


@tk.chained_auth_function
def update_datarequest(next_auth, context, data_dict):
    if next_auth(context, data_dict)['success']:
        return {'success': True}
    return {'success': can_change_status(context.get('auth_user_obj'), _datarequest(data_dict))}


@tk.chained_auth_function
@tk.auth_sysadmins_check
def close_datarequest(next_auth, context, data_dict):
    # Status replaces closing, so nobody closes a Data Request, sysadmins included.
    return {'success': False}
