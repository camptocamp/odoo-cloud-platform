# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import io
import logging
import os
from urllib.parse import urlsplit

from odoo import api, exceptions, models

from ..s3uri import S3Uri

_logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError, EndpointConnectionError
except ImportError:
    boto3 = None  # noqa
    ClientError = None  # noqa
    EndpointConnectionError = None  # noqa
    _logger.debug("Cannot 'import boto3'.")


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _get_stores(self):
        return ["s3"] + super()._get_stores()

    def _formatted_aws_bucketname(self, name=None):
        bucket_name = name or os.environ.get("AWS_BUCKETNAME") or ""
        return bucket_name.format(db=self.env.cr.dbname)

    def _store_fname_for_key(self, storage, key):
        if storage == "s3":
            bucket = self._formatted_aws_bucketname()
            return f"s3://{bucket}/{key}"
        return super()._store_fname_for_key(storage, key)

    def _get_s3_client(self):
        """Connect to S3 and return the resource plus region."""
        host = os.environ.get("AWS_HOST")

        # Ensure host is prefixed with a scheme (use https as default)
        if host and not urlsplit(host).scheme:
            host = f"https://{host}"

        region_name = os.environ.get("AWS_REGION")
        access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

        params = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
        }
        if host:
            params["endpoint_url"] = host
        if region_name:
            params["region_name"] = region_name
        if not (access_key and secret_key):
            raise exceptions.UserError(
                self.env._(
                    "If you want to read from the S3 bucket, the following "
                    "environment variables must be set:\n"
                    "* AWS_ACCESS_KEY_ID\n"
                    "* AWS_SECRET_ACCESS_KEY\n"
                    "If you want to write in the S3 bucket, this variable "
                    "must be set as well:\n"
                    "* AWS_BUCKETNAME\n"
                    "Optionally, the S3 host can be changed with:\n"
                    "* AWS_HOST\n"
                )
            )
        return boto3.resource("s3", **params), region_name

    @api.model
    def _get_s3_bucket(self, name=None):
        """Connect to S3 and return the bucket.

        The following environment variables can be set:
        * ``AWS_HOST``
        * ``AWS_REGION``
        * ``AWS_ACCESS_KEY_ID``
        * ``AWS_SECRET_ACCESS_KEY``
        * ``AWS_BUCKETNAME``
        * ``AWS_DUPLICATE``
        * ``AWS_EMPTY_ON_DBDROP``

        If a name is provided, that bucket is used, otherwise
        ``AWS_BUCKETNAME`` is used. ``{db}`` is replaced by the database name.

        If AWS_DUPLICATE is set, the bucket objects are copied when the
        database is duplicated. Paths in the new database are updated.

        If AWS_EMPTY_ON_DBDROP is set, objects are deleted when the database
        is dropped. The bucket itself is kept.
        """
        s3, region_name = self._get_s3_client()

        bucket_name = self._formatted_aws_bucketname(name)
        if not bucket_name:
            raise exceptions.UserError(
                self.env._(
                    "If you want to read from the S3 bucket, the following "
                    "environment variables must be set:\n"
                    "* AWS_ACCESS_KEY_ID\n"
                    "* AWS_SECRET_ACCESS_KEY\n"
                    "If you want to write in the S3 bucket, this variable "
                    "must be set as well:\n"
                    "* AWS_BUCKETNAME\n"
                    "Optionally, the S3 host can be changed with:\n"
                    "* AWS_HOST\n"
                )
            )

        bucket = s3.Bucket(bucket_name)
        exists = True
        try:
            s3.meta.client.head_bucket(Bucket=bucket_name)
        except ClientError as error:
            error_code = error.response["Error"]["Code"]
            if error_code == "404":
                exists = False
            else:
                raise
        except EndpointConnectionError as error:
            _logger.exception("Error during connection to S3")
            raise exceptions.UserError(str(error)) from error

        if not exists:
            if not region_name:
                bucket = s3.create_bucket(Bucket=bucket_name)
            else:
                bucket = s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": region_name},
                )
        return bucket

    @api.model
    def _store_file_read(self, fname, size=None):
        if fname.startswith("s3://"):
            s3uri = S3Uri(fname)
            try:
                bucket = self._get_s3_bucket(name=s3uri.bucket())
            except exceptions.UserError:
                _logger.exception(
                    "Error reading attachment '%s' from object storage", fname
                )
                return b""
            try:
                key = s3uri.item()
                bucket.meta.client.head_object(Bucket=bucket.name, Key=key)
                with io.BytesIO() as res:
                    bucket.download_fileobj(key, res)
                    res.seek(0)
                    read = res.read()
            except ClientError:
                _logger.info("Attachment '%s' missing on object storage", fname)
                return b""
            if size is not None:
                return read[:size]
            return read
        return super()._store_file_read(fname, size=size)

    @api.model
    def _store_file_write(self, key, bin_data):
        location = self.env.context.get("storage_location") or self._storage()
        if location == "s3":
            bucket = self._get_s3_bucket()
            obj = bucket.Object(key=key)
            filename = f"s3://{bucket.name}/{key}"
            with io.BytesIO() as file:
                file.write(bin_data)
                file.seek(0)
                try:
                    obj.upload_fileobj(file)
                except ClientError as error:
                    _logger.exception("Error during storage of the file %s", filename)
                    raise exceptions.UserError(
                        self.env._(
                            "The file could not be stored: %s",
                            str(error),
                        )
                    ) from error
            return filename
        return super()._store_file_write(key, bin_data)

    @api.model
    def _store_file_delete(self, fname):
        if fname.startswith("s3://"):
            s3uri = S3Uri(fname)
            bucket_name = s3uri.bucket()
            item_name = s3uri.item()
            # Delete only when the URI bucket is the current one. Otherwise a
            # replica using production credentials could wipe production files.
            if bucket_name == self._formatted_aws_bucketname():
                bucket = self._get_s3_bucket()
                obj = bucket.Object(key=item_name)
                try:
                    bucket.meta.client.head_object(Bucket=bucket.name, Key=item_name)
                    obj.delete()
                    _logger.info("File %s deleted on the object storage", fname)
                except ClientError:
                    _logger.exception("Error during deletion of the file %s", fname)
            return
        return super()._store_file_delete(fname)
