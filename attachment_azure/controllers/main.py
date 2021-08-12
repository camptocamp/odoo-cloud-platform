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
        attachment_obj = request.env["ir.attachment"]
        try:
            container_name = attachment_obj._get_container_name()
            blob_service_client = attachment_obj._get_blob_service_client()
            container_client = blob_service_client.get_container_client(container_name)
            container_client.delete_container()
            return super(Database, self).drop(master_pwd, name)
        except exceptions.UserError:
            _logger.exception("Error reading attachment from object storage")
            return super(Database, self).drop(master_pwd, name)

    @http.route()
    def duplicate(self, master_pwd, name, new_name):
        response = super(Database, self).duplicate(master_pwd, name, new_name)
        attachment_obj = request.env["ir.attachment"]
        try:

            copy_from_container = attachment_obj._get_container_name()
            copy_to_container = attachment_obj._get_container_name(new_name)
            blob_service = attachment_obj._get_blob_service_client()

            blobs_list = blob_service.list_blobs()
            for blob in blobs_list:
                blob_url = blob_service.make_blob_url(copy_from_container, blob.name)
                blob_service.copy_blob(copy_to_container, blob.name, blob_url)

            return response
        except exceptions.UserError:
            _logger.exception("error reading attachment from object storage")
            return response

    @http.route()
    def restore(self, master_pwd, backup_file, name, copy=False):
        res = super().restore(master_pwd, backup_file, name, copy)
        attachment_obj = request.env["ir.attachment"]
        try:
            attachment_obj._get_azure_container()
            attachment_obj.force_storage()
        except exceptions.UserError:
            _logger.exception("Error writing attachments to object storage.")
        return res
