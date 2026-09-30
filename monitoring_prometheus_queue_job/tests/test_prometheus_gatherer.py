# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from unittest.mock import patch

from odoo.tests import TransactionCase

from ..models.prometheus_gatherer import GAUGE_NAME, MONITORED_STATES


class TestPrometheusGatherer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gatherer = cls.env["prometheus.gatherer"]
        cls.channel = cls.env["queue.job.channel"].search([], limit=1)

    def test_00_gather_queue_job_counts_for_every_state(self):
        """Test queue metrics include counts and zero series for every state."""
        grouped_jobs = [
            {
                "state": "pending",
                "channel": self.channel.complete_name,
                "__count": 2,
            }
        ]

        with patch.object(
            type(self.env["queue.job"]),
            "read_group",
            return_value=grouped_jobs,
        ):
            metrics = self.gatherer._gather_metrics()

        queue_metrics = {
            (metric["labels"]["state"], metric["labels"]["channel"]): metric["value"]
            for metric in metrics
            if metric["name"] == GAUGE_NAME
        }
        self.assertEqual(
            queue_metrics[("pending", self.channel.complete_name)],
            2,
        )
        self.assertEqual(
            queue_metrics[("failed", self.channel.complete_name)],
            0,
        )
        self.assertEqual(len(queue_metrics), len(MONITORED_STATES))
