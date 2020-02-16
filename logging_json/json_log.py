# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os
import threading
import time

from distutils.util import strtobool
from odoo.netsvc import PerfFilter

_logger = logging.getLogger(__name__)
TIMING_DP = 6

try:
    from pythonjsonlogger import jsonlogger
except ImportError:
    jsonlogger = None  # noqa
    _logger.debug("Cannot 'import pythonjsonlogger'.")


def is_true(strval):
    return bool(strtobool(strval or '0'.lower()))


class OdooJsonFormatter(jsonlogger.JsonFormatter):

    def add_fields(self, log_record, record, message_dict):
        record.pid = os.getpid()
        record.dbname = getattr(threading.currentThread(), 'dbname', '?')
        if hasattr(record, "perf_info"):
            delattr(record, "perf_info")
        _super = super(OdooJsonFormatter, self)
        return _super.add_fields(log_record, record, message_dict)


class JsonPerfFilter(logging.Filter):

    def filter(self, record):
        if hasattr(threading.current_thread(), "query_count"):
            record.request_time = round(
                time.time() - threading.current_thread().perf_t0, TIMING_DP)
            record.query_count = threading.current_thread().query_count
            record.query_time = round(
                threading.current_thread().query_time, TIMING_DP)
            delattr(threading.current_thread(), "query_count")
        return True


if is_true(os.environ.get('ODOO_LOGGING_JSON')):
    format = ('%(asctime)s %(pid)s %(levelname)s'
              '%(dbname)s %(name)s: %(message)s')
    formatter = OdooJsonFormatter(format)
    logging.getLogger().handlers[0].formatter = formatter

    http_logger = logging.getLogger('werkzeug')

    # Configure performance logging
    for f in http_logger.filters:
        if isinstance(f, PerfFilter):
            http_logger.removeFilter(f)
    json_perf_filter = JsonPerfFilter()
    http_logger.addFilter(json_perf_filter)
