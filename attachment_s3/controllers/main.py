# Copyright 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os

import odoo
from odoo import SUPERUSER_ID, exceptions, http

from odoo.addons.web.controllers.database import Database as WebDatabase

from ..s3uri import S3Uri

_logger = logging.getLogger(__name__)


def _env_flag(name):
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


class Database(WebDatabase):
    @http.route()
    def drop(self, master_pwd, name):
        res = super().drop(master_pwd, name)
        if not _env_flag("AWS_EMPTY_ON_DBDROP"):
            return res
        try:
            bucket_name = (os.environ.get("AWS_BUCKETNAME") or "").format(db=name)
            if not bucket_name:
                return res
            other_dbs = [db for db in (http.db_list() or []) if db != name]
            if not other_dbs:
                _logger.warning(
                    "Cannot empty S3 bucket %s: no remaining database to open a registry",
                    bucket_name,
                )
                return res
            with odoo.modules.registry.Registry(other_dbs[0]).cursor() as cr:
                env = odoo.api.Environment(cr, SUPERUSER_ID, {})
                env["ir.attachment"]._get_s3_bucket(bucket_name).objects.all().delete()
        except exceptions.UserError:
            _logger.exception("Error deleting attachments in object storage.")
        return res

    @http.route()
    def duplicate(self, master_pwd, name, new_name, neutralize_database=False):
        res = super().duplicate(
            master_pwd, name, new_name, neutralize_database=neutralize_database
        )
        if not _env_flag("AWS_DUPLICATE"):
            return res
        try:
            bucket_to_copy = (os.environ.get("AWS_BUCKETNAME") or "").format(db=name)
            new_bucket_name = (os.environ.get("AWS_BUCKETNAME") or "").format(
                db=new_name
            )
            if not (bucket_to_copy and new_bucket_name):
                return res
            with odoo.modules.registry.Registry(name).cursor() as cr:
                env = odoo.api.Environment(cr, SUPERUSER_ID, {})
                dst = env["ir.attachment"]._get_s3_bucket(new_bucket_name)
                files = env["ir.attachment"].sudo().search(
                    [("store_fname", "=like", "s3://%")]
                )
                for attachment in files:
                    key = S3Uri(attachment.store_fname).item()
                    dst.copy({"Bucket": bucket_to_copy, "Key": key}, key)
            with odoo.modules.registry.Registry(new_name).cursor() as cr:
                env = odoo.api.Environment(cr, SUPERUSER_ID, {})
                env.cr.execute(
                    """
                    UPDATE ir_attachment
                       SET store_fname = REPLACE(store_fname, %s, %s)
                     WHERE store_fname LIKE 's3://%%'
                    """,
                    (bucket_to_copy, new_bucket_name),
                )
        except exceptions.UserError:
            _logger.exception("Error writing attachments to object storage.")
        return res

    @http.route()
    def restore(
        self, master_pwd, backup_file, name, copy=False, neutralize_database=False
    ):
        res = super().restore(
            master_pwd,
            backup_file,
            name,
            copy=copy,
            neutralize_database=neutralize_database,
        )
        if not os.environ.get("AWS_BUCKETNAME"):
            return res
        try:
            with odoo.modules.registry.Registry(name).cursor() as cr:
                env = odoo.api.Environment(cr, SUPERUSER_ID, {})
                env["ir.attachment"]._get_s3_bucket(
                    os.environ["AWS_BUCKETNAME"].format(db=name)
                )
                env["ir.config_parameter"].set_param("ir_attachment.location", "s3")
                env["ir.attachment"].force_storage()
        except exceptions.UserError:
            _logger.exception("Error writing attachments to object storage.")
        return res
