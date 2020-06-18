# -*- coding: utf-8 -*-

import logging
import os
import threading
import uuid

from distutils.util import strtobool

from odoo import http

_logger = logging.getLogger(__name__)

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
        record.request_id = getattr(threading.current_thread(), 'request_uuid', None)
        record.uid = getattr(threading.current_thread(), 'uid', None)
        _super = super(OdooJsonFormatter, self)
        return _super.add_fields(log_record, record, message_dict)


if is_true(os.environ.get('ODOO_LOGGING_JSON')):
    format = ('%(asctime)s %(pid)s %(levelname)s'
              '%(dbname)s %(name)s: %(message)s')
    formatter = OdooJsonFormatter(format)
    logging.getLogger().handlers[0].formatter = formatter


# monkey patch WebRequest constructor to store request_uuid
org_init = http.WebRequest.__init__


def new_init(self, httprequest):
    org_init(self, httprequest)
    threading.current_thread().request_uuid = uuid.uuid4()


http.WebRequest.__init__ = new_init
