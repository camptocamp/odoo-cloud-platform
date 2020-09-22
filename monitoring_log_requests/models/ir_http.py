# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json
import time
from os import environ
from collections import MutableMapping
from contextlib import suppress

from odoo import models
from odoo.http import request as http_request
from odoo.tools.config import config


udp_dest = environ.get("ODOO_REQUESTS_LOGGING_UDP")
if udp_dest:
    import socket
    import atexit

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    atexit.register(sock.close)
    ip, port = udp_dest.split(":")
    port = int(port)

    def output_method(data):
        data += "\n"
        sock.sendto(data.encode("utf-8"), (ip, port))
else:
    import logging

    _logger = logging.getLogger("monitoring.http.requests")
    output_method = _logger.info


def delete_from_dict(d, keys):
    for key in keys:
        with suppress(KeyError):
            del d[key]
    for value in d.values():
        if isinstance(value, MutableMapping):
            delete_from_dict(value, keys)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _dispatch(cls):
        begin = time.time()
        response = super()._dispatch()
        end = time.time()
        if not cls._monitoring_blacklist(http_request) and cls._monitoring_filter(
            http_request
        ):
            info = cls._monitoring_info(http_request, response, begin, end)
            cls._monitoring_log(info)
        return response

    @classmethod
    def _monitoring_blacklist(cls, request):
        path_info = request.httprequest.environ.get("PATH_INFO")
        if path_info.startswith("/longpolling/"):
            return True
        return False

    @classmethod
    def _monitoring_filter(cls, _):
        return True

    @classmethod
    def _json_blacklist(cls):
        return ["HTTP_COOKIE", "session_token"]

    @classmethod
    def _monitoring_info(cls, request, response, begin, end):
        info = {
            # timing
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(begin)),
            "duration": end - begin,
            # HTTP things
            "method": request.httprequest.method,
            "url": request.httprequest.url,
            "status_code": response.status_code,
            "headers": request.httprequest.environ.copy(),
            # Odoo things
            "uid": request.uid,
            "server_environment": config.get("running_env"),
        }
        if hasattr(request, "session"):
            info["session"] = dict(request.session)
        if hasattr(request, "params"):
            info["params"] = dict(request.params)

        return info

    @classmethod
    def _monitoring_log(cls, info):
        delete_from_dict(info, cls._json_blacklist())
        output_method(
            json.dumps(
                info,
                ensure_ascii=True,
                default=lambda o: f"<non-serializable: {type(o).__qualname__}>",
            )
        )
