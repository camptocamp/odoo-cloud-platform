# Copyright 2016-2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from prometheus_client import CollectorRegistry, Gauge

from odoo import api, models


class PrometheusGatherer(models.AbstractModel):
    """Collect application metrics to be exposed on the /metrics endpoint."""

    _name = "prometheus.gatherer"
    _description = "Prometheus Metrics Gatherer"

    @api.model
    def _gather_metrics(self):
        """Return the metrics as a list of dicts.

        Each entry is of the form::

            {
                "name": "odoo_some_metric",
                "documentation": "What this metric measures",
                "labels": {"label_name": "label_value"},
                "value": 42,
            }

        ``labels`` may be omitted for an unlabelled metric. All the entries
        sharing a ``name`` must declare the same label names.

        Modules extending this method must return the result of ``super()``
        extended with their own entries.
        """
        return []

    @api.model
    def _group_metrics(self, metrics):
        # group the metrics by definition so each gauge is created once
        groups = {}
        for metric in metrics:
            labels = metric.get("labels") or {}
            label_names = tuple(sorted(labels))
            key = (metric["name"], metric.get("documentation", ""), label_names)
            groups.setdefault(key, []).append((labels, metric["value"]))
        return groups

    @api.model
    def _build_prometheus_registry(self):
        """Return a new ``CollectorRegistry`` publishing ``_gather_metrics()``.

        A fresh registry per call, instead of process-wide gauges, means
        nothing is shared between concurrent requests nor between the
        databases served by the same process.
        """
        groups = self._group_metrics(self._gather_metrics())
        registry = CollectorRegistry()
        for (name, documentation, label_names), values in groups.items():
            gauge = Gauge(name, documentation, label_names, registry=registry)
            for labels, value in values:
                if labels:
                    gauge.labels(**labels).set(value)
                else:
                    gauge.set(value)
        return registry
