import logging
import os

from odoo.addons.web.controllers.main import Database
from odoo import http
from odoo import exceptions
from odoo.http import request

_logger = logging.getLogger(__name__)


class Database(Database):
    @http.route()
    def drop(self, master_pwd, name):
        delete_on_drop = os.environ.get("AWS_DELETE_ON_DBDROP", False)
        if not delete_on_drop:
            return super(Database, self).drop(master_pwd, name)
        try:
            bucket = request.env["ir.attachment"]._get_s3_bucket()
            bucket.objects.all().delete()
            s3_resource = request.env["ir.attachment"]._get_s3_client()
            s3_resource.delete_bucket(
                Bucket=bucket.name,
            )
            return super(Database, self).drop(master_pwd, name)
        except exceptions.UserError:
            _logger.exception("error reading attachment from object storage")
            return super(Database, self).drop(master_pwd, name)

    @http.route()
    def duplicate(self, master_pwd, name, new_name):
        response = super(Database, self).duplicate(master_pwd, name, new_name)
        try:
            s3_resource = request.env["ir.attachment"]._get_s3_client()
            bucket_to_copy = request.env["ir.attachment"]._get_s3_bucket()
            new_bucket_name = request.env["ir.attachment"]._get_s3_bucket(new_name)
            new_bucket_name = new_bucket_name.name
            bucket_to_copy = bucket_to_copy.name
            sql = ("""
                UPDATE ir_attachment AS t SET store_fname = s.store_fname FROM (
                    SELECT
                        id,
                        REPLACE(store_fname, '/*%s*/', '%s')
                    AS store_fname FROM ir_attachment WHERE db_datas is NULL)
                AS s(id,store_fname) where t.id = s.id;
            """ (bucket_to_copy, new_bucket_name,))
            request.env.cr.execute(sql)
            for key in s3_resource.list_objects(Bucket=bucket_to_copy)["Contents"]:
                files = key["Key"]
                copy_source = {"Bucket": bucket_to_copy, "Key": files}
                s3_resource.meta.client.copy(copy_source, new_bucket_name, files)

            return response
        except exceptions.UserError:
            _logger.exception("Error reading attachments from object storage.")
            return response
