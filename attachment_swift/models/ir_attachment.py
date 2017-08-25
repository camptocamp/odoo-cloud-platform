# -*- coding: utf-8 -*-
# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def _file_write(self, value, checksum):
        _logger.debug('Writing a file :)')
        filename = super(IrAttachment, self)._file_write(value, checksum)
        return filename
