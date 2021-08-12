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
        res = super().drop(master_pwd, name)
        delete = os.environ.get("AZURE_DELETE_ON_DBDROP", False)
        if delete:
            attachment_obj = request.env["ir.attachment"]
            try:
                container_name = attachment_obj._get_container_name()
                blob_service_client = attachment_obj._get_blob_service_client()
                container_client = blob_service_client.get_container_client(
                    container_name
                )
                container_client.delete_container()
            except exceptions.UserError:
                _logger.exception("Error deleting attachments from object storage.")
        return res

    @http.route()
    def duplicate(self, master_pwd, name, new_name):
        res = super().duplicate(master_pwd, name, new_name)
        duplicate = os.environ.get("AWS_DUPLICATE", False)
        if duplicate:
            attachment_obj = request.env["ir.attachment"]
            try:
                copy_from_container = attachment_obj._get_container_name()
                copy_to_container = attachment_obj._get_container_name(new_name)
                blob_service = attachment_obj._get_blob_service_client()
                container_client = blob_service.get_container_client(
                    copy_from_container
                )

                blobs_list = container_client.list_blobs()
                for blob in blobs_list:
                    blob_url = container_client.make_blob_url(
                        copy_from_container, blob.name
                    )
                    container_client.copy_blob(copy_to_container, blob.name, blob_url)
            except exceptions.UserError:
                _logger.exception("Error writing attachments to object storage.")
        return res

    @http.route()
    def restore(self, master_pwd, backup_file, name, copy=False):
        res = super().restore(master_pwd, backup_file, name, copy)
        attachment_obj = request.env["ir.attachment"]
        try:
            attachment_obj._get_azure_container()
            request.env["ir.config_parameter"].create(
                {"key": "ir_attachment.location", "value": "azure"}
            )
            attachment_obj.force_storage()
        except exceptions.UserError:
            _logger.exception("Error writing attachments to object storage.")
        return res
