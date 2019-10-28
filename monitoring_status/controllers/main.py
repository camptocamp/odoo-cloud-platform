# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import json

import psycopg2

import werkzeug

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import ensure_db


class HealthCheckFilter(logging.Filter):

    def __init__(self, path, name=''):
        super(HealthCheckFilter, self).__init__(name)
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
        http_status = 200
        # TODO: add 'sub-systems' status and infos:
        # queue job, cron, database, ...
        headers = {'Content-Type': 'application/json'}
        info = {'status': 1}
        # check the database connection
        try:
            cr = request.env.cr
            cr.execute(
                'SELECT value '
                'FROM ir_config_parameter '
                'WHERE key=%s',
                ('web.base.url',))
            result = cr.fetchone()
            info['web.base.url'] = result or ''
        except psycopg2.OperationalError as exc:
            info['database_error'] = str(exc)
            http_status = 503
        session = http.request.session
        # We set a custom expiration of 1 second for this request, as we do a
        # lot of health checks, we don't want those anonymous sessions to be
        # kept. Beware, it works only when session_redis is used.
        # Alternatively, we could set 'session.should_save = False', which is
        # tested in odoo source code, but we wouldn't check the health of
        # Redis.
        if not session.uid:
            session.expiration = 1
        return werkzeug.wrappers.Response(
            json.dumps(info), status=http_status, headers=headers
        )
