# Copyright 2016-2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from prometheus_client import generate_latest

from odoo.http import Controller, route


class PrometheusController(Controller):
    @route("/metrics", auth="public")
    def metrics(self):
        return generate_latest()
