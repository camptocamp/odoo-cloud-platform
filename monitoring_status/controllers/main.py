# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json

import werkzeug

from openerp import http
from openerp.addons.web.controllers.main import ensure_db


class Monitoring(http.Controller):

    @http.route('/monitoring/status', type='http', auth='none')
    def status(self):
        ensure_db()
        # TODO: add 'sub-systems' status and infos:
        # queue job, cron, database, ...
        headers = {'Content-Type': 'application/json'}
        info = {'status': 1}
        return werkzeug.wrappers.Response(json.dumps(info), headers=headers)
