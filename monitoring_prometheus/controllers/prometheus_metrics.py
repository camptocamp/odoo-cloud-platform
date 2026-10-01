# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging

from prometheus_client import REGISTRY, Gauge, generate_latest

from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)


# Gauges must be instantiated only once per process, registering the same
# metric name twice raises a "Duplicated timeseries" error.
_GAUGES = {}


def _get_gauge(name, documentation, label_names, registry=REGISTRY):
    gauge = _GAUGES.get(name)
    if gauge is None:
        gauge = Gauge(name, documentation, label_names, registry=registry)
        _GAUGES[name] = gauge
    return gauge


class PrometheusController(Controller):
    @route("/metrics", auth="public")
    def metrics(self):
        # REGISTRY holds the in-process metrics (request latency, longpolling)
        output = generate_latest(REGISTRY)
        try:
            records = request.env["prometheus.metric"].sudo().search([])
            registry = records._build_prometheus_registry()
            output += generate_latest(registry)
        except Exception:
            _logger.exception("Could not publish the gathered Prometheus metrics")
        return output
