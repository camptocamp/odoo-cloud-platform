# Copyright 2019 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import models, fields


class ResUsers(models.Model):

    _inherit = 'res.users'

    partner_url_file = fields.FileURL(related='partner_id.url_file')
    partner_url_file_fname = fields.Char(related='partner_id.url_file_fname')
