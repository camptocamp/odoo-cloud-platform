# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


import base64
import logging
import os
import xml.dom.minidom
from functools import partial

import boto
from boto.exception import S3ResponseError

from openerp import _, api, exceptions, models

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.model
    def _get_s3_bucket(self, bucket_url):
        """Connect to S3 and return the bucket

        It expects the ``bucket_url`` to be in the form:

        ``s3://<access-key>:<secret-key>@<bucket-name>``

        Alternatively, we can also use environment variables, in that case,
        you must set the url to ``s3://``.

        If the S3 provider is not AWS, the key
        ``ir_attachment.location.s3host`` can be configured in the System
        Parameters with the hostname.

        The following environment variable can be set:
        * ``AWS_HOST``
        * ``AWS_ACCESS_KEY_ID``
        * ``AWS_SECRET_ACCESS_KEY``
        * ``AWS_BUCKETNAME``

        """
        assert bucket_url.startswith('s3://')
        host = os.environ.get('AWS_HOST')
        if not host:
            host = self.env['ir.config_parameter'].get_param(
                'ir_attachment.location.s3host', default=None
            )
        if host:
            connect_s3 = partial(boto.connect_s3, host=host)
        else:
            connect_s3 = boto.connect_s3

        if bucket_url == 's3://':
            access_key = os.environ.get('AWS_ACCESS_KEY_ID')
            secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
            bucket_name = os.environ.get('AWS_BUCKETNAME')
            if not (access_key and secret_key and bucket_name):
                raise exceptions.UserError(
                    _('The following environment variables must be set:\n'
                      '* AWS_ACCESS_KEY_ID\n'
                      '* AWS_SECRET_ACCESS_KEY\n'
                      '* AWS_BUCKETNAME\n'
                      )
                )
        else:
            malformed_msg = _(
                'S3 bucket %s is malformed, the expected form is '
                's3://<access-key>:<secret-key>@<bucket-name>'
            )
            params = bucket_url[5:].split('@')
            if not len(params) == 2:
                raise exceptions.UserError(malformed_msg % bucket_url)
            keys, bucket_name = params
            keys = keys.split(':')
            if not len(keys) == 2:
                raise exceptions.UserError(malformed_msg % bucket_url)
            access_key, secret_key = keys

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
    def _file_read(self, fname, bin_size=False):
        _super = super(IrAttachment, self)
        storage = self._storage()
        if storage.startswith('s3://'):
            bucket = self._get_s3_bucket(storage)
            filekey = bucket.get_key(fname)
            if filekey:
                read = base64.b64encode(filekey.get_contents_as_string())
            else:
                # If the attachment has been created before the installation
                # of the addon, it might be stored on the filesystem.
                # Fallback on the filesystem read.
                # Consider running ``force_storage()`` to move all the
                # attachments on the Object Storage
                try:
                    read = _super._file_read(fname, bin_size=bin_size)
                except (IOError, OSError):
                    # File is missing
                    return ''
        else:
            read = _super._file_read(fname, bin_size=bin_size)
        return read

    @api.model
    def _file_write(self, value, checksum):
        storage = self._storage()
        if storage.startswith('s3://'):
            bucket = self._get_s3_bucket(storage)
            bin_data = value.decode('base64')
            filename = self._compute_checksum(bin_data)
            filekey = bucket.get_key(filename) or bucket.new_key(filename)
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
            filename = super(IrAttachment, self)._file_write(value, checksum)
        return filename

    @api.model
    def _file_delete(self, fname):
        storage = self._storage()
        if storage.startswith('s3://'):
            bucket = self._get_s3_bucket(storage)
            filekey = bucket.get_key(fname)
            if filekey:
                try:
                    filekey.delete()
                except S3ResponseError as error:
                    # log verbose error from s3, return short message for user
                    _logger.exception(
                        'Error during deletion of the file %s' % fname
                    )
                    raise exceptions.UserError(
                        _('The file could not be deleted: %s') %
                        (self._parse_s3_error(error),)
                    )
            else:
                # If the attachment has been created before the installation
                # of the addon, it might be stored on the filesystem.
                # Fallback on the filesystem delete method.
                # Consider running ``force_storage()`` to move all the
                # attachments on the Object Storage
                super(IrAttachment, self)._file_delete(fname)
        else:
            super(IrAttachment, self)._file_delete(fname)

    @api.model
    def force_storage(self):
        if not self.env['res.users'].browse(self.env.uid)._is_admin():
            raise exceptions.AccessError(
                _('Only administrators can execute this action.')
            )

        storage = self._storage()
        if storage.startswith('s3://'):
            _logger.info('migrating files to the object storage')
            s3_bucket = self._get_s3_bucket(storage)
            domain = ['|',
                      ('res_field', '=', False),
                      ('res_field', '!=', False)]
            ids = self.search(domain).ids
            for attachment_id in ids:
                # This is a trick to avoid having the 'datas' function fields
                # computed for every attachment on each iteration of the loop.
                # The former issue being that it reads the content of the file
                # of ALL the attachments on each loop.
                self.env.clear()
                attachment = self.browse(attachment_id)
                _logger.info('inspecting attachment %s (%d)',
                             attachment.name, attachment.id)
                fname = attachment.store_fname
                if fname:
                    # migrating from filestore
                    s3_key = s3_bucket.get_key(fname)
                    if s3_key:
                        _logger.info('file %s already on the object storage',
                                     fname)
                    else:
                        _logger.info('moving %s on the object storage', fname)
                        attachment.write({'datas': attachment.datas,
                                          # this is required otherwise the
                                          # mimetype gets overriden with
                                          # 'application/octet-stream'
                                          # on assets
                                          'mimetype': attachment.mimetype})
                        _logger.info('moved %s on the object storage', fname)
                        full_path = self._full_path(fname)
                        _logger.info('cleaning fs attachment')
                        if os.path.exists(full_path):
                            try:
                                os.unlink(full_path)
                            except OSError:
                                _logger.info(
                                    "_file_delete could not unlink %s",
                                    full_path, exc_info=True
                                )
                            except IOError:
                                # Harmless and needed for race conditions
                                _logger.info(
                                    "_file_delete could not unlink %s",
                                    full_path, exc_info=True
                                )
                elif attachment.db_datas:
                    _logger.info('moving on the object storage from database')
                    attachment.write({'datas': attachment.datas})
            self.env.cr.commit()
        else:
            return super(IrAttachment, self).force_storage()
