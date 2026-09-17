import ckan.plugins as p
import ckan.plugins.toolkit as tk

from . import helpers


class DataRequestsCdpPlugin(p.SingletonPlugin):
    """Internal Data Catalogue behaviour layered over `datarequests`.

    List this plugin before `datarequests` in `ckan.plugins` so its templates
    and chained functions take precedence.
    """

    p.implements(p.IConfigurer)
    p.implements(p.ITemplateHelpers)

    def update_config(self, config):
        tk.add_template_directory(config, 'templates')

    def get_helpers(self):
        return {
            'get_status_list': helpers.get_status_list,
            'get_status_label': helpers.get_status_label,
        }
