# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json
import logging
import os
import time

from odoo import models
from odoo.http import request as http_request
from odoo.tools.config import config

_logger = logging.getLogger("monitoring.http.requests")

# Maximum size (bytes) for serialized params in log entries.
# Set MONITORING_LOG_PARAMS_MAX_SIZE=0 to disable param logging.
PARAMS_MAX_SIZE = int(os.environ.get("MONITORING_LOG_PARAMS_MAX_SIZE", "4096"))


def _sanitize_params(params, max_size=PARAMS_MAX_SIZE):
    """Return a JSON-safe summary of RPC params, excluding binary data.

    Only keeps scalar values (str, int, float, bool, None) and lists of IDs.
    Truncates the serialized result to max_size bytes.
    """
    if not params or max_size <= 0:
        return None

    def _clean(val, depth=0):
        if depth > 3:
            return "..."
        if val is None or isinstance(val, (bool, int, float)):
            return val
        if isinstance(val, str):
            # Skip binary-like strings (base64 encoded data)
            if len(val) > 1000:
                return f"<str len={len(val)}>"
            return val
        if isinstance(val, bytes):
            return f"<bytes len={len(val)}>"
        if isinstance(val, (list, tuple)):
            if all(isinstance(v, int) for v in val):
                # List of IDs — keep as-is
                return list(val)
            return [_clean(v, depth + 1) for v in val[:20]]
        if isinstance(val, dict):
            return {
                k: _clean(v, depth + 1)
                for k, v in list(val.items())[:30]
                if not isinstance(v, bytes)
            }
        return str(type(val).__name__)

    cleaned = _clean(params)
    result = json.dumps(cleaned, default=str)
    if len(result) > max_size:
        return result[:max_size] + "..."
    return cleaned


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _dispatch(cls, endpoint):
        begin = time.time()
        response = super()._dispatch(endpoint)
        end = time.time()
        if not cls._monitoring_blacklist(http_request) and cls._monitoring_filter(
            http_request
        ):
            info = cls._monitoring_info(http_request, response, begin, end)
            cls._monitoring_log(info)
        return response

    @classmethod
    def _monitoring_blacklist(cls, request):
        path_info = request.httprequest.environ.get("PATH_INFO", "")
        if path_info.startswith(("/longpolling/", "/websocket")):
            return True
        return False

    @classmethod
    def _monitoring_filter(cls, _):
        return True

    @classmethod
    def _monitoring_info(cls, request, response, begin, end):
        path = request.httprequest.environ.get("PATH_INFO")
        info = {
            # timing
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(begin)),
            "duration": end - begin,
            # HTTP things
            "method": request.httprequest.method,
            "url": request.httprequest.url,
            "path": path,
            "content_type": request.httprequest.environ.get("CONTENT_TYPE"),
            "user_agent": request.httprequest.environ.get("HTTP_USER_AGENT"),
            # Odoo things
            "db": None,
            "uid": request.uid,
            "login": None,
            "server_environment": config.get("running_env"),
            "model": None,
            "model_method": None,
            "workflow_signal": None,
            # response things
            "response_status_code": None,
        }
        if hasattr(response, "status_code"):
            info["response_status_code"] = response.status_code
        if hasattr(request, "session"):
            info.update(
                {
                    "login": request.session.get("login"),
                    "db": request.session.get("db"),
                }
            )
        if hasattr(request, "params") and request.params:
            info.update(
                {
                    "model": request.params.get("model"),
                    "model_method": request.params.get("method"),
                }
            )
            if PARAMS_MAX_SIZE > 0:
                args = request.params.get("args")
                kwargs = request.params.get("kwargs")
                if args:
                    info["args"] = _sanitize_params(args)
                if kwargs:
                    info["kwargs"] = _sanitize_params(kwargs)
        return info

    @classmethod
    def _monitoring_log(cls, info):
        _logger.info(json.dumps(info, default=str))
