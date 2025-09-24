# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os
import sys
import threading
import uuid

from odoo import http

from .strtobool import strtobool

_logger = logging.getLogger(__name__)

try:
    from pythonjsonlogger.json import JsonFormatter
except ImportError:
    JsonFormatter = None  # noqa
    _logger.debug("Cannot 'import pythonjsonlogger'.")


def is_true(strval):
    return bool(strtobool(strval or "0".lower()))


class OdooJsonFormatter(JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        record.pid = os.getpid()
        record.dbname = getattr(threading.current_thread(), "dbname", "?")
        record.request_id = getattr(threading.current_thread(), "request_uuid", None)
        record.uid = getattr(threading.current_thread(), "uid", None)
        _super = super()
        return _super.add_fields(log_record, record, message_dict)


if is_true(os.environ.get("ODOO_LOGGING_JSON")):
    formatted_message = (
        "%(asctime)s %(pid)s %(levelname)s %(dbname)s %(name)s: %(message)s"
    )
    formatter = OdooJsonFormatter(formatted_message)

    if is_true(os.environ.get("ODOO_LOGGING_JSON_STDERR")):

        class MaxLevelFilter(logging.Filter):
            def __init__(self, max_level):
                self.max_level = max_level

            def filter(self, record):
                return record.levelno < self.max_level

        # keep the original level
        root_logger = logging.getLogger()
        original_level = root_logger.level

        # Split lower levels into stdout
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.NOTSET)
        stdout_handler.addFilter(MaxLevelFilter(logging.WARNING))
        stdout_handler.setFormatter(formatter)

        # Split WARNING and upper into stderr
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.WARNING)
        stderr_handler.setFormatter(formatter)

        # Replace handlers
        root_logger.handlers = []
        root_logger.setLevel(original_level)
        root_logger.addHandler(stdout_handler)
        root_logger.addHandler(stderr_handler)
    else:
        logging.getLogger().handlers[0].formatter = formatter


# monkey patch Request constructor to store request_uuid
org_init = http.Request.__init__


def new_init(self, httprequest):
    org_init(self, httprequest)
    threading.current_thread().request_uuid = uuid.uuid4()


http.Request.__init__ = new_init
