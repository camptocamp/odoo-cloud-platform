# Copyright 2016-2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from openerp import osv
from openerp.http import request
from prometheus_client import Summary, Counter


REQUEST_TIME = Summary(
    "request_latency_sec", "Request response time in sec", ["query_type"]
)
LONGPOLLING_COUNT = Counter("longpolling", "Longpolling request count")


class IrHttp(osv.osv_abstract):
    _inherit = "ir.http"

    @classmethod
    def _dispatch(cls):
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
