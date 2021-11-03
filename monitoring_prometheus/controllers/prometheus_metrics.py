# -*- coding: utf-8 -*-
# Copyright 2016-2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import logging

from odoo.http import Controller, route

_logger = logging.getLogger(__name__)

try:
    from prometheus_client import generate_latest
except (ImportError, IOError) as err:
    _logger.warning(err)


class PrometheusController(Controller):
    @route('/metrics', auth='public')
    def metrics(self):
        return generate_latest()
