# -*- coding: utf-8 -*-
from openerp import api, fields, models


class ShippingLabel(models.Model):
    """ Inherit of shipping label to store datas
    in the right location if S3 activated """

    _inherit = 'shipping.label'

    datas = fields.Binary(
        compute='_compute_datas',
        inverse='_inverse_datas',
        string='File Content',
        nodrop=True,
    )

    @api.depends('store_fname', 'db_datas')
    def _compute_datas(self):
        values = self._data_get('datas', None)
        for attach in self:
            attach.datas = values.get(attach.id)

    def _inverse_datas(self):
        # override in order to store files that need fast access,
        # we keep them in the database instead of the object storage
        location = self.attachment_id._storage()
        for attach in self:
            if location == 's3' and self._store_in_db_when_s3():
                # compute the fields that depend on datas
                value = attach.datas
                bin_data = value and value.decode('base64') or ''
                vals = {
                    'file_size': len(bin_data),
                    'checksum': self._compute_checksum(bin_data),
                    'db_datas': value,
                    # we seriously don't need index content on those fields
                    'index_content': False,
                    'store_fname': False,
                }
                fname = attach.store_fname
                # write as superuser, as user probably does not
                # have write access
                super(ShippingLabel, attach.sudo()).write(vals)
                if fname:
                    self._file_delete(fname)
                continue
            self.attachment_id._data_set('datas', attach.datas, None)
