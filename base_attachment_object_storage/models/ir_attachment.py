# Copyright 2017-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import inspect
import logging
import os
import time
from contextlib import contextmanager

import psycopg2

from odoo import _, api, models
from odoo.exceptions import AccessError
from odoo.fields import Domain
from odoo.http import Stream
from odoo.tools.safe_eval import const_eval

from .strtobool import strtobool

_logger = logging.getLogger(__name__)


def is_true(strval):
    return bool(strtobool(strval or "0"))


def clean_fs(files):
    _logger.info("cleaning old files from filestore")
    for full_path in files:
        if os.path.exists(full_path):
            try:
                os.unlink(full_path)
            except OSError:
                # Harmless and needed for race conditions
                _logger.info(
                    "_file_delete could not unlink %s", full_path, exc_info=True
                )


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @staticmethod
    def is_storage_disabled(storage=None, log=True):
        msg = _("Storages are disabled (see environment configuration).")
        if storage:
            msg = _("Storage '%s' is disabled (see environment configuration).") % (
                storage,
            )
        is_disabled = is_true(os.environ.get("DISABLE_ATTACHMENT_STORAGE"))
        if is_disabled and log:
            _logger.warning(msg)
        return is_disabled

    def _register_hook(self):
        super()._register_hook()
        location = self.env.context.get("storage_location") or self._storage()
        if location not in self._get_stores():
            return
        update_module = False
        frame = inspect.currentframe()
        try:
            while frame:
                if frame.f_code.co_name == "load_modules":
                    update_module = bool(frame.f_locals.get("update_module"))
                    break
                frame = frame.f_back
        finally:
            del frame
        if update_module:
            self.env["ir.attachment"].sudo()._force_storage_to_object_storage()

    @property
    def _object_storage_default_force_db_config(self):
        return {"image/": 51200, "application/javascript": 0, "text/css": 0}

    def _get_storage_force_db_config(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("ir_attachment.storage.force.database")
        )
        storage_config = None
        if param:
            try:
                storage_config = const_eval(param)
            except (SyntaxError, TypeError, ValueError):
                _logger.exception(
                    "Could not parse system parameter"
                    " 'ir_attachment.storage.force.database', reverting to the"
                    " default configuration."
                )
        if not storage_config:
            storage_config = self._object_storage_default_force_db_config
        return storage_config

    def _store_in_db_instead_of_object_storage_domain(self):
        """Return a domain for attachments that must be forced to DB."""
        domain = Domain.FALSE
        storage_config = self._get_storage_force_db_config()
        for mimetype_key, limit in storage_config.items():
            part = Domain("mimetype", "=like", f"{mimetype_key}%")
            if limit:
                part &= Domain("file_size", "<=", limit)
            domain |= part
        return domain

    def _store_in_db_instead_of_object_storage(self, data, mimetype):
        """Return whether an attachment must be stored in db when using object storage."""
        if self.is_storage_disabled():
            return True
        storage_config = self._get_storage_force_db_config()
        for mimetype_key, limit in storage_config.items():
            if mimetype.startswith(mimetype_key):
                if not limit:
                    return True
                return len(data) <= limit
        return False

    def _mark_checksum_stored_in_db(self, checksum):
        """Remember a checksum that must not be uploaded (see create/_file_write)."""
        db_only = self.env.context.get("_object_storage_db_checksums")
        if db_only is not None:
            db_only.add(checksum)

    def _get_datas_related_values(self, data, mimetype):
        # Odoo 19 sets store_fname via _get_path() and writes the file later
        # in create/_set_attachment_data. Object-store URIs must be decided
        # here; _get_path() only knows the local filestore.
        storage = self.env.context.get("storage_location") or self._storage()
        if data and storage in self._get_stores():
            checksum = self._compute_checksum(data)
            try:
                index_content = self._index(data, mimetype, checksum=checksum)
            except TypeError:
                index_content = self._index(data, mimetype)
            if self._store_in_db_instead_of_object_storage(data, mimetype):
                self._mark_checksum_stored_in_db(checksum)
                return {
                    "file_size": len(data),
                    "checksum": checksum,
                    "index_content": index_content,
                    "store_fname": False,
                    "db_datas": data,
                }
            key = self.env.context.get("force_storage_key") or checksum
            return {
                "file_size": len(data),
                "checksum": checksum,
                "index_content": index_content,
                "store_fname": f"{storage}://{key}",
                "db_datas": False,
            }
        return super()._get_datas_related_values(data, mimetype)

    def _with_object_storage_write_tracking(self):
        """Return self with a mutable set of checksums forced to the database.

        Core ``create`` / ``_set_attachment_data`` always call ``_file_write``
        when ``_storage() != 'db'``. Force-to-database attachments must skip
        that upload; the set is filled by ``_get_datas_related_values``.
        """
        if "_object_storage_db_checksums" in self.env.context:
            return self
        return self.with_context(_object_storage_db_checksums=set())

    @api.model_create_multi
    def create(self, vals_list):
        storage = self.env.context.get("storage_location") or self._storage()
        if storage not in self._get_stores():
            return super().create(vals_list)
        return super(IrAttachment, self._with_object_storage_write_tracking()).create(
            vals_list
        )

    def _set_attachment_data(self, asbytes):
        storage = self.env.context.get("storage_location") or self._storage()
        if storage not in self._get_stores():
            return super()._set_attachment_data(asbytes)
        return super(
            IrAttachment, self._with_object_storage_write_tracking()
        )._set_attachment_data(asbytes)

    @api.model
    def _file_read(self, fname, size=None):
        if self._is_file_from_a_store(fname):
            data = self._store_file_read(fname, size=size)
            if size is not None and data:
                return data[:size]
            return data
        return super()._file_read(fname, size=size)

    def _store_file_read(self, fname, size=None):
        storage = fname.partition("://")[0]
        raise NotImplementedError(f"No implementation for {storage}")

    def _store_file_write(self, key, bin_data):
        storage = self.env.context.get("storage_location") or self._storage()
        raise NotImplementedError(f"No implementation for {storage}")

    def _store_file_delete(self, fname):
        storage = fname.partition("://")[0]
        raise NotImplementedError(f"No implementation for {storage}")

    @api.model
    def _file_write(self, bin_data, checksum):
        location = self.env.context.get("storage_location") or self._storage()
        if location in self._get_stores():
            db_only = self.env.context.get("_object_storage_db_checksums")
            if db_only is not None and checksum in db_only:
                return False
            key = self.env.context.get("force_storage_key") or checksum
            return self._store_file_write(key, bin_data)
        return super()._file_write(bin_data, checksum)

    @api.model
    def _file_delete(self, fname):
        if self._is_file_from_a_store(fname):
            self.env.cr.execute(
                "SELECT COUNT(*) FROM ir_attachment WHERE store_fname = %s",
                (fname,),
            )
            count = self.env.cr.fetchone()[0]
            if not count:
                self._store_file_delete(fname)
            return
        return super()._file_delete(fname)

    @api.model
    def _is_file_from_a_store(self, fname):
        if not fname:
            return False
        for store_name in self._get_stores():
            if self.is_storage_disabled(store_name):
                continue
            if fname.startswith(f"{store_name}://"):
                return True
        return False

    def _to_http_stream(self):
        """Serve object-store files as in-memory data.

        Core ``_to_http_stream`` treats ``store_fname`` as a local path.
        ``s3://…`` / ``azure://…`` would raise if passed to ``os.stat``.
        """
        self.ensure_one()
        if self.store_fname and self._is_file_from_a_store(self.store_fname):
            data = self._file_read(self.store_fname) or b""
            return Stream(
                type="data",
                data=data,
                mimetype=self.mimetype,
                download_name=self.name,
                etag=self.checksum,
                last_modified=self.write_date,
                size=len(data),
                public=self.public,
            )
        return super()._to_http_stream()

    @contextmanager
    def do_in_new_env(self, new_cr=False):
        """Yield a new environment, optionally on a new cursor."""
        if new_cr:
            with self.env.registry.cursor() as cr:
                try:
                    yield self.env(cr=cr)
                except Exception:
                    cr.rollback()
                    raise
                else:
                    cr.commit()  # pylint: disable=invalid-commit
        else:
            yield self.env()

    def _move_attachment_to_store(self):
        self.ensure_one()
        _logger.info("inspecting attachment %s (%d)", self.name, self.id)
        fname = self.store_fname
        storage = fname.partition("://")[0] if fname else ""
        if self.is_storage_disabled(storage):
            fname = False
        if fname:
            _logger.info("moving %s on the object storage", fname)
            self.write(
                {
                    "raw": self.raw,
                    "mimetype": self.mimetype,
                }
            )
            _logger.info("moved %s on the object storage", fname)
            if self._is_file_from_a_store(fname):
                return False
            return self._full_path(fname)
        if self.db_datas:
            _logger.info("moving on the object storage from database")
            self.write({"raw": self.raw})
        return False

    @api.model
    def force_storage(self):
        if not self.env.is_admin():
            raise AccessError(_("Only administrators can execute this action."))
        location = self.env.context.get("storage_location") or self._storage()
        if location not in self._get_stores():
            return super().force_storage()
        self._force_storage_to_object_storage()

    @api.model
    def force_storage_to_db_for_special_fields(self, new_cr=False):
        """Migrate special attachments from object storage back to database."""
        storage = self._storage()
        if self.is_storage_disabled(storage):
            return
        if storage not in self._get_stores():
            return

        domain = (
            Domain("store_fname", "=like", f"{storage}://%")
            & Domain.OR(
                [
                    Domain("res_field", "=", False),
                    Domain("res_field", "!=", False),
                ]
            )
            & self._store_in_db_instead_of_object_storage_domain()
        )

        with self.do_in_new_env(new_cr=new_cr) as new_env:
            model_env = new_env["ir.attachment"].with_context(prefetch_fields=False)
            attachment_ids = model_env.search(domain).ids
            if not attachment_ids:
                return
            total = len(attachment_ids)
            start_time = time.time()
            _logger.info(
                "Moving %d attachments from %s to DB for fast access", total, storage
            )
            current = 0
            for attachment_id in attachment_ids:
                current += 1
                attachment = model_env.browse(attachment_id)
                attachment.write({"raw": attachment.raw})
                new_env.cr.commit()
                if current % 100 == 0 or total - current == 0:
                    _logger.info(
                        "attachment %s/%s after %.2fs",
                        current,
                        total,
                        time.time() - start_time,
                    )

    @api.model
    def _force_storage_to_object_storage(self, new_cr=False):
        _logger.info("migrating files to the object storage")
        storage = self.env.context.get("storage_location") or self._storage()
        if self.is_storage_disabled(storage):
            return
        # The weird "res_field = False OR res_field != False" domain is
        # required because ir.attachment._search adds ('res_field', '=', False)
        # when the domain does not mention res_field.
        domain = (~Domain("store_fname", "=like", f"{storage}://%")) & Domain.OR(
            [
                Domain("res_field", "=", False),
                Domain("res_field", "!=", False),
            ]
        )
        with self.do_in_new_env(new_cr=new_cr) as new_env:
            model_env = new_env["ir.attachment"]
            ids = model_env.search(domain).ids
            files_to_clean = []
            for attachment_id in ids:
                try:
                    with new_env.cr.savepoint():
                        self.env.cr.execute(
                            "SELECT id FROM ir_attachment WHERE id = %s FOR UPDATE NOWAIT",
                            (attachment_id,),
                            log_exceptions=False,
                        )
                        new_env.invalidate_all()
                        attachment = model_env.browse(attachment_id)
                        path = attachment._move_attachment_to_store()
                        if path:
                            files_to_clean.append(path)
                except psycopg2.OperationalError:
                    _logger.error(
                        "Could not migrate attachment %s to object storage",
                        attachment_id,
                    )

            if files_to_clean:
                new_env.cr.commit()
                clean_fs(files_to_clean)

    def _get_stores(self):
        """Return the list of object-store names activated in the system."""
        return []
