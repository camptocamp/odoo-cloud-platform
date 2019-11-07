# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from openerp import models
from openerp.http import request
from datetime import datetime
from ..statsd_client import statsd, customer, environment
from ..sql_tracker import get_cursor_tracker


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def _dispatch(self):
        if not statsd:
            return super(IrHttp, self)._dispatch()

        path_info = request.httprequest.environ.get('PATH_INFO')
        if path_info.startswith('/longpolling/'):
            return super(IrHttp, self)._dispatch()
        elif path_info.startswith('/web/dataset/call_kw'):
            # remove useless duplicated information
            path_info = '/web/dataset/call_kw'

        params = request.params
        if params.get('method'):
            action = params['method']
        elif params.get('signal'):
            action = params['signal']
        else:
            action = 'undefined'

        parts = [
            path_info.replace('.', '-'),
            customer,
            environment,
            request.params.get('model', 'undefined').replace('.', '_'),
            action
            ]

        def build_name(prefix):
            return '.'.join([prefix] + parts)

        with statsd.pipeline() as pipe:
            start = datetime.now()
            res = super(IrHttp, self)._dispatch()
            duration = datetime.now() - start
            pipe.timing(build_name('http'), duration)
            pipe.timing('request', duration)
            tracker = get_cursor_tracker()
            pipe.timing(build_name('http_sql'), tracker.duration)
            pipe.timing('request_sql', tracker.duration)
            pipe.incr(build_name('http_sql_total'), tracker.count)
            pipe.incr("request_sql_total", tracker.count)
            if tracker.slow_active:
                pipe.timing(build_name('http_sql_slow'), tracker.duration)
                pipe.timing('request_sql_slow', tracker.duration)
                pipe.incr(build_name('http_sql_slow_total'), tracker.count)
                pipe.incr("request_sql_slow_total", tracker.count)
            return res
