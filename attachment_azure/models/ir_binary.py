# Copyright 2016-2019 Camptocamp SA
# Copyright 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
from odoo import models
from odoo.http import Stream


class IrBinary(models.AbstractModel):
    _inherit = "ir.binary"
    _description = "File streaming helper model for controllers"

    def _record_to_stream(self, record, field_name):
        """
        Low level method responsible for the actual conversion from a
        model record to a stream. This method is an extensible hook for
        other modules. It is not meant to be directly called from
        outside or the ir.binary model.

        :param record: the record where to load the data from.
        :param str field_name: the binary field where to load the data
            from.
        :rtype: odoo.http.Stream
        """
        if (
            (record._name in ["ir.attachment", "documents.document"])
            and record.store_fname
            and record.store_fname.startswith("azure://")
        ):
            # we will create or own tream and return it
            stream_data = self.env["ir.attachment"]._store_file_read(record.store_fname)
            azurestream = Stream(
                type="data",
                data=stream_data,
                path=None,
                url=None,
                mimetype=record.mimetype or None,
                download_name=record.name,
                size=len(stream_data),
                etag=record.checksum,
            )
            return azurestream
        else:
            return super()._record_to_stream(record, field_name)
