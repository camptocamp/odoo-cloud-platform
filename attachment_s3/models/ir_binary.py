# Copyright 2016-2019 Camptocamp SA
# Copyright 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
from odoo import models
from odoo.http import Stream


class IrBinary(models.AbstractModel):
    _inherit = "ir.binary"
    _description = "File streaming helper model for controllers"

    def _s3_stream(self, attachment):
        # we will create or own tream and return it
        stream_data = self.env["ir.attachment"]._store_file_read(attachment.store_fname)
        s3stream = Stream(
            type="data",
            data=stream_data,
            path=None,
            url=None,
            mimetype=attachment.mimetype or None,
            download_name=attachment.name,
            size=len(stream_data),
            etag=attachment.checksum,
        )
        return s3stream

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
            record._name == "ir.attachment"
            and record.store_fname
            and record.store_fname.startswith("s3://")
        ):
            # we will create or own stream and return it
            return self._s3_stream(record)
        elif (
            record._name == "documents.document"
            and record.attachment_id
            and record.attachment_id.store_fname
            and record.attachment_id.store_fname.startswith("s3://")
        ):
            return self._s3_stream(record.attachment_id)

        else:
            return super()._record_to_stream(record, field_name)


# This part is used if the customer install tne enterprise module documents
try:
    from odoo.addons import documents

    documents.models.ir_binary.IrBinary._record_to_stream = IrBinary._record_to_stream
except ImportError:
    # document enterprise module if not installed, we just ignore
    pass
