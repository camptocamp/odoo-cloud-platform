# Copyright 2016-2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json

from odoo import api, models

METRICS_PARAM = "monitoring_prometheus.metrics"


class PrometheusGatherer(models.AbstractModel):
    """Collect application metrics to be exposed on the /metrics endpoint.

    Metrics are gathered by a cron and stored as JSON in an
    ``ir.config_parameter``, because crons and HTTP workers run in
    separate processes and cannot share the Prometheus registry.
    """

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
    def _cron_gather_metrics(self):
        self.env["ir.config_parameter"].sudo().set_param(
            METRICS_PARAM, json.dumps(self._gather_metrics())
        )
        return True
