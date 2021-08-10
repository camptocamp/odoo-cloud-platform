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

    @http.route('/monitoring/status', type='http', auth='none', save_session=False)
    def status(self):
        ensure_db()
        # TODO: add 'sub-systems' status and infos:
        # queue job, cron, database, ...
        headers = {'Content-Type': 'application/json'}
        info = {'status': 1}
        return werkzeug.wrappers.Response(json.dumps(info), headers=headers)
