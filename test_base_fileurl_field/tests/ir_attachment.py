# Copyright 2019 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

import logging

from odoo import models, api

_logger = logging.getLogger(__name__)

FAKE_S3_BUCKET = {}


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _get_stores(self):
        l = ['s3']
        l += super(IrAttachment, self)._get_stores()
        return l

    @api.model
    def _store_file_read(self, fname, bin_size=False):
        if fname.startswith('s3://'):
            return FAKE_S3_BUCKET.get(fname)
        else:
            return super(IrAttachment, self)._store_file_read(fname, bin_size)

    @api.model
    def _store_file_write(self, key, bin_data):
        location = self.env.context.get('storage_location') or self._storage()
        if location == 's3':
            FAKE_S3_BUCKET[key] = bin_data
            filename = 's3://fake_bucket/%s' % key
        else:
            _super = super(IrAttachment, self)
            filename = _super._store_file_write(key, bin_data)
        return filename

    @api.model
    def _store_file_delete(self, fname):
        if fname.startswith('s3://'):
            FAKE_S3_BUCKET.pop(fname)
        else:
            super(IrAttachment, self)._store_file_delete(fname)
