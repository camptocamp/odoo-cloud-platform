# -*- coding: utf-8 -*-

import logging
import os
import threading

from distutils.util import strtobool

from pythonjsonlogger import jsonlogger


def is_true(strval):
    return bool(strtobool(strval or '0'.lower()))


class OdooJsonFormatter(jsonlogger.JsonFormatter):

    def add_fields(self, log_record, record, message_dict):
        record.pid = os.getpid()
        record.dbname = getattr(threading.currentThread(), 'dbname', '?')
        _super = super(OdooJsonFormatter, self)
        return _super.add_fields(log_record, record, message_dict)


if is_true(os.environ.get('ODOO_LOGGING_JSON')):
    format = ('%(asctime)s %(pid)s %(levelname)s'
              '%(dbname)s %(name)s: %(message)s')
    formatter = OdooJsonFormatter(format)
    logging.getLogger().handlers[0].formatter = formatter
