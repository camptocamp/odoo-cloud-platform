# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestPrometheusController(HttpCase):
    def test_00_metrics_publishes_current_records(self):
        """Test the endpoint publishes current rows and drops deleted series."""
        record = self.env["prometheus.metric"].create(
            {
                "name": "odoo_test_gauge",
                "labels": '{"a": "1"}',
                "value": 3,
            }
        )

        self.assertIn(
            'odoo_test_gauge{a="1"} 3.0',
            self.url_open("/metrics").text,
        )

        record.unlink()
        self.assertNotIn("odoo_test_gauge", self.url_open("/metrics").text)

    @mute_logger("odoo.addons.monitoring_prometheus.controllers.prometheus_metrics")
    def test_01_incompatible_metric_does_not_hide_later_records(self):
        """Test incompatible labels do not hide following valid rows."""
        self.env["prometheus.metric"].create(
            [
                {
                    "name": "odoo_incompatible_gauge",
                    "labels": '{"a": "1"}',
                    "value": 1,
                },
                {
                    "name": "odoo_incompatible_gauge",
                    "labels": '{"b": "2"}',
                    "value": 1,
                },
                {
                    "name": "odoo_valid_gauge",
                    "value": 2,
                },
            ]
        )

        response = self.url_open("/metrics").text

        self.assertIn('odoo_incompatible_gauge{a="1"} 1.0', response)
        self.assertNotIn('odoo_incompatible_gauge{b="2"}', response)
        self.assertIn("odoo_valid_gauge 2.0", response)
