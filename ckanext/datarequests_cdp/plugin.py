import ckan.plugins as p


class DataRequestsCdpPlugin(p.SingletonPlugin):
    """Internal Data Catalogue behaviour layered over `datarequests`.

    List this plugin before `datarequests` in `ckan.plugins` so its templates
    and chained functions take precedence.
    """
