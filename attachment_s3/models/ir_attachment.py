# Copyright 2016-2018 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


import base64
import logging
import os
import io
from urllib.parse import urlsplit

from odoo import _, api, exceptions, models
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


class S3BucketClientRegistry(object):
    bucket_dict = {}

    @classmethod
    def get_bucket_client(cls, bucket_name):
        return cls.bucket_dict.get(bucket_name)

    @classmethod
    def set_bucket_client(cls, bucket_name, bucket_obj):
        cls.bucket_dict[bucket_name] = bucket_obj


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _get_stores(self):
        stores = ['s3']
        stores += super(IrAttachment, self)._get_stores()
        return stores

    @api.model
    def _get_s3_connection_params(self, bucket_name=None):
        host = os.environ.get('AWS_HOST')

        # Ensure host is prefixed with a scheme (use https as default)
        if host and not urlsplit(host).scheme:
            host = 'https://%s' % host

        region_name = os.environ.get('AWS_REGION')
        access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        aws_use_irsa = os.environ.get('AWS_USE_IRSA')
        bucket_name = bucket_name or os.environ.get('AWS_BUCKETNAME')
        # replaces {db} by the database name to handle multi-tenancy
        bucket_name = bucket_name.format(db=self.env.cr.dbname)
        params = {
            'bucket_name': bucket_name,
        }
        if not aws_use_irsa and access_key:
            params['aws_access_key_id'] = access_key
            if secret_key:
                params['aws_secret_access_key'] = secret_key
        if host:
            params['endpoint_url'] = host
        if region_name:
            params['region_name'] = region_name

        return params, aws_use_irsa

    @api.model
    def _get_s3_bucket(self, name=None):
        """Connect to S3 and return the bucket

        The following environment variables can be set:
        * ``AWS_HOST``
        * ``AWS_REGION``
        * ``AWS_ACCESS_KEY_ID``
        * ``AWS_SECRET_ACCESS_KEY``
        * ``AWS_BUCKETNAME``
        * ``AWS_USE_IRSA``

        If a name is provided, we'll read this bucket, otherwise, the bucket
        from the environment variable ``AWS_BUCKETNAME`` will be read.

        """
        params, aws_use_irsa = self._get_s3_connection_params(bucket_name=name)
        # Pop the bucket_name to avoid TypeError: resource() got an unexpected
        #  keyword argument 'bucket_name'
        bucket_name = params.pop("bucket_name")
        if not (
            bucket_name and
            (params.get("aws_access_key_id") and
             params.get("aws_secret_access_key") or
             aws_use_irsa)
        ):
            msg = _('If you want to read from the %s S3 bucket, the following '
                    'environment variables must be set:\n'
                    '* AWS_ACCESS_KEY_ID\n'
                    '* AWS_SECRET_ACCESS_KEY\n'
                    'or use irsa for authentification\n'
                    '* AWS_USE_IRSA\n'
                    'If you want to write in the %s S3 bucket, this variable '
                    'must be set as well:\n'
                    '* AWS_BUCKETNAME\n'
                    'Optionally, the S3 host can be changed with:\n'
                    '* AWS_HOST\n'
                    ) % (bucket_name, bucket_name)

            raise exceptions.UserError(msg)
        # try:
        # get instanciated bucket from bucket_dict
        bucket = S3BucketClientRegistry.get_bucket_client(bucket_name)
        if bucket:
            return bucket
        s3 = boto3.resource('s3', **params)
        bucket = s3.Bucket(bucket_name)
        exists = True
        try:
            s3.meta.client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = e.response['Error']['Code']
            if error_code == '404':
                exists = False
        except EndpointConnectionError as error:
            # log verbose error from s3, return short message for user
            _logger.exception('Error during connection on S3')
            raise exceptions.UserError(str(error))

        if not exists:
            region_name = params.get('region_name')
            if not region_name:
                bucket = s3.create_bucket(Bucket=bucket_name)
            else:
                bucket = s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={
                        'LocationConstraint': region_name
                    })
        # store instanciated bucket to bucket_dict
        S3BucketClientRegistry.set_bucket_client(bucket_name, bucket)
        return bucket

    @api.model
    def _store_file_read(self, fname, bin_size=False):
        if fname.startswith('s3://'):
            s3uri = S3Uri(fname)
            try:
                bucket = self._get_s3_bucket(name=s3uri.bucket())
            except exceptions.UserError:
                _logger.exception(
                    "error reading attachment '%s' from object storage", fname
                )
                return ''
            try:
                key = s3uri.item()
                bucket.meta.client.head_object(
                    Bucket=bucket.name,  Key=key
                )
                if bin_size:
                    return bucket.Object(key).content_length
                with io.BytesIO() as res:
                    bucket.download_fileobj(key, res)
                    res.seek(0)
                    read = base64.b64encode(res.read())
            except ClientError:
                read = ''
                _logger.info(
                    "attachment '%s' missing on object storage", fname
                )
            return read
        else:
            return super(IrAttachment, self)._store_file_read(fname, bin_size)


    def _inverse_datas(self):
        location = self._storage()
        for attach in self:
            # compute the fields that depend on datas
            value = attach.datas
            bin_data = base64.b64decode(value) if value else b''
            vals = {
                'file_size': len(bin_data),
                'checksum': self._compute_checksum(bin_data),
                'index_content': self._index(bin_data, attach.datas_fname, attach.mimetype),
                'store_fname': False,
                'db_datas': value,
            }
            if value and location != 'db':
                # save it to the filestore
                self=self.with_context(mimetype=attach.mimetype)
                vals['store_fname'] = self._file_write(value, vals['checksum'])
                vals['db_datas'] = False

            # take current location in filestore to possibly garbage-collect it
            fname = attach.store_fname
            # write as superuser, as user probably does not have write access
            super(IrAttachment, attach.sudo()).write(vals)
            if fname:
                self._file_delete(fname)

    @api.model
    def _store_file_write(self, key, bin_data):
        location = self.env.context.get('storage_location') or self._storage()
        mimetype = self.env.context.get('mimetype')
        if location == 's3':
            bucket = self._get_s3_bucket()
            obj = bucket.Object(key=key)
            with io.BytesIO() as file:
                file.write(bin_data)
                file.seek(0)
                filename = 's3://%s/%s' % (bucket.name, key)
                try:
                    if mimetype:
                        obj.upload_fileobj(file, ExtraArgs={'ContentType': mimetype})
                    else:
                        obj.upload_fileobj(file)
                except ClientError as error:
                    # log verbose error from s3, return short message for user
                    _logger.exception(
                        'Error during storage of the file %s' % filename
                    )
                    raise exceptions.UserError(
                        _('The file could not be stored: %s') % str(error)
                    )
        else:
            _super = super(IrAttachment, self)
            filename = _super._store_file_write(key, bin_data)
        return filename

    @api.model
    def _store_file_delete(self, fname):
        if fname.startswith('s3://'):
            s3uri = S3Uri(fname)
            bucket_name = s3uri.bucket()
            item_name = s3uri.item()
            # delete the file only if it is on the current configured bucket
            # otherwise, we might delete files used on a different environment
            if bucket_name == os.environ.get('AWS_BUCKETNAME'):
                bucket = self._get_s3_bucket()
                obj = bucket.Object(key=item_name)
                try:
                    bucket.meta.client.head_object(
                        Bucket=bucket.name, Key=item_name
                    )
                    obj.delete()
                    _logger.info(
                        'file %s deleted on the object storage' % (fname,)
                    )
                except ClientError:
                    # log verbose error from s3, return short message for
                    # user
                    _logger.exception(
                        'Error during deletion of the file %s' % fname
                    )
        else:
            super(IrAttachment, self)._store_file_delete(fname)
