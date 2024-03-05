# -*- coding: utf-8 -*-
# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import hashlib
import inspect
import logging
import os
import psycopg2

from openerp import _
from openerp.osv import osv
from openerp.osv.orm import except_orm
from openerp import SUPERUSER_ID


_logger = logging.getLogger(__name__)


def clean_fs(files):
    _logger.info('cleaning old files from filestore')
    for full_path in files:
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


class IrAttachment(osv.osv):
    _inherit = 'ir.attachment'

    @staticmethod
    def _compute_checksum(bin_data):
        """ compute the checksum for the given datas
            :param bin_data : datas in its binary form
        """
        # an empty file has a checksum too (for caching)
        return hashlib.sha1(bin_data or '').hexdigest()

    def _is_user_admin(self, cr, uid):
        if uid == SUPERUSER_ID:
            return True
        else:
            return self.pool.get('res.users').has_group(
                cr, uid, 'base.group_erp_manager'
            )

    def _register_hook(self, cr):
        super(IrAttachment, self)._register_hook(cr)
        # ignore if we are not using an object storage
        # Use directly SUPERUSER_ID
        # because the uid parameter is required
        # in function _storage and
        # the SUPERUSER_ID is used directly instead of use the uid parameter.
        if self._storage(cr, SUPERUSER_ID) not in self._get_stores():
            return
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        # the caller of _register_hook is 'load_modules' in
        # odoo/modules/loading.py
        # We have to go up 2 stacks because of the old api wrapper
        load_modules_frame = calframe[2][0]
        # 'update_module' is an argument that 'load_modules' receives with a
        # True-ish value meaning that an install or upgrade of addon has been
        # done during the initialization. We need to move the attachments that
        # could have been created or updated in other addons before this addon
        # was loaded
        update_module = load_modules_frame.f_locals.get('update_module')

        # We need to call the migration on the loading of the model because
        # when we are upgrading addons, some of them might add attachments.
        # To be sure they are migrated to the storage we need to call the
        # migration here.
        # Typical example is images of ir.ui.menu which are updated in
        # ir.attachment at every upgrade of the addons
        if update_module:
            self.pool.get('ir.attachment')._force_storage_to_object_storage(
                cr, SUPERUSER_ID
            )

    def _save_in_db_anyway(self, cr, uid, ids, context=None):
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
        assert (isinstance(ids, int) or
                len(ids) == 1), 'Expecting only one record'
        rec = self.browse(cr, uid, ids, context=context)

        # assets
        if rec.res_model == 'ir.ui.view':
            # assets are stored in 'ir.ui.view'
            return True

        return False

    def _data_set(self, cr, uid, id, name, value, arg, context=None):
        # override in order to store files that need fast access,
        # we keep them in the database instead of the object storage
        location = self._storage(cr, uid)
        for attach in self.browse(cr, uid, id, context):
            if (location in self._get_stores() and
                    self._save_in_db_anyway(cr, uid, [id], context)):
                # compute the fields that depend on datas
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
                super(IrAttachment, self).write(
                    cr, SUPERUSER_ID, id, vals, context
                )
                if fname:
                    self._file_delete(cr, uid, fname)
                continue
            self._data_set(cr, uid, id, 'datas', value, None, context)

    def _store_file_read(self, fname, bin_size=False):
        storage = fname.partition('://')[0]
        raise NotImplementedError(
            'No implementation for %s' % (storage,)
        )

    def _store_file_write(self, storage, key, bin_data):
        raise NotImplementedError(
            'No implementation for %s' % (storage,)
        )

    def _store_file_delete(self, fname):
        storage = fname.partition('://')[0]
        raise NotImplementedError(
            'No implementation for %s' % (storage,)
        )

    def _file_read(self, cr, uid, fname, bin_size=False):
        if self._is_file_from_a_store(fname):
            return self._store_file_read(fname, bin_size=bin_size)
        else:
            _super = super(IrAttachment, self)
            return _super._file_read(cr, uid, fname, bin_size=bin_size)

    def _file_write(self, cr, uid, value):
        storage = self._storage(cr, uid)
        if storage in self._get_stores():
            bin_data = value.decode('base64')
            key = self._compute_checksum(bin_data)
            filename = self._store_file_write(storage, key, bin_data)
        else:
            _super = super(IrAttachment, self)
            filename = _super._file_write(cr, uid, value)
        return filename

    def _file_delete(self, cr, uid, fname):
        if self._is_file_from_a_store(fname):
            # using SQL to include files hidden through unlink or due to record
            # rules
            cr.execute("SELECT COUNT(*) FROM ir_attachment "
                       "WHERE store_fname = %s", (fname,))
            count = cr.fetchone()[0]
            if not count:
                self._store_file_delete(fname)
        else:
            super(IrAttachment, self)._file_delete(cr, uid, fname)

    def _is_file_from_a_store(self, fname):
        for store_name in self._get_stores():
            uri = '{}://'.format(store_name)
            if fname.startswith(uri):
                return True
        return False

    def _move_attachment_to_store(self, cr, uid, ids, context=None):
        assert (isinstance(ids, int) or
                len(ids) == 1), 'Expecting only one record'
        rec = self.browse(cr, uid, ids, context)
        _logger.info('inspecting attachment %s (%d)', rec.name, rec.id)
        fname = rec.store_fname
        if fname:
            # migrating from filesystem filestore
            # or from the old 'store_fname' without the bucket name
            _logger.info('moving %s on the object storage', fname)
            self.write(cr, uid, ids, {'datas': rec.datas}, context)
            _logger.info('moved %s on the object storage', fname)
            return self._full_path(cr, uid, fname)
        elif rec.db_datas:
            _logger.info('moving on the object storage from database')
            self.write(cr, uid, ids, {'datas': rec.datas}, context)

    def force_storage(self, cr, uid, context=None):
        if not self._is_user_admin(cr, uid):
            raise except_orm(
                _('Error'),
                _('Only administrators can execute this action.')
            )
        storage = self._storage(cr, uid)
        if storage not in self._get_stores():
            return super(IrAttachment, self).force_storage(cr, uid, context)
        self._force_storage_to_object_storage(cr, uid, context)

    def _force_storage_to_object_storage(self, cr, uid, context=None):
        _logger.info('migrating files to the object storage')
        storage = self._storage(cr, uid)

        domain = [('store_fname', 'not like', '{}://%'.format(storage))]

        ids = self.search(cr, uid, domain, context=context)
        files_to_clean = []
        for attachment_id in ids:
            try:
                with cr.savepoint():
                    # check that no other transaction has
                    # locked the row, don't send a file to storage
                    # in that case
                    cr.execute(
                        "SELECT id "
                        "FROM ir_attachment "
                        "WHERE id = %s "
                        "FOR UPDATE NOWAIT",
                        (attachment_id,),
                        log_exceptions=False
                    )

                    path = self._move_attachment_to_store(
                        cr, uid, attachment_id, context
                    )
                    if path:
                        files_to_clean.append(path)
            except psycopg2.OperationalError:
                _logger.error('Could not migrate attachment %s to %s' %
                              (attachment_id, storage))

        clean_filesystem = os.environ.get('ODOO_ADDON_BASE_ATTACHMENT_OBJECT_STORAGE_CLEAN_FILESYSTEM', False) in ("True", "true", True)
        # delete the files from the filesystem
        if files_to_clean and clean_filesystem:
            clean_fs(files_to_clean)

    def _get_stores(self):
        """ To get the list of stores activated in the system  """
        return []
