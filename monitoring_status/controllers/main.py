# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import json

import werkzeug

from odoo import http
from odoo.addons.web.controllers.main import ensure_db


class HealthCheckFilter(logging.Filter):

    def __init__(self, path, name=''):
        super().__init__(name)
        self.path = path

    def filter(self, record):
        return self.path not in record.getMessage()


logging.getLogger('werkzeug').addFilter(
    HealthCheckFilter('GET /monitoring/status HTTP')
)


class Monitoring(http.Controller):

    @http.route('/monitoring/status', type='http', auth='none')
    def status(self):
        ensure_db()
        # TODO: add 'sub-systems' status and infos:
        # queue job, cron, database, ...
        headers = {'Content-Type': 'application/json'}
        info = {'status': 1}
        session = http.request.session
        # We set a custom expiration of 1 second for this request, as we do a
        # lot of health checks, we don't want those anonymous sessions to be
        # kept. Beware, it works only when session_redis is used.
        # Alternatively, we could set 'session.should_save = False', which is
        # tested in odoo source code, but we wouldn't check the health of
        # Redis.
        if not session.uid:
            session.expiration = 1
        return werkzeug.wrappers.Response(json.dumps(info), headers=headers)
