# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


import base64
import logging
import os
import xml.dom.minidom
from functools import partial

from odoo import _, api, exceptions, models
from ..s3uri import S3Uri

_logger = logging.getLogger(__name__)

try:
    import boto
    from boto.exception import S3ResponseError
except ImportError:
    boto = None  # noqa
    S3ResponseError = None  # noqa
    _logger.debug("Cannot 'import boto'.")


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _get_stores(self):
        l = ['s3']
        l += super(IrAttachment, self)._get_stores()
        return l

    @api.model
    def _get_s3_bucket(self, name=None):
        """Connect to S3 and return the bucket

        The following environment variables can be set:
        * ``AWS_HOST``
        * ``AWS_ACCESS_KEY_ID``
        * ``AWS_SECRET_ACCESS_KEY``
        * ``AWS_BUCKETNAME``

        If a name is provided, we'll read this bucket, otherwise, the bucket
        from the environment variable ``AWS_BUCKETNAME`` will be read.

        """
        host = os.environ.get('AWS_HOST')
        if host:
            connect_s3 = partial(boto.connect_s3, host=host)
        else:
            connect_s3 = boto.connect_s3

        access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        if name:
            bucket_name = name
        else:
            bucket_name = os.environ.get('AWS_BUCKETNAME')
        if not (access_key and secret_key and bucket_name):
            msg = _('If you want to read from the %s S3 bucket, the following '
                    'environment variables must be set:\n'
                    '* AWS_ACCESS_KEY_ID\n'
                    '* AWS_SECRET_ACCESS_KEY\n'
                    'If you want to write in the %s S3 bucket, this variable '
                    'must be set as well:\n'
                    '* AWS_BUCKETNAME\n'
                    'Optionally, the S3 host can be changed with:\n'
                    '* AWS_HOST\n'
                    ) % (bucket_name, bucket_name)

            raise exceptions.UserError(msg)

        try:
            conn = connect_s3(aws_access_key_id=access_key,
                              aws_secret_access_key=secret_key)

        except S3ResponseError as error:
            # log verbose error from s3, return short message for user
            _logger.exception('Error during connection on S3')
            raise exceptions.UserError(self._parse_s3_error(error))

        bucket = conn.lookup(bucket_name)
        if not bucket:
            bucket = conn.create_bucket(bucket_name)
        return bucket

    @staticmethod
    def _parse_s3_error(s3error):
        msg = s3error.reason
        # S3 error message is a XML message...
        doc = xml.dom.minidom.parseString(s3error.body)
        msg_node = doc.getElementsByTagName('Message')
        if msg_node:
            msg = '%s: %s' % (msg, msg_node[0].childNodes[0].data)
        return msg

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
            filekey = bucket.get_key(s3uri.item())
            if filekey:
                read = base64.b64encode(filekey.get_contents_as_string())
            else:
                read = ''
                _logger.info(
                    "attachment '%s' missing on object storage", fname
                )
            return read
        else:
            return super(IrAttachment, self)._store_file_read(fname, bin_size)

    @api.model
    def _store_file_write(self, key, bin_data):
        if self._storage() == 's3':
            bucket = self._get_s3_bucket()
            filekey = bucket.get_key(key) or bucket.new_key(key)
            filename = 's3://%s/%s' % (bucket.name, key)
            try:
                filekey.set_contents_from_string(bin_data)
            except S3ResponseError as error:
                # log verbose error from s3, return short message for user
                    _logger.exception(
                        'Error during storage of the file %s' % filename
                    )
                    raise exceptions.UserError(
                        _('The file could not be stored: %s') %
                        (self._parse_s3_error(error),)
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
                filekey = bucket.get_key(item_name)
                if filekey:
                    try:
                        filekey.delete()
                        _logger.info(
                            'file %s deleted on the object storage' % (fname,)
                        )
                    except S3ResponseError:
                        # log verbose error from s3, return short message for
                        # user
                        _logger.exception(
                            'Error during deletion of the file %s' % fname
                        )
        else:
            super(IrAttachment, self)._store_file_delete(fname)
