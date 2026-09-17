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
