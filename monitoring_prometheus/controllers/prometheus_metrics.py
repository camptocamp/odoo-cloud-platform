# Copyright 2016-2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json
import logging

from prometheus_client import Gauge, generate_latest

from odoo.http import Controller, request, route

from ..models.prometheus_gatherer import METRICS_PARAM

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
        param = request.env["ir.config_parameter"].sudo().get_param(METRICS_PARAM)
        if not param:
            return

        cleared = set()
        for metric in json.loads(param):
            name = metric["name"]
            labels = metric.get("labels") or {}
            gauge = _get_gauge(name, metric.get("documentation", ""), sorted(labels))
            if name not in cleared:
                # drop the series that disappeared since the last collection
                gauge.clear()
                cleared.add(name)
            if labels:
                gauge.labels(**labels).set(metric["value"])
            else:
                gauge.set(metric["value"])

    @route("/metrics", auth="public")
    def metrics(self):
        try:
            self._publish_gathered_metrics()
        except Exception:
            _logger.exception("Could not publish the gathered Prometheus metrics")
        return generate_latest()
