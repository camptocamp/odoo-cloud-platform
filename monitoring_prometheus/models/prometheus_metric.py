# Copyright 2016-2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json

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
    labels = fields.Char(default="{}")
    value = fields.Float(required=True)

    @staticmethod
    def _labels_key(labels):
        return json.dumps(labels or {}, sort_keys=True)

    @api.model
    def _update_metric(self, metric):
        """Create or update the record matching ``metric``, return it."""
        labels_key = self._labels_key(metric.get("labels"))
        record = self.search(
            [("name", "=", metric["name"]), ("labels", "=", labels_key)],
            limit=1,
        )
        values = {
            "name": metric["name"],
            "documentation": metric.get("documentation", ""),
            "labels": labels_key,
            "value": metric["value"],
        }
        if record:
            record.write(values)
        else:
            record = self.create(values)
        return record
