# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


import io
import logging
import os
from urllib.parse import urlsplit
from typing import Optional

from odoo import api, models
from odoo.exceptions import UserError

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

    @api.model
    def _get_s3_bucket(self, name: Optional[str] = None):
        """Connect to S3 and return the bucket

        The following environment variables can be set:
        * ``AWS_HOST``
        * ``AWS_REGION``
        * ``AWS_ACCESS_KEY_ID``
        * ``AWS_SECRET_ACCESS_KEY``
        * ``AWS_BUCKETNAME``

        If a name is provided, we'll read this bucket, otherwise, the bucket
        from the environment variable ``AWS_BUCKETNAME`` will be read.

        """
        if not boto3:
            raise UserError(self.env._("boto3 library is required for S3 integration."))

        host = os.getenv("AWS_HOST").strip()

        # Ensure `host`` is prefixed with a scheme (use https as default)
        if host and not urlsplit(host).scheme:
            host = f"https://{host}"

        region_name = os.getenv("AWS_REGION")
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        bucket_name = (name or os.getenv("AWS_BUCKETNAME", "")).format(db=self.env.cr.dbname)

        if not all([access_key, secret_key, bucket_name]):
            msg = self.env._(
                "Missing AWS credentials."
                "If you want to read from the %(bucket_name)s S3 bucket, the following "
                "environment variables must be set:\n"
                "* AWS_ACCESS_KEY_ID\n"
                "* AWS_SECRET_ACCESS_KEY\n"
                "If you want to write in the %(bucket_name)s S3 bucket, this variable "
                "must be set as well:\n"
                "* AWS_BUCKETNAME\n"
                "Optionally, the S3 host can be changed with:\n"
                "* AWS_HOST\n"
            ).format(bucket_name=bucket_name)
            raise UserError(msg)

        s3_params = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
        }
        if host:
            s3_params["endpoint_url"] = host
        if region_name:
            s3_params["region_name"] = region_name

        s3 = boto3.resource("s3", **s3_params)
        bucket = s3.Bucket(bucket_name)

        try:
            s3.meta.client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            if e.response.get("Error", {}).get("Code") == "404":
                _logger.warning(f"S3 bucket '{bucket_name}' does not exist.")
                return self._create_s3_bucket(s3, bucket_name, region_name)
            raise UserError(f"Failed to connect to S3 bucket: {str(e)}") from None
        except EndpointConnectionError as error:
            # log verbose error from s3, return short message for user
            _logger.exception("Error during S3 connection.")
            raise UserError(str(error)) from None

        return bucket

    def _create_s3_bucket(self, s3, bucket_name: str, region_name: Optional[str]):
        """Create an S3 bucket if it does not exist."""
        params = {"Bucket": bucket_name}
        if region_name:
            params["CreateBucketConfiguration"] = {"LocationConstraint": region_name}
        
        try:
            return s3.create_bucket(**params)
        except ClientError as e:
            _logger.exception(f"Failed to create S3 bucket '{bucket_name}'")
            raise UserError(f"Bucket creation failed: {str(e)}") from None

    @api.model
    def _store_file_read(self, fname: str):
        if fname.startswith("s3://"):
            s3uri = S3Uri(fname)
            try:
                bucket = self._get_s3_bucket(name=s3uri.bucket)
            except UserError:
                _logger.exception(f"Error reading attachment '{fname}' from S3.")
                return ""

            key = s3uri.item()
            try:
                bucket.meta.client.head_object(Bucket=bucket.name, Key=key)
                with io.BytesIO() as res:
                    bucket.download_fileobj(key, res)
                    res.seek(0)
                    return res.read()
            except ClientError:
                _logger.info(f"Attachment '{fname}' missing on S3.")
                return ""
        return super()._store_file_read(fname)

    @api.model
    def _store_file_write(self, key: str, bin_data: bytes) -> str:
        location = self.env.context.get("storage_location") or self._storage()
        if location == "s3":
            bucket = self._get_s3_bucket()
            obj = bucket.Object(key=key)
            filename = f"s3://{bucket.name}/{key}"

            try:
                with io.BytesIO(bin_data) as file:
                    obj.upload_fileobj(file)
            except ClientError as error:
                # log verbose error from s3, return short message for user
                _logger.exception(f"Error storing file {filename} on S3.")
                raise UserError(self.env._("The file could not be stored: %s") % str(error)) from None

            return filename
        return super()._store_file_write(key, bin_data)

    @api.model
    def _store_file_delete(self, fname: str):
        if fname.startswith("s3://"):
            s3uri = S3Uri(fname)
            bucket_name = s3uri.bucket()
            item_name = s3uri.item()
            # delete the file only if it is on the current configured bucket
            # otherwise, we might delete files used on a different environment
            if bucket_name == os.getenv("AWS_BUCKETNAME"):
                bucket = self._get_s3_bucket()
                obj = bucket.Object(key=item_name)

                try:
                    bucket.meta.client.head_object(Bucket=bucket.name, Key=item_name)
                    obj.delete()
                    _logger.info(f"File {fname} deleted from S3.")
                except ClientError:
                    # log verbose error from s3, return short message for user
                    _logger.exception(f"Error deleting file {fname} from S3.")
        else:
            return super()._store_file_delete(fname)
