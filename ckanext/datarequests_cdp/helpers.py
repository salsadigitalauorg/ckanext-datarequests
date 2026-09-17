import ckan.plugins.toolkit as tk

STATUS_LIST = [
    {'value': 'Assigned', 'text': 'Assigned', 'label_class': 'open'},
    {'value': 'Processing', 'text': 'Processing', 'label_class': 'open'},
    {'value': 'Finalised - Approved', 'text': 'Finalised - Approved', 'label_class': 'closed'},
    {'value': 'Finalised - Not Approved', 'text': 'Finalised - Not Approved', 'label_class': 'closed'},
    {'value': 'Assign to Internal Data Catalogue Support', 'text': 'Assign to Internal Data Catalogue Support', 'label_class': 'open'},
]


def get_status_list():
    return STATUS_LIST


def get_status_label(status):
    """The list entry for `status`; an unknown or missing Status reads as Assigned."""
    return next((item for item in STATUS_LIST if item['value'] == status), STATUS_LIST[0])


def requesting_organisation_options():
    """Select options for Requesting Organisation: the organisations the user belongs to."""
    organizations = tk.h.organizations_available('read')
    return [{'value': '', 'text': ''}] + [{'value': org['id'], 'text': org['name']} for org in organizations]


def can_edit_status(datarequest_id):
    """Whether the current user may change Status: sysadmins, and editors and admins of the Owning Organisation."""
    if tk.current_user.sysadmin:
        return True
    datarequest = tk.get_action('show_datarequest')({}, {'id': datarequest_id})
    users = (datarequest.get('organization') or {}).get('users', [])
    return any(user['id'] == tk.current_user.id and user['capacity'] in ('editor', 'admin') for user in users)


def prefilled_from_dataset(datarequest):
    """`datarequest` with title, dataset and Owning Organisation taken from the dataset named by `?id=`."""
    dataset_id = tk.request.args.get('id')
    if not dataset_id:
        return datarequest
    dataset = tk.get_action('package_show')({}, {'id': dataset_id})
    return dict(
        datarequest,
        title=dataset.get('title', ''),
        requested_dataset=dataset.get('id', ''),
        organization_id=(dataset.get('organization') or {}).get('id'),
    )
