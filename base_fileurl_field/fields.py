# Copyright 2012-2019 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
import unicodedata

from odoo import fields


fields.Field.__doc__ += """

        .. _field-fileurl:

        .. rubric:: FileURL fields

        FileURL fields is intended to store Binary data on an external storage
         with the possibility to be accessed outside of odoo.

        :param storage_location: Required external storage that must be
         activated on the system (cf base_attachment_storage)

        :param storage_path: Path to be used as a prefix to the filename in the
         storage solution (must be used with filename)

        :param filename: Field on the same model which stores the filename.
         Will be used to set fname on ir.attachment and, if storage_path is
         defined, will be passed to force the storage key.
"""


class FileURL(fields.Binary):

    _slots = {
        'attachment': True,  # Override default with True
        'storage_location': '',  # External storage activated on the system (cf base_attachment_storage)  # noqa
        'storage_path': '',  # Path to be used as storage key (prefix of filename)  # noqa
        'filename': '',  # Field to use to store the filename on ir.attachment
    }

    def create(self, record_values):
        assert self.attachment
        if not record_values:
            return
        # create the attachments that store the values
        env = record_values[0][0].env
        with env.norecompute():
            for record, value in record_values:
                if not value:
                    continue
                vals = {
                    'name': self.name,
                    'res_model': self.model_name,
                    'res_field': self.name,
                    'res_id': record.id,
                    'type': 'binary',
                    'datas': value,
                }
                fname = False
                if self.filename:
                    fname = record[self.filename]
                    vals['datas_fname'] = fname
                    if fname and self.storage_path:
                        storage_key = self._build_storage_key(fname)
                if not fname:
                    storage_key = False
                env['ir.attachment'].sudo().with_context(
                    binary_field_real_user=env.user,
                    storage_location=self.storage_location,
                    force_storage_key=storage_key,
                ).create(vals)

    def write(self, records, value):
        for record in records:
            storage_key = False
            if self.filename:
                fname = record[self.filename]
                if fname and self.storage_path:
                    storage_key = self._build_storage_key(fname)
            super().write(
                records.with_context(
                    storage_location=self.storage_location,
                    force_storage_key=storage_key,
                ),
                value
            )
        return True

    def _setup_regular_base(self, model):
        super()._setup_regular_base(model)
        if self.storage_path:
            assert self.filename is not None, \
                "Field %s defines storage_path without filename" % self

    def _build_storage_key(self, filename):
        return '/'.join([
            self.storage_path.rstrip('/'),
            unicodedata.normalize('NFKC', filename)
        ])


fields.FileURL = FileURL
