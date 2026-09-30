# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from unittest.mock import patch

from odoo.tests import TransactionCase


class TestPrometheusMetric(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.metric_model = cls.env["prometheus.metric"]
        cls.gatherer = cls.env["prometheus.gatherer"]

    def test_00_update_metric_reuses_canonical_labels(self):
        """Test updating a metric reuses its canonical label combination."""
        metric = self.metric_model._update_metric(
            {
                "name": "odoo_test_metric",
                "labels": {"second": "2", "first": "1"},
                "value": 1,
            }
        )

        updated_metric = self.metric_model._update_metric(
            {
                "name": "odoo_test_metric",
                "labels": {"first": "1", "second": "2"},
                "value": 2,
            }
        )

        self.assertEqual(updated_metric, metric)
        self.assertEqual(updated_metric.value, 2)

    def test_01_cron_removes_stale_metric_series(self):
        """Test gathering metrics removes series absent from the new snapshot."""
        stale_metric = self.metric_model.create(
            {"name": "odoo_stale_metric", "value": 1}
        )
        gathered_metric = {
            "name": "odoo_current_metric",
            "documentation": "Current metric",
            "value": 2,
        }

        with patch.object(
            type(self.gatherer),
            "_gather_metrics",
            return_value=[gathered_metric],
        ):
            self.gatherer._cron_gather_metrics()

        self.assertFalse(stale_metric.exists())
        current_metric = self.metric_model.search(
            [("name", "=", "odoo_current_metric")]
        )
        self.assertEqual(current_metric.value, 2)
