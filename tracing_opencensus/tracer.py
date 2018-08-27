# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os

from distutils.util import strtobool

_logger = logging.getLogger(__name__)

try:
    import opencensus
    from opencensus.trace import tracer as tracer_module
    from opencensus.trace.exporters import jaeger_exporter
except ImportError:
    opencensus = execution_context = None  # noqa
    _logger.debug("Cannot 'import opencensus'.")


def is_true(strval):
    return bool(strtobool(strval or '0'.lower()))


SERVICE_PATTERN = 'odoo.%s'
DEFAULT_IGNORE_PATH = '/longpolling'
DEFAULT_JAEGER_AGENT = 'jaeger-agent'
DEFAULT_JAEGER_PORT = jaeger_exporter.DEFAULT_AGENT_PORT  # 6831

use_opencensus = is_true(os.environ.get('ODOO_OPENCENSUS_TRACING'))
ignore_paths = [
    path.strip() for path in
    os.environ.get('ODOO_OPENCENSUS_IGNORE_PATH',
                   DEFAULT_IGNORE_PATH).split(',')
]
jaeger_agent = os.environ.get('ODOO_OPENCENSUS_JAEGER_AGENT',
                              DEFAULT_JAEGER_AGENT)
jaeger_port = os.environ.get('ODOO_OPENCENSUS_JAEGER_PORT',
                             DEFAULT_JAEGER_PORT)


def get_tracer(dbname):
    if not use_opencensus:
        return None
    exporter = jaeger_exporter.JaegerExporter(
        service_name=SERVICE_PATTERN % (dbname,),
        agent_host_name=jaeger_agent,
        agent_port=jaeger_port,
    )
    tracer = tracer_module.Tracer(
        exporter=exporter,
    )
    return tracer
