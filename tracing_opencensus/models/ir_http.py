# -*- coding: utf-8 -*-
# Copyright 2018 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os
import sys

from odoo import api, models
from odoo.http import request

from ..tracer import get_tracer, ignore_paths

from google.rpc import code_pb2

from opencensus.trace import config_integration

from opencensus.trace import attributes_helper
from opencensus.trace import execution_context
from opencensus.trace import stack_trace
from opencensus.trace import status
from opencensus.trace.ext import utils

integration = ['postgresql', 'requests']

config_integration.trace_integrations(integration)

HTTP_METHOD = attributes_helper.COMMON_ATTRIBUTES['HTTP_METHOD']
HTTP_URL = attributes_helper.COMMON_ATTRIBUTES['HTTP_URL']
HTTP_STATUS_CODE = attributes_helper.COMMON_ATTRIBUTES['HTTP_STATUS_CODE']
PID = attributes_helper.COMMON_ATTRIBUTES['PID']

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

    # @api.multi
    # def read(self, fields=None, load='_classic_read'):
    #     if not odoo_jaeger:
    #         return super(Tracing, self).read(fields=fields, load=load)
    #     root_span = get_current_span()
    #     tracer = get_tracer(self.env.cr.dbname)
    #     with tracer.start_span('odoo.models.read', child_of=root_span):
    #         return super(Tracing, self).read(fields=fields, load=load)

    # @api.model
    # def search(self, args, offset=0, limit=None, order=None, count=False):
    #     if not odoo_jaeger:
    #         return super(Tracing, self).search(
    #             args, offset=offset, limit=limit, order=order, count=count
    #         )
    #     root_span = get_current_span()
    #     tracer = get_tracer(self.env.cr.dbname)
    #     with tracer.start_span('odoo.models.search',
    #                            child_of=root_span) as span:
    #         span.set_tag('odoo.model', self._name)
    #         span.set_tag('odoo.domain', args)
    #         return super(Tracing, self).search(
    #             args, offset=offset, limit=limit, order=order, count=count
    #         )

    # @api.model
    # def recompute(self):
    #     if not odoo_jaeger:
    #         return super(Tracing, self).recompute()
    #     root_span = get_current_span()
    #     tracer = get_tracer(self.env.cr.dbname)
    #     with tracer.start_span('odoo.models.recompute',
    #                            child_of=root_span) as span:
    #         span.set_tag('odoo.model', self._name)
    #         span.set_tag('odoo.model.ids', self.ids)
    #         return super(Tracing, self).recompute()


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    _tail_model = True

    @classmethod
    def _dispatch(cls):
        # ignore longpolling requests or other configured paths
        if utils.disable_tracing_url(request.httprequest.url, ignore_paths):
            return super(IrHttp, cls)._dispatch()

        tracer = get_tracer(request.session.db)
        if not tracer:
            return super(IrHttp, cls)._dispatch()

        execution_context.set_opencensus_tracer(tracer)

        with tracer.span('http.dispatch') as span:

            tracer.add_attribute_to_current_span(
                '/odoo/user/id', request.session.uid
            )
            tracer.add_attribute_to_current_span(
                '/odoo/user/login', str(request.session.login)
            )
            tracer.add_attribute_to_current_span(
                '/odoo/db/name', str(request.session.db)
            )
            tracer.add_attribute_to_current_span(
                HTTP_URL, str(request.httprequest.url)
            )
            tracer.add_attribute_to_current_span(
                PID, os.getpid()
            )
            tracer.add_attribute_to_current_span(
                '/odoo/rpc/model', str(request.params.get('model', ''))
            )
            tracer.add_attribute_to_current_span(
                '/odoo/rpc/method', str(request.params.get('method', ''))
            )
            tracer.add_attribute_to_current_span(
                '/odoo/workflow/signal', str(request.params.get('signal', ''))
            )

            try:
                result = super(IrHttp, cls)._dispatch()
            except Exception as err:
                span.status = status.Status(
                    code=code_pb2.UNKNOWN,
                    message=str(err)
                )
                __, __, exc_traceback = sys.exc_info()
                if exc_traceback is not None:
                    span.stack_trace = stack_trace.StackTrace.from_traceback(
                        exc_traceback
                    )
                raise

            code = str(getattr(result, 'status_code', ''))
            tracer.add_attribute_to_current_span(HTTP_STATUS_CODE, code)
        tracer.finish()
        return result
