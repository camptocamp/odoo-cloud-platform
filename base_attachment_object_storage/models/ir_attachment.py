# -*- coding: utf-8 -*-
# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


import logging
import os
import psycopg2
import odoo

from contextlib import closing, contextmanager
from odoo import api, exceptions, models, _


_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    store_types = ['s3', 'swift']

    @api.multi
    def _save_in_db_anyway(self):
        """ Return whether an attachment must be stored in db

        When we are using an Object Store. This is sometimes required
        because the object storage is slower than the database/filesystem.

        We store image_small and image_medium from 'Binary' fields
        because they should be fast to read as they are often displayed
        in kanbans / lists. The same for web_icon_data.

        We store the assets locally as well. Not only for performance,
        but also because it improves the portability of the database:
        when assets are invalidated, they are deleted so we don't have
        an old database with attachments pointing to deleted assets.

        """
        self.ensure_one()

        # assets
        if self.res_model == 'ir.ui.view':
            # assets are stored in 'ir.ui.view'
            return True

        # Binary fields
        if self.res_field:
            # Binary fields are stored with the name of the field in
            # 'res_field'
            local_fields = ('image_small', 'image_medium', 'web_icon_data')
            # 'image' fields can be rather large and should usually
            # not be requests in bulk in lists
            if self.res_field and self.res_field in local_fields:
                return True
        return False

    def _inverse_datas(self):
        # override in order to store files that need fast access,
        # we keep them in the database instead of the object storage
        location = self._storage()
        for attach in self:
            if location in self.store_types and self._save_in_db_anyway():
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
                super(IrAttachment, attach.sudo()).write(vals)
                if fname:
                    self._file_delete(fname)
                continue
            super(IrAttachment, attach)._inverse_datas()

    @api.model
    def _file_read(self, fname, bin_size=False):
        if self._is_file_from_a_store(fname):
            return self._store_file_read(fname, bin_size=bin_size)
        else:
            _super = super(IrAttachment, self)
            return _super._file_read(fname, bin_size=bin_size)

    @api.model
    def _file_write(self, value, checksum):
        if self._storage() in self.store_types:
            filename = self._store_file_write(value, checksum)
        else:
            filename = super(IrAttachment, self)._file_write(value, checksum)
        return filename

    @api.model
    def _file_delete(self, fname):
        if self._is_file_from_a_store(fname):
            cr = self.env.cr
            cr.execute("SELECT COUNT(*) FROM ir_attachment "
                       "WHERE store_fname = %s", (fname,))
            count = cr.fetchone()[0]
            if not count:
                self._file_delete_from_store(fname)
        else:
            super(IrAttachment, self)._file_delete(fname)

    def _is_file_from_a_store(self, fname):
        for store_name in self.store_types:
            uri = '{}://'.format(store_name)
            if fname.startswith(uri):
                return True
        return False

    @contextmanager
    def do_in_new_env(self, new_cr=False):
        """ Context manager that yields a new environment

        Using a new Odoo Environment thus a new PG transaction.
        """
        with api.Environment.manage():
            if new_cr:
                registry = odoo.modules.registry.RegistryManager.get(
                    self.env.cr.dbname
                )
                with closing(registry.cursor()) as cr:
                    try:
                        yield self.env(cr=cr)
                    except:
                        cr.rollback()
                        raise
                    else:
                        # disable pylint error because this is a valid commit,
                        # we are in a new env
                        cr.commit()  # pylint: disable=invalid-commit
            else:
                # make a copy
                yield self.env()

    @api.multi
    def _move_attachment_to_store(self):
        self.ensure_one()
        _logger.info('inspecting attachment %s (%d)', self.name, self.id)
        fname = self.store_fname
        if fname:
            # migrating from filesystem filestore
            # or from the old 'store_fname' without the bucket name
            _logger.info('moving %s on the object storage', fname)
            self.write({'datas': self.datas,
                        # this is required otherwise the
                        # mimetype gets overriden with
                        # 'application/octet-stream'
                        # on assets
                        'mimetype': self.mimetype})
            _logger.info('moved %s on the object storage', fname)
            full_path = self._full_path(fname)
            _logger.info('cleaning fs self')
            if os.path.exists(full_path):
                try:
                    os.unlink(full_path)
                except OSError:
                    _logger.info(
                        "_file_delete could not unlink %s",
                        full_path, exc_info=True
                    )
                except IOError:
                    # Harmless and needed for race conditions
                    _logger.info(
                        "_file_delete could not unlink %s",
                        full_path, exc_info=True
                    )
        elif self.db_datas:
            _logger.info('moving on the object storage from database')
            self.write({'datas': self.datas})

    @api.model
    def force_storage(self):
        if not self.env['res.users'].browse(self.env.uid)._is_admin():
            raise exceptions.AccessError(
                _('Only administrators can execute this action.')
            )
        storage = self._storage()
        if storage in self.store_types:
            _logger.info('migrating files to the object storage')
            domain = ['!', ('store_fname', '=like', '{}://%'.format(storage)),
                      '|',
                      ('res_field', '=', False),
                      ('res_field', '!=', False)]
            # We do a copy of the environment so we can workaround the
            # cache issue below. We do not create a new cursor because
            # it causes serialization issues due to concurrent updates on
            # attachments during the installation
            with self.do_in_new_env() as new_env:
                model_env = new_env['ir.attachment']
                ids = model_env.search(domain).ids
                for attachment_id in ids:
                    try:
                        with new_env.cr.savepoint():
                            # check that no other transaction has
                            # locked the row, don't send a file to S3
                            # in that case
                            self.env.cr.execute("SELECT id "
                                                "FROM ir_attachment "
                                                "WHERE id = %s "
                                                "FOR UPDATE NOWAIT",
                                                (attachment_id,),
                                                log_exceptions=False)

                            # This is a trick to avoid having the 'datas'
                            # function fields computed for every attachment on
                            # each iteration of the loop. The former issue
                            # being that it reads the content of the file of
                            # ALL the attachments on each loop.
                            new_env.clear()
                            attachment = model_env.browse(attachment_id)
                            attachment._move_attachment_to_store()
                    except psycopg2.OperationalError:
                        _logger.error('Could not migrate attachment %s to S3',
                                      attachment_id)
        else:
            return super(IrAttachment, self).force_storage()

    def _get_stores(self):
        """ To get the list of stores activated in the system  """
        return []
