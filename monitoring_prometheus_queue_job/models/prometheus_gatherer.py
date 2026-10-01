# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo import api, models

MONITORED_STATES = ("pending", "enqueued", "started", "failed", "wait_dependencies")
GAUGE_NAME = "odoo_queue_job_count"
GAUGE_DOC = "Number of queue jobs per state and channel"


class PrometheusGatherer(models.AbstractModel):
    _inherit = "prometheus.gatherer"

    @api.model
    def _gather_metrics(self):
        metrics = super()._gather_metrics()
        groups = self.env["queue.job"].read_group(
            [("state", "in", list(MONITORED_STATES))],
            ["state", "channel"],
            ["state", "channel"],
            lazy=False,
        )
        channels = self.env["queue.job.channel"].search([]).mapped("complete_name")
        # seed every combination so a series never disappears when its jobs are gone
        counts = {
            (state, channel): 0 for state in MONITORED_STATES for channel in channels
        }
        for group in groups:
            key = (group["state"], group["channel"])
            counts[key] = counts.get(key, 0) + group["__count"]
        metrics.extend(
            {
                "name": GAUGE_NAME,
                "documentation": GAUGE_DOC,
                "labels": {"state": state, "channel": channel},
                "value": count,
            }
            for (state, channel), count in counts.items()
        )
        return metrics
