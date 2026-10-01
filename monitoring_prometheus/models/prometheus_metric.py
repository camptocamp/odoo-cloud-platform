# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json

from prometheus_client import CollectorRegistry, Gauge

from odoo import api, fields, models


class PrometheusMetric(models.Model):
    """Store the metrics gathered by ``prometheus.gatherer``.

    A record is stored per metric name/labels combination, because a single
    metric name can be reported several times with different labels (e.g.
    one gauge value per queue job state and channel).
    """

    _name = "prometheus.metric"
    _description = "Prometheus Metric"

    name = fields.Char(required=True, index=True)
    documentation = fields.Char()
    # JSON-serialized dict, used both to publish the metric and as part of
    # the uniqueness key alongside ``name``.
    _labels = fields.Char(default="{}")
    value = fields.Float(required=True)

    _sql_constraints = [
        (
            "name_labels_uniq",
            "unique(name, _labels)",
            "A metric can only be stored once per name and labels.",
        )
    ]

    @staticmethod
    def _serialize_labels(labels):
        return json.dumps(labels or {}, sort_keys=True)

    def labels(self):
        return json.loads(self._labels or "{}")

    def _check_upsert_context(self):
        # forces every writer through ``_create_or_update_metric`` (the upsert)
        assert self.env.context.get("prometheus_metric_upsert"), (
            "prometheus.metric records must be written through "
            "_create_or_update_metric()"
        )

    @api.model_create_multi
    def create(self, vals_list):
        self._check_upsert_context()
        return super().create(vals_list)

    def write(self, vals):
        self._check_upsert_context()
        return super().write(vals)

    @api.model
    def _create_or_update_metric(self, metric):
        """Create or update the record matching ``metric``, return it."""
        labels_key = self._serialize_labels(metric.get("labels"))
        record = self.search(
            [("name", "=", metric["name"]), ("_labels", "=", labels_key)],
            limit=1,
        )
        values = {
            "name": metric["name"],
            "documentation": metric.get("documentation", ""),
            "_labels": labels_key,
            "value": metric["value"],
        }
        if record:
            record.with_context(prometheus_metric_upsert=True).write(values)
        else:
            record = self.with_context(prometheus_metric_upsert=True).create(values)
        return record

    def _group_metrics(self):
        # group the records by metric definition so each gauge is created once
        groups = {}
        for record in self:
            labels = record.labels()
            label_names = tuple(sorted(labels))
            key = (record.name, record.documentation or "", label_names)
            groups.setdefault(key, []).append((labels, record.value))
        return groups

    def _build_prometheus_registry(self):
        groups = self._group_metrics()
        registry = CollectorRegistry()
        for (name, documentation, label_names), values in groups.items():
            gauge = Gauge(name, documentation, label_names, registry=registry)
            for labels, value in values:
                if labels:
                    gauge.labels(**labels).set(value)
                else:
                    gauge.set(value)
        return registry
