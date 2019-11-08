# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json
import logging
import time

from odoo import models
from odoo.http import request as http_request
from odoo.tools.config import config


_logger = logging.getLogger('monitoring.http.requests')


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls):
        begin = time.time()
        response = super()._dispatch()
        end = time.time()
        if (not cls._monitoring_blacklist(http_request) and
                cls._monitoring_filter(http_request)):
            info = cls._monitoring_info(http_request, response, begin, end)
            cls._monitoring_log(info)
        return response

    @classmethod
    def _monitoring_blacklist(cls, request):
        path_info = request.httprequest.environ.get('PATH_INFO')
        if path_info.startswith('/longpolling/'):
            return True
        return False

    @classmethod
    def _monitoring_filter(cls, _):
        return True

    @classmethod
    def _monitoring_info(cls, request, response, begin, end):
        path = request.httprequest.environ.get('PATH_INFO')
        info = {
            # timing
            'start_time': time.strftime("%Y-%m-%d %H:%M:%S",
                                        time.gmtime(begin)),
            'duration': end - begin,
            # HTTP things
            'method': request.httprequest.method,
            'url': request.httprequest.url,
            'path': path,
            'content_type': request.httprequest.environ.get('CONTENT_TYPE'),
            'user_agent': request.httprequest.environ.get('HTTP_USER_AGENT'),
            # Odoo things
            'db': None,
            'uid': request.uid,
            'login': None,
            'server_environment': config.get('running_env'),
            'model': None,
            'model_method': None,
            'workflow_signal': None,
            # response things
            'response_status_code': None,
        }
        if hasattr(request, 'status_code'):
            info['status_code'] = response.status_code
        if hasattr(request, 'session'):
            info.update({
                'login': request.session.get('login'),
                'db': request.session.get('db'),
            })
        if hasattr(request, 'params'):
            info.update({
                'model': request.params.get('model'),
                'model_method': request.params.get('method'),
                'workflow_signal': request.params.get('signal'),
            })
        return info

    @classmethod
    def _monitoring_log(cls, info):
        _logger.info(json.dumps(info))
