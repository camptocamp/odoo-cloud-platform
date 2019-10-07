# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os

from distutils.util import strtobool

from odoo.tools.config import config

_logger = logging.getLogger(__name__)

try:
    from statsd import defaults
    from statsd.client import StatsClient
except ImportError:
    _logger.warning('statds must be installed')
    defaults = None  # noqa
    StatsClient = None  # noqa


def is_true(strval):
    return bool(strtobool(strval or '0'.lower()))


statsd_active = is_true(os.environ.get('ODOO_STATSD'))

statsd = None
customer = None
environment = None
if statsd_active and statsd is None and StatsClient is not None:
    if not os.environ.get('STATSD_CUSTOMER'):
        raise Exception(
            'STATSD_CUSTOMER must contain the name of the customer'
        )
    customer = os.environ.get('STATSD_CUSTOMER')
    if os.environ.get('STATSD_ENVIRONMENT'):
        environment = os.environ['STATSD_ENVIRONMENT']
    elif config.get('running_env'):
        environment = config['running_env']
    else:
        raise Exception(
            'Either STATSD_ENVIRONMENT or configuration option running_env '
            'must contain the environment (prod, integration, ...)'
        )

    host = os.getenv('STATSD_HOST', defaults.HOST)
    port = int(os.getenv('STATSD_PORT', defaults.PORT))
    prefix = os.getenv('STATSD_PREFIX', defaults.PREFIX)
    maxudpsize = int(os.getenv('STATSD_MAXUDPSIZE', defaults.MAXUDPSIZE))
    ipv6 = bool(int(os.getenv('STATSD_IPV6', defaults.IPV6)))
    statsd = StatsClient(host=host, port=port, prefix='odoo',
                         maxudpsize=maxudpsize, ipv6=ipv6)
