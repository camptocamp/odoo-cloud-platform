# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from openerp import models
from openerp.http import request

from ..statsd_client import statsd, customer, environment


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def _dispatch(self):
        if not statsd:
            return super(IrHttp, self)._dispatch()

        path_info = request.httprequest.environ.get('PATH_INFO')
        if path_info.startswith('/longpolling/'):
            return super(IrHttp, self)._dispatch()

        parts = ['http', ]
        if path_info.startswith('/web/dataset/call_button'):
            parts += ['button',
                      customer, environment,
                      request.params['model'].replace('.', '_'),
                      request.params['method'],
                      ]
        elif path_info.startswith('/web/dataset/exec_workflow'):
            parts += ['workflow',
                      customer, environment,
                      request.params['model'].replace('.', '_'),
                      request.params['signal'],
                      ]
        else:
            parts += ['request',
                      customer, environment,
                      ]

        with statsd.timer('.'.join(parts)):
            return super(IrHttp, self)._dispatch()
