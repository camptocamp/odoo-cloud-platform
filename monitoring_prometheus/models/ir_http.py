# -*- coding: utf-8 -*-
# Copyright 2016-2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
from __future__ import with_statement
from __future__ import absolute_import
import logging

from openerp import models
from openerp.http import request

_logger = logging.getLogger(__name__)

try:
    from prometheus_client import Summary, Counter
except (ImportError, IOError), err:
    _logger.warning(err)


REQUEST_TIME = Summary(
    "request_latency_sec", "Request response time in sec", ["query_type"]
)
LONGPOLLING_COUNT = Counter("longpolling", "Longpolling request count")


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def _dispatch(self):
        path_info = request.httprequest.environ.get("PATH_INFO")

        if path_info.startswith("/longpolling/"):
            LONGPOLLING_COUNT.inc()
            return super(IrHttp, self)._dispatch()

        if path_info.startswith("/metrics"):
            return super(IrHttp, self)._dispatch()

        if path_info.startswith("/web/static"):
            label = "assets"
        elif path_info.startswith("/web/content"):
            label = "filestore"
        else:
            label = "client"

        res = None
        with REQUEST_TIME.labels(label).time():
            res = super(IrHttp, self)._dispatch()

        return res
