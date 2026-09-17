import ckan.plugins as p
import ckan.plugins.toolkit as tk

from . import actions, auth, helpers


class DataRequestsCdpPlugin(p.SingletonPlugin):
    """Internal Data Catalogue behaviour layered over `datarequests`.

    List this plugin before `datarequests` in `ckan.plugins` so its templates
    and chained functions take precedence.
    """

    p.implements(p.IActions)
    p.implements(p.IAuthFunctions)
    p.implements(p.IConfigurer)
    p.implements(p.ITemplateHelpers)

    def update_config(self, config):
        tk.add_template_directory(config, 'templates')

    def get_actions(self):
        chained = {
            'create_datarequest': actions.create_datarequest,
            'update_datarequest': actions.update_datarequest,
            'delete_datarequest': actions.delete_datarequest,
        }
        # datarequests only registers the comment action when comments are on.
        if tk.asbool(tk.config.get('ckan.datarequests.comments', True)):
            chained['comment_datarequest'] = actions.comment_datarequest
        return chained

    def get_auth_functions(self):
        return {
            'show_datarequest': auth.show_datarequest,
            'update_datarequest': auth.update_datarequest,
            'delete_datarequest': auth.delete_datarequest,
            'close_datarequest': auth.close_datarequest,
        }

    def get_helpers(self):
        return {
            'get_status_list': helpers.get_status_list,
            'get_status_label': helpers.get_status_label,
            'datarequest_requesting_organisation_options': helpers.requesting_organisation_options,
            'datarequest_can_edit_status': helpers.can_edit_status,
            'datarequest_prefilled_from_dataset': helpers.prefilled_from_dataset,
        }
