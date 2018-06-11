# -*- coding: utf-8 -*-
# Copyright 2018 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
from odoo import api, models
from odoo.http import request

from ..http import odoo_jaeger, get_tracer, init_tracer
from opentracing_instrumentation.request_context import (
    get_current_span, span_in_context
)

_logger = logging.getLogger(__name__)


# TODO extract in an addon, use in monitoring_statsd too
class BaseModel(models.AbstractModel):
    _inherit = 'base'

    @classmethod
    def _build_model_attributes(cls, pool):
        # ensure that an _inherit of the model is always at the end of the mro,
        # so we trace everything happening above
        bases = []
        tail = []
        for base in cls.__bases__:
            tail_base = getattr(base, '_tail_model', False)
            tail.append(base) if tail_base else bases.append(base)

            cls.__bases__ = tuple(tail + bases)

        super(BaseModel, cls)._build_model_attributes(pool)


# TODO find way to automatically add to all models (first in mro)
class Tracing(models.AbstractModel):
    _name = 'jaeger.model.tracing'
    # _tracing_model = True
    _tail_model = True

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        if not odoo_jaeger:
            return super(Tracing, self).read(fields=fields, load=load)
        root_span = get_current_span()
        tracer = get_tracer(self.env.cr.dbname)
        with tracer.start_span('odoo.models.read', child_of=root_span):
            return super(Tracing, self).read(fields=fields, load=load)

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        if not odoo_jaeger:
            return super(Tracing, self).search(
                args, offset=offset, limit=limit, order=order, count=count
            )
        root_span = get_current_span()
        tracer = get_tracer(self.env.cr.dbname)
        with tracer.start_span('odoo.models.search',
                               child_of=root_span) as span:
            span.set_tag('odoo.model', self._name)
            span.set_tag('odoo.domain', args)
            return super(Tracing, self).search(
                args, offset=offset, limit=limit, order=order, count=count
            )

    @api.model
    def recompute(self):
        if not odoo_jaeger:
            return super(Tracing, self).recompute()
        root_span = get_current_span()
        tracer = get_tracer(self.env.cr.dbname)
        with tracer.start_span('odoo.models.recompute',
                               child_of=root_span) as span:
            span.set_tag('odoo.model', self._name)
            span.set_tag('odoo.model.ids', self.ids)
            return super(Tracing, self).recompute()


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    _tail_model = True

    @api.model_cr
    def _register_hook(self):
        super(IrHttp, self)._register_hook()
        if odoo_jaeger:
            init_tracer(self.env.cr.dbname)

    @classmethod
    def _dispatch(cls):
        tracer = get_tracer(request.session.db)
        if not tracer:
            return super(IrHttp, cls)._dispatch()

        path_info = request.httprequest.environ.get('PATH_INFO')
        # ignore longpolling requests
        if path_info.startswith('/longpolling/'):
            return super(IrHttp, cls)._dispatch()

        _logger.error('tracer: %r', tracer)
        with tracer.start_span('ir.http._dispatch') as span:
            # TODO use set_tags
            span.set_tag('odoo.user.id', request.session.uid)
            span.set_tag('odoo.path.info', path_info)
            span.set_tag(
                'odoo.rpc.model', request.params.get('model', '')
            )
            span.set_tag(
                'odoo.rpc.method', request.params.get('method', '')
            )
            span.set_tag(
                'odoo.workflow.signal', request.params.get('signal', '')
            )

            with span_in_context(span):
                return super(IrHttp, cls)._dispatch()
