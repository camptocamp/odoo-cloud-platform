# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests import TransactionCase

from ..models.prometheus_gatherer import GAUGE_NAME, MONITORED_STATES


class TestPrometheusGatherer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gatherer = cls.env["prometheus.gatherer"]
        cls.channel = cls.env["queue.job.channel"].create(
            {
                "name": "test_prometheus",
                "parent_id": cls.env.ref("queue_job.channel_root").id,
            }
        )
        Job = cls.env["queue.job"].with_context(
            _job_edit_sentinel=cls.env["queue.job"].EDIT_SENTINEL
        )
        Job.create(
            [
                {
                    "uuid": f"test_prometheus_{index}",
                    "user_id": cls.env.user.id,
                    "state": "pending",
                    "channel": cls.channel.complete_name,
                    "model_name": "queue.job",
                    "method_name": "write",
                }
                for index in range(2)
            ]
        )

    def test_00_gather_queue_job_counts_for_every_state(self):
        """Test queue metrics include counts and zero series for every state."""
        metrics = self.gatherer._gather_metrics()
        counts = {
            metric["labels"]["state"]: metric["value"]
            for metric in metrics
            if metric["name"] == GAUGE_NAME
            and metric["labels"]["channel"] == self.channel.complete_name
        }
        self.assertEqual(
            counts,
            {state: 2 if state == "pending" else 0 for state in MONITORED_STATES},
        )
