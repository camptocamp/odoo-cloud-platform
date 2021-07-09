# Copyright (c) 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import logging
import os

import odoo
from odoo import SUPERUSER_ID
from odoo.addons.web.controllers.main import Database
from odoo import http
from odoo import exceptions
from odoo.http import request
from ..s3uri import S3Uri

_logger = logging.getLogger(__name__)


class Database(Database):
    @http.route()
    def drop(self, master_pwd, name):
        res = super().drop(master_pwd, name)
        empty = os.environ.get("AWS_EMPTY_ON_DBDROP", False)
        if empty:
            try:
                bucket = os.environ.get("AWS_BUCKETNAME").format(db=name)
                bucket = request.env["ir.attachment"]._get_s3_bucket(bucket)
                bucket.objects.all().delete()
            except exceptions.UserError:
                _logger.exception("Error deleting attachments in object storage.")
        return res

    @http.route()
    def duplicate(self, master_pwd, name, new_name):
        res = super().duplicate(master_pwd, name, new_name)
        duplicate = os.environ.get("AWS_DUPLICATE", False)
        if duplicate:
            try:
                bucket_to_copy = os.environ.get("AWS_BUCKETNAME").format(db=name)
                new_bucket_name = os.environ.get("AWS_BUCKETNAME").format(db=new_name)
                dst = request.env["ir.attachment"]._get_s3_bucket(new_bucket_name)
                files = (
                    request.env["ir.attachment"].sudo().search([
                        ("db_datas", "=", False)
                    ])
                )
                for file in files:
                    key = S3Uri(file.store_fname).item()
                    copy_source = {"Bucket": bucket_to_copy, "Key": key}
                    dst.copy(copy_source, key)
                sql = """UPDATE ir_attachment AS t SET store_fname = s.store_fname FROM (
                        SELECT id, REPLACE(store_fname, '%s', '%s')
                        AS store_fname FROM ir_attachment WHERE db_datas is NULL
                    ) AS s(id,store_fname) where t.id = s.id;
                """ % (bucket_to_copy, new_bucket_name)
                registry = odoo.modules.registry.Registry.new(new_name)
                with registry.cursor() as cr:
                    env = odoo.api.Environment(cr, SUPERUSER_ID, {})
                    env.cr.execute(sql)
            except exceptions.UserError:
                _logger.exception("Error writing attachments to object storage.")
        return res

    @http.route()
    def restore(self, master_pwd, backup_file, name, copy=False):
        res = super().restore(master_pwd, backup_file, name, copy)
        try:
            new_bucket_name = os.environ.get("AWS_BUCKETNAME").format(db=name)
            request.env["ir.attachment"]._get_s3_bucket(new_bucket_name)
            request.env["ir.config_parameter"].sudo().create(
                {"key": "ir_attachment.location", "value": "s3"}
            )
            request.env["ir.attachment"].sudo().force_storage()
        except exceptions.UserError:
            _logger.exception("Error writing attachments to object storage.")
        return res
