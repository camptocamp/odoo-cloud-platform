# Copyright 2017-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import re


class SwiftUri(object):

    _url_re = re.compile("^swift:///*([^/]*)/?(.*)",
                         re.IGNORECASE | re.UNICODE)

    def __init__(self, uri):
        match = self._url_re.match(uri)
        if not match:
            raise ValueError("%s: is not a valid Swift URI" % (uri,))
        self._container, self._item = match.groups()

    def container(self):
        return self._container

    def item(self):
        return self._item
