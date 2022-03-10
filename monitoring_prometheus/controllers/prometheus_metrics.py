# -*- coding: utf-8 -*-
# Copyright 2016-2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
from __future__ import absolute_import
import logging

from openerp.http import Controller, route

_logger = logging.getLogger(__name__)

try:
    from prometheus_client import generate_latest
except (ImportError, IOError), err:
    _logger.warning(err)


class PrometheusController(Controller):
    @route(u'/metrics', auth=u'public')
    def metrics(self):
        return generate_latest()
