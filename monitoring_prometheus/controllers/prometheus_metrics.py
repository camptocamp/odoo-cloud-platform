# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json
import logging

from prometheus_client import REGISTRY, CollectorRegistry, Gauge, generate_latest

from odoo.http import Controller, request, route

from ..models.psutils_helpers import get_process_info

_logger = logging.getLogger(__name__)


class PrometheusController(Controller):
    def _build_gathered_registry(self):
        """Build an isolated registry from the latest gathered metrics."""
        registry = CollectorRegistry()
        gauges = {}
        records = request.env["prometheus.metric"].sudo().search([])
        for record in records:
            try:
                labels = json.loads(record.labels or "{}")
                gauge = gauges.get(record.name)
                if gauge is None:
                    gauge = gauges[record.name] = Gauge(
                        record.name,
                        record.documentation or "",
                        sorted(labels),
                        registry=registry,
                    )
                if labels:
                    gauge.labels(**labels).set(record.value)
                else:
                    gauge.set(record.value)
            except ValueError:
                _logger.exception("Could not publish Prometheus metric %s", record.name)
        return registry

    @route("/metrics", auth="public")
    def metrics(self):
        get_process_info()
        output = generate_latest(REGISTRY)
        try:
            output += generate_latest(self._build_gathered_registry())
        except Exception:
            _logger.exception("Could not publish the gathered Prometheus metrics")
        return output
