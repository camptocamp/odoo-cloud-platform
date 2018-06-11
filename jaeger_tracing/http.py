# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os

from distutils.util import strtobool

_logger = logging.getLogger(__name__)

try:
    import jaeger_client
    from opentracing_instrumentation.client_hooks import install_all_patches
except ImportError:
    jaeger_client = None  # noqa
    _logger.debug("Cannot 'import jaeger_client'.")


def is_true(strval):
    return bool(strtobool(strval or '0'.lower()))


odoo_jaeger = is_true(os.environ.get('ODOO_JAEGER_TRACING'))

_tracers = {}

SERVICE_PATTERN = 'odoo.%s'


# TODO lock
def init_tracer(dbname):
    service_name = SERVICE_PATTERN % (dbname,)
    tracer_config = jaeger_client.Config(
        config={  # usually read from some yaml config
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': False,
        },
        service_name=service_name,
        validate=True,
    )
    tracer = _tracers[dbname] = tracer_config.new_tracer()
    return tracer


def get_tracer(dbname):
    if not odoo_jaeger:
        return None
    return _tracers.get(dbname)


# TODO multiprocess compatible?
if odoo_jaeger:
    install_all_patches()
