# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from openerp import models
from openerp.http import request
from datetime import datetime
from ..statsd_client import statsd, customer, environment
from ..sql_tracker import get_cursor_tracker

SKIP_PATH = [
    "/connector/runjob",
    "/longpolling/",
    ]


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def _dispatch(self):
        if not statsd:
            return super(IrHttp, self)._dispatch()

        path_info = request.httprequest.environ.get('PATH_INFO')
        for path in SKIP_PATH:
            if path_info.startswith(path):
                return super(IrHttp, self)._dispatch()

        if path_info.startswith('/web/dataset/call_kw'):
            # remove useless duplicated information
            path_info = '/web/dataset/call_kw'

        params = request.params
        if params.get('method'):
            action = params['method']
        elif params.get('signal'):
            action = params['signal']
        else:
            action = 'undefined'

        name = '.'.join([
            path_info.replace('.', '-'),
            customer,
            environment,
            request.params.get('model', 'undefined').replace('.', '_'),
            action
            ])

        with statsd.pipeline() as pipe:
            start = datetime.now()
            res = super(IrHttp, self)._dispatch()
            duration = datetime.now() - start
            pipe.timing('http', duration)
            pipe.timing("http_detail.{}".format(name), duration)
            tracker = get_cursor_tracker()
            tracker.add_metric(pipe, 'http_sql')
            tracker.add_metric(pipe, 'http_sql_detail', name)
            return res
