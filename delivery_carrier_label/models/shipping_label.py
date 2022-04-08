# -*- coding: utf-8 -*-
from openerp import api, fields, models


class ShippingLabel(models.Model):
    """Inherit of shipping label to store datas
    in the right location if external stroage activated"""

    _inherit = "shipping.label"

    datas = fields.Binary(
        compute="_compute_datas",
        inverse="_inverse_datas",
        string="File Content",
        nodrop=True,
    )

    @api.depends("store_fname", "db_datas")
    def _compute_datas(self):
        for label in self:
            values = label.attachment_id._data_get("datas", None)
            label.datas = values.get(label.id)

    def _inverse_datas(self):
        # override in order to store files that need fast access,
        # we keep them in the database instead of the object storage
        for label in self:
            location = label.attachment_id._storage()
            if (
                location == label.attachment_id._get_stores()
                and self.attachment_id._save_in_db_anyway()
            ):
                # compute the fields that depend on datas
                value = label.datas
                bin_data = value and value.decode("base64") or ""
                vals = {
                    "file_size": len(bin_data),
                    "checksum": self.attachment_id._compute_checksum(bin_data),
                    "db_datas": value,
                    # we seriously don't need index content on those fields
                    "index_content": False,
                    "store_fname": False,
                }
                fname = label.store_fname
                # write as superuser, as user probably does not
                # have write access
                super(ShippingLabel, label.sudo()).write(vals)
                if fname:
                    self.attachment_id._file_delete(fname)
                continue
            self.attachment_id._data_set("datas", label.datas, None)
