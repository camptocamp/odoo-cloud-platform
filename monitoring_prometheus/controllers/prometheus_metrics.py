# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json
import logging

from prometheus_client import Gauge, generate_latest

from odoo.http import Controller, request, route

_logger = logging.getLogger(__name__)

# Gauges must be instantiated only once per process, registering the same
# metric name twice raises a "Duplicated timeseries" error.
_GAUGES = {}


def _get_gauge(name, documentation, label_names):
    gauge = _GAUGES.get(name)
    if gauge is None:
        gauge = Gauge(name, documentation, label_names)
        _GAUGES[name] = gauge
    return gauge


class PrometheusController(Controller):
    def _publish_gathered_metrics(self):
        records = request.env["prometheus.metric"].sudo().search([])
        if not records:
            return

        cleared = set()
        for record in records:
            name = record.name
            labels = json.loads(record.labels or "{}")
            gauge = _get_gauge(name, record.documentation or "", sorted(labels))
            if name not in cleared:
                # drop the series that disappeared since the last collection
                gauge.clear()
                cleared.add(name)
            if labels:
                gauge.labels(**labels).set(record.value)
            else:
                gauge.set(record.value)

    @route("/metrics", auth="public")
    def metrics(self):
        try:
            self._publish_gathered_metrics()
        except Exception:
            _logger.exception("Could not publish the gathered Prometheus metrics")
        return generate_latest()
