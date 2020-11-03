# Copyright 2017-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
import inspect
import logging
import os
import time

import psycopg2
import odoo

from contextlib import closing, contextmanager
from odoo import api, exceptions, models, _
from odoo.osv.expression import AND, OR, normalize_domain
from odoo.tools.safe_eval import const_eval


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


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _register_hook(self):
        super()._register_hook()
        location = self.env.context.get('storage_location') or self._storage()
        # ignore if we are not using an object storage
        if location not in self._get_stores():
            return
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 2)
        # the caller of _register_hook is 'load_modules' in
        # odoo/modules/loading.py
        load_modules_frame = calframe[1][0]
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
            self.env['ir.attachment'].sudo()._force_storage_to_object_storage()

    @property
    def _object_storage_default_force_db_config(self):
        return {"image/": 51200, "application/javascript": 0, "text/css": 0}

    def _get_storage_force_db_config(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'ir_attachment.storage.force.database',
        )
        storage_config = None
        if param:
            try:
                storage_config = const_eval(param)
            except (SyntaxError, TypeError, ValueError):
                _logger.exception(
                    "Could not parse system parameter"
                    " 'ir_attachment.storage.force.database', reverting to the"
                    " default configuration.")

        if not storage_config:
            storage_config = self._object_storage_default_force_db_config
        return storage_config

    def _store_in_db_instead_of_object_storage_domain(self):
        """Return a domain for attachments that must be forced to DB

        Read the docstring of ``_store_in_db_instead_of_object_storage`` for
        more details.

        Used in ``force_storage_to_db_for_special_fields`` to find records
        to move from the object storage to the database.

        The domain must be inline with the conditions in
        ``_store_in_db_instead_of_object_storage``.
        """
        domain = []
        storage_config = self._get_storage_force_db_config()
        for mimetype_key, limit in storage_config.items():
            part = [("mimetype", "=like", "{}%".format(mimetype_key))]
            if limit:
                part = AND([part, [("file_size", "<=", limit)]])
            domain = OR([domain, part])
        return domain

    def _store_in_db_instead_of_object_storage(self, data, mimetype):
        """ Return whether an attachment must be stored in db

        When we are using an Object Storage. This is sometimes required
        because the object storage is slower than the database/filesystem.

        Small images (128, 256) are used in Odoo in list / kanban views. We
        want them to be fast to read.
        They are generally < 50KB (default configuration) so they don't take
        that much space in database, but they'll be read much faster than from
        the object storage.

        The assets (application/javascript, text/css) are stored in database
        as well whatever their size is:

        * a database doesn't have thousands of them
        * of course better for performance
        * better portability of a database: when replicating a production
          instance for dev, the assets are included

        The configuration can be modified in the ir.config_parameter
        ``ir_attachment.storage.force.database``, as a dictionary, for
        instance::

            {"image/": 51200, "application/javascript": 0, "text/css": 0}

        Where the key is the beginning of the mimetype to configure and the
        value is the limit in size below which attachments are kept in DB.
        0 means no limit.

        Default configuration means:

        * images mimetypes (image/png, image/jpeg, ...) below 51200 bytes are
          stored in database
        * application/javascript are stored in database whatever their size
        * text/css are stored in database whatever their size

        The conditions must be inline with the domain in
        ``_store_in_db_instead_of_object_storage_domain``.

        """
        storage_config = self._get_storage_force_db_config()
        for mimetype_key, limit in storage_config.items():
            if mimetype.startswith(mimetype_key):
                if not limit:
                    return True
                bin_data = base64.b64decode(data) if data else b''
                return len(bin_data) <= limit
        return False

    def _get_datas_related_values(self, data, mimetype):
        storage = self.env.context.get('storage_location') or self._storage()
        if data and storage in self._get_stores():
            if self._store_in_db_instead_of_object_storage(data, mimetype):
                # compute the fields that depend on datas
                bin_data = base64.b64decode(data) if data else b''
                values = {
                    'file_size': len(bin_data),
                    'checksum': self._compute_checksum(bin_data),
                    'index_content': self._index(bin_data, mimetype),
                    'store_fname': False,
                    'db_datas': data,
                }
                return values
        return super()._get_datas_related_values(data, mimetype)

    @api.model
    def _file_read(self, fname):
        if self._is_file_from_a_store(fname):
            return self._store_file_read(fname)
        else:
            return super()._file_read(fname)

    def _store_file_read(self, fname):
        storage = fname.partition('://')[0]
        raise NotImplementedError(
            'No implementation for %s' % (storage,)
        )

    def _store_file_write(self, key, bin_data):
        raise NotImplementedError(
            'No implementation for %s' % (self.storage(),)
        )

    def _store_file_delete(self, fname):
        storage = fname.partition('://')[0]
        raise NotImplementedError(
            'No implementation for %s' % (storage,)
        )

    @api.model
    def _file_write(self, bin_data, checksum):
        location = self.env.context.get('storage_location') or self._storage()
        if location in self._get_stores():
            key = self.env.context.get('force_storage_key')
            if not key:
                key = self._compute_checksum(bin_data)
            filename = self._store_file_write(key, bin_data)
        else:
            filename = super()._file_write(bin_data, checksum)
        return filename

    @api.model
    def _file_delete(self, fname):
        if self._is_file_from_a_store(fname):
            cr = self.env.cr
            # using SQL to include files hidden through unlink or due to record
            # rules
            cr.execute("SELECT COUNT(*) FROM ir_attachment "
                       "WHERE store_fname = %s", (fname,))
            count = cr.fetchone()[0]
            if not count:
                self._store_file_delete(fname)
        else:
            super()._file_delete(fname)

    @api.model
    def _is_file_from_a_store(self, fname):
        for store_name in self._get_stores():
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
                registry = odoo.modules.registry.Registry.new(
                    self.env.cr.dbname
                )
                with closing(registry.cursor()) as cr:
                    try:
                        yield self.env(cr=cr)
                    except Exception:
                        cr.rollback()
                        raise
                    else:
                        # disable pylint error because this is a valid commit,
                        # we are in a new env
                        cr.commit()  # pylint: disable=invalid-commit
            else:
                # make a copy
                yield self.env()

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
            return self._full_path(fname)
        elif self.db_datas:
            _logger.info('moving on the object storage from database')
            self.write({'datas': self.datas})

    @api.model
    def force_storage(self):
        if not self.env['res.users'].browse(self.env.uid)._is_admin():
            raise exceptions.AccessError(
                _('Only administrators can execute this action.'))
        location = self.env.context.get('storage_location') or self._storage()
        if location not in self._get_stores():
            return super().force_storage()
        self._force_storage_to_object_storage()

    @api.model
    def force_storage_to_db_for_special_fields(self, new_cr=False):
        """Migrate special attachments from Object Storage back to database

        The access to a file stored on the objects storage is slower
        than a local disk or database access. For attachments like
        image_small that are accessed in batch for kanban views, this
        is too slow. We store this type of attachment in the database.

        This method can be used when migrating a filestore where all the files,
        including the special files (assets, image_small, ...) have been pushed
        to the Object Storage and we want to write them back in the database.

        It is not called anywhere, but can be called by RPC or scripts.
        """
        storage = self._storage()
        if storage not in self._get_stores():
            return

        domain = AND((
            normalize_domain(
                [('store_fname', '=like', '{}://%'.format(storage)),
                 # for res_field, see comment in
                 # _force_storage_to_object_storage
                 '|',
                 ('res_field', '=', False),
                 ('res_field', '!=', False),
                 ]
            ),
            normalize_domain(self._store_in_db_instead_of_object_storage_domain())
        ))

        with self.do_in_new_env(new_cr=new_cr) as new_env:
            model_env = new_env['ir.attachment'].with_context(
                prefetch_fields=False
            )
            attachment_ids = model_env.search(domain).ids
            if not attachment_ids:
                return
            total = len(attachment_ids)
            start_time = time.time()
            _logger.info('Moving %d attachments from %s to'
                         ' DB for fast access', total, storage)
            current = 0
            for attachment_id in attachment_ids:
                current += 1
                # if we browse attachments outside of the loop, the first
                # access to 'datas' will compute all the 'datas' fields at
                # once, which means reading hundreds or thousands of files at
                # once, exhausting memory
                attachment = model_env.browse(attachment_id)
                # this write will read the datas from the Object Storage and
                # write them back in the DB (the logic for location to write is
                # in the 'datas' inverse computed field)
                attachment.write({'datas': attachment.datas})
                # as the file will potentially be dropped on the bucket,
                # we should commit the changes here
                new_env.cr.commit()
                if current % 100 == 0 or total - current == 0:
                    _logger.info(
                        'attachment %s/%s after %.2fs',
                        current, total,
                        time.time() - start_time
                    )

    @api.model
    def _force_storage_to_object_storage(self, new_cr=False):
        _logger.info('migrating files to the object storage')
        storage = self.env.context.get('storage_location') or self._storage()
        # The weird "res_field = False OR res_field != False" domain
        # is required! It's because of an override of _search in ir.attachment
        # which adds ('res_field', '=', False) when the domain does not
        # contain 'res_field'.
        # https://github.com/odoo/odoo/blob/9032617120138848c63b3cfa5d1913c5e5ad76db/odoo/addons/base/ir/ir_attachment.py#L344-L347
        domain = ['!', ('store_fname', '=like', '{}://%'.format(storage)),
                  '|',
                  ('res_field', '=', False),
                  ('res_field', '!=', False)]
        # We do a copy of the environment so we can workaround the cache issue
        # below. We do not create a new cursor by default because it causes
        # serialization issues due to concurrent updates on attachments during
        # the installation
        with self.do_in_new_env(new_cr=new_cr) as new_env:
            model_env = new_env['ir.attachment']
            ids = model_env.search(domain).ids
            files_to_clean = []
            for attachment_id in ids:
                try:
                    with new_env.cr.savepoint():
                        # check that no other transaction has
                        # locked the row, don't send a file to storage
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
                        path = attachment._move_attachment_to_store()
                        if path:
                            files_to_clean.append(path)
                except psycopg2.OperationalError:
                    _logger.error('Could not migrate attachment %s to S3',
                                  attachment_id)

            def clean():
                clean_fs(files_to_clean)

            # delete the files from the filesystem once we know the changes
            # have been committed in ir.attachment
            if files_to_clean:
                new_env.cr.after('commit', clean)

    def _get_stores(self):
        """ To get the list of stores activated in the system  """
        return []
