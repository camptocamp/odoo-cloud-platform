# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import fields, models


class SpreadsheetDashboard(models.Model):
    _inherit = "spreadsheet.dashboard"

    data = fields.Binary(attachment=False)
    raw = fields.Binary(attachment=False)
