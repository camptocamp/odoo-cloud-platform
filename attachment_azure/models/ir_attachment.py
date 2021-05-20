# Copyright 2016-2019 Camptocamp SA
# Copyright 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import io
import logging
import os
from datetime import datetime, timedelta

from odoo import _, api, exceptions, models

_logger = logging.getLogger(__name__)

try:
    from azure.storage.blob import (
        BlobServiceClient,
        generate_account_sas,
        ResourceTypes,
        AccountSasPermissions,
    )
    from azure.core.exceptions import ResourceExistsError, HttpResponseError
except ImportError:
    _logger.debug("Cannot 'import azure-storage-blob'.")


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _get_stores(self):
        l = ["azure"]
        l += super(IrAttachment, self)._get_stores()
        return l

    @api.model
    def _get_blob_service_client(self):
        """Connect to Azure and return the blob service client

        The following environment variables must be set:
        * ``AZURE_STORAGE_CONNECTION_STRING``
        or
        * ``AZURE_STORAGE_ACCOUNT_NAME``
        * ``AZURE_STORAGE_ACCOUNT_URL``
        * ``AZURE_STORAGE_ACCOUNT_KEY``

        """
        connect_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        account_name = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
        account_url = os.environ.get("AZURE_STORAGE_ACCOUNT_URL")
        account_key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
        if not (connect_str or (account_name and account_url and account_key)):
            msg = _(
                "If you want to read from the Azure container, you must provide the "
                "following environment variables:\n"
                "* AZURE_STORAGE_CONNECTION_STRING\n"
                "or\n"
                "* AZURE_STORAGE_ACCOUNT_NAME\n"
                "* AZURE_STORAGE_ACCOUNT_URL\n"
                "* AZURE_STORAGE_ACCOUNT_KEY\n"
            )
            raise exceptions.UserError(msg)
        blob_service_client = None
        if connect_str:
            try:
                blob_service_client = BlobServiceClient.from_connection_string(
                    connect_str
                )
            except HttpResponseError as error:
                _logger.exception(
                    "Error during the connection to Azure container using the "
                    "connection string."
                )
                raise exceptions.UserError(str(error))
        else:
            try:
                sas_token = generate_account_sas(
                    account_name=account_name,
                    account_key=account_key,
                    resource_types=ResourceTypes(service=True),
                    permission=AccountSasPermissions(read=True),
                    expiry=datetime.utcnow() + timedelta(hours=1),
                )
                blob_service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=sas_token,
                )
            except HttpResponseError as error:
                _logger.exception(
                    "Error during the connection to Azure container using the Shared "
                    "Access Signature (SAS)"
                )
                raise exceptions.UserError(str(error))
        return blob_service_client

    @api.model
    def _get_azure_container(self):
        running_env = os.environ.get("RUNNING_ENV", "dev")
        container_name = str.lower(running_env + "-" + self.env.cr.dbname)
        blob_service_client = self._get_blob_service_client()
        container_client = blob_service_client.get_container_client(container_name)
        try:
            # Create the container
            container_client.create_container()
        except ResourceExistsError:
            pass
        except HttpResponseError as error:
            _logger.exception("Error during the creation of the Azure container")
            raise exceptions.UserError(str(error))
        return container_client

    @api.model
    def _store_file_read(self, fname, bin_size=False):
        if fname.startswith("azure://"):
            container_client = self._get_azure_container()
            key = fname.replace("azure://", "", 1).lower()
            try:
                blob_client = container_client.get_blob_client(key)
                read = blob_client.download_blob().readall()
            except HttpResponseError:
                read = ""
                _logger.info("Attachment '%s' missing on object storage", fname)
            return read
        else:
            return super(IrAttachment, self)._store_file_read(fname, bin_size)

    @api.model
    def _store_file_write(self, key, bin_data):
        location = self.env.context.get("storage_location") or self._storage()
        if location == "azure":
            container_client = self._get_azure_container()
            with io.BytesIO() as file:
                blob_client = container_client.get_blob_client(key.lower())
                file.write(bin_data)
                file.seek(0)
                filename = "azure://%s" % (key)
                try:
                    blob_client.upload_blob(file, blob_type="BlockBlob")
                except ResourceExistsError:
                    pass
                except HttpResponseError as error:
                    # log verbose error from azure, return short message for user
                    _logger.exception("Error during storage of the file %s" % filename)
                    raise exceptions.UserError(
                        _("The file could not be stored: %s") % str(error)
                    )
        else:
            _super = super(IrAttachment, self)
            filename = _super._store_file_write(key, bin_data)
        return filename

    @api.model
    def _store_file_delete(self, fname):
        if fname.startswith("azure://"):
            container_client = self._get_azure_container()
            key = fname.replace("azure://", "", 1).lower()
            # delete the file only if it is on the current configured container
            # otherwise, we might delete files used on a different environment
            try:
                blob_client = container_client.get_blob_client(key)
                blob_client.delete_blob()
                _logger.info("File %s deleted on the object storage" % (fname))
            except HttpResponseError:
                # log verbose error from azure, return short message for
                # user
                _logger.exception("Error during deletion of the file %s" % fname)
        else:
            super(IrAttachment, self)._store_file_delete(fname)
