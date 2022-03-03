# Copyright 2016-2021 Camptocamp SA
# Copyright 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import base64
import io
import logging
import os
import re
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

try:
    from azure.identity import DefaultAzureCredential
except ImportError:
    _logger.debug("Cannot 'import azure-identity'.")


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
        or if you want to use AAD (pod identity), set it to 1 or 0
        * ``AZURE_STORAGE_USE_AAD``

        """
        connect_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        account_name = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
        account_url = os.environ.get("AZURE_STORAGE_ACCOUNT_URL")
        account_key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
        account_use_aad = os.environ.get("AZURE_STORAGE_USE_AAD")
        if not (
            connect_str
            or (account_name and account_url and account_key)
            or account_use_aad
        ):
            msg = _(
                "If you want to read from the Azure container, you must provide the "
                "following environment variables:\n"
                "* AZURE_STORAGE_CONNECTION_STRING\n"
                "or\n"
                "* AZURE_STORAGE_ACCOUNT_NAME\n"
                "* AZURE_STORAGE_ACCOUNT_URL\n"
                "* AZURE_STORAGE_ACCOUNT_KEY\n"
                "or\n"
                "* AZURE_STORAGE_USE_AAD\n"
            )
            raise exceptions.UserError(msg)
        blob_service_client = None
        if account_use_aad:
            token_credential = DefaultAzureCredential()
            blob_service_client = BlobServiceClient(
                account_url=account_url, credential=token_credential
            )
        elif connect_str:
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
                    resource_types=ResourceTypes(container=True, object=True),
                    permission=AccountSasPermissions(read=True, write=True),
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
    def _get_container_name(self):
        """
        Container naming rules:
        https://docs.microsoft.com/en-us/rest/api/storageservices/naming-and-referencing-containers--blobs--and-metadata#container-names
        """
        running_env = os.environ.get("RUNNING_ENV", "dev")
        storage_name = os.environ.get('AZURE_STORAGE_NAME', r'{env}-{db}')
        storage_name = storage_name.format(
            env=running_env,
            db=self.env.cr.dbname
        )
        # replace invalid characters by _
        storage_name = re.sub(r"[\W_]+", "-", storage_name)
        # lowercase, max 63 chars
        return str.lower(storage_name)[:63]

    @api.model
    def _get_azure_container(self, container_name=None):
        if not container_name:
            container_name = self._get_container_name()
        try:
            blob_service_client = self._get_blob_service_client()
        except exceptions.UserError:
            _logger.exception(
                "error accessing to storage '%s' please check credentials ",
                container_name
            )
            return False
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
            try:
                # Create the container
                container_client.create_container()
            except HttpResponseError as error:
                _logger.exception("Error during the creation of the Azure container")
                raise exceptions.UserError(str(error))
        return container_client

    @api.model
    def _store_file_read(self, fname, bin_size=False):
        if fname.startswith("azure://"):
            key = fname.replace("azure://", "", 1).lower()
            if '/' in key:
                container_name, key = key.split('/', 1)
            else:
                container_name = None
            container_client = self._get_azure_container(container_name)
            # if container cannot be retrived, abort reading from azure storage
            if not container_client:
                return ''
            try:
                blob_client = container_client.get_blob_client(key)
                read = base64.b64encode(blob_client.download_blob().readall())
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
            filename = "azure://%s/%s" % (container_client.container_name, key)
            with io.BytesIO() as file:
                blob_client = container_client.get_blob_client(key.lower())
                file.write(bin_data)
                file.seek(0)
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
            key = fname.replace("azure://", "", 1).lower()
            if '/' in key:
                container_name, key = key.split('/', 1)
            else:
                container_name = None
            container_client = self._get_azure_container(container_name)
            if not container_client:
                return ''
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
