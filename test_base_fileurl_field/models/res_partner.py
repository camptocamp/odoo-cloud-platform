# Copyright 2019 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):

    _inherit = 'res.partner'

    name = fields.Char()
    url_file = fields.FileURL(
        storage_location='s3',
        filename='url_file_fname',
        storage_path='partner'
    )
    url_file_fname = fields.Char()

    url_image = fields.FileURL(
        storage_location='s3',
        filename='url_image_fname',
        storage_path='partner_image',
    )
    url_image_fname = fields.Char()

    @api.constrains('url_file', 'url_file_fname')
    def _check_url_file_fname(self):
        rec = self.search([('url_file_fname', '=', self.url_file_fname)])
        if len(rec) > 1:
            raise ValidationError(_(
                "This file name is already used on an existing record. "
                "Please use another file name or delete the url_file on :\n"
                "Model: %s Id: %s" % (self._name, rec.id)
            ))

    @api.constrains('url_image', 'url_image_fname')
    def _check_url_image_fname(self):
        rec = self.search([('url_image_fname', '=', self.url_image_fname)])
        if len(rec) > 1:
            raise ValidationError(_(
                "This file name is already used on an existing record. "
                "Please use another file name or delete the url_image on :\n"
                "Model: %s Id: %s" % (self._name, rec.id)
            ))
