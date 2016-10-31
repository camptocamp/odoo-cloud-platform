# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


import base64
import logging
import os
import xml.dom.minidom
from contextlib import closing, contextmanager
from functools import partial

from distutils.util import strtobool

import boto
from boto.exception import S3ResponseError

import openerp
from openerp import _, api, exceptions, fields, models, SUPERUSER_ID
from ..s3uri import S3Uri

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

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
            raise exceptions.UserError(
                _('The following environment variables must be set:\n'
                  '* AWS_ACCESS_KEY_ID\n'
                  '* AWS_SECRET_ACCESS_KEY\n'
                  '* AWS_BUCKETNAME\n'
                  '* AWS_HOST (optional)\n'
                  )
            )

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
    def _file_read_s3(self, fname, bin_size=False):
        try:
            s3uri = S3Uri(fname)
        except ValueError:
            # compatibility mode: previously we stored only the key
            # of the object, not we store the uri:
            # example:
            # before: fc02f84c0db500c69204972d27356ffdf0759386
            # now: s3://bucket/fc02f84c0db500c69204972d27356ffdf0759386
            # where 'project-odoo-prod' is the bucket name
            bucket_name = None
            item_name = fname
        else:
            bucket_name = s3uri.bucket()
            item_name = s3uri.item()

        bucket = self._get_s3_bucket(name=bucket_name)
        filekey = bucket.get_key(item_name)
        if filekey:
            read = base64.b64encode(filekey.get_contents_as_string())
        else:
            read = ''
            _logger.info("_read_file_s3 reading %s, file missing", fname)
        return read

    @api.model
    def _file_read(self, fname, bin_size=False):
        storage = self._storage()
        if storage.startswith('s3') or fname.startswith('s3://'):
            read = self._file_read_s3(fname, bin_size=bin_size)
            if not read and not fname.startswith('s3://'):
                # If the attachment has been created before the installation
                # of the addon, it might still be stored on the filesystem.
                # Fallback on the filesystem read.
                try:
                    _super = super(IrAttachment, self)
                    read = _super._file_read(fname, bin_size=bin_size)
                except (IOError, OSError):
                    # File is missing
                    read = ''
        else:
            _super = super(IrAttachment, self)
            read = _super._file_read(fname, bin_size=bin_size)
        return read

    @api.model
    def _file_write(self, value, checksum):
        storage = self._storage()
        if storage.startswith('s3'):
            bucket = self._get_s3_bucket()
            bin_data = value.decode('base64')
            key = self._compute_checksum(bin_data)
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
            filename = super(IrAttachment, self)._file_write(value, checksum)
        return filename

    @api.model
    def _file_delete(self, fname):
        if fname.startswith('s3://'):
            # using SQL to include files hidden through unlink or due to record
            # rules
            cr = self.env.cr
            cr.execute("SELECT COUNT(*) FROM ir_attachment "
                       "WHERE store_fname = %s", (fname,))
            count = cr.fetchone()[0]
            s3uri = S3Uri(fname)
            bucket_name = s3uri.bucket()
            item_name = s3uri.item()

            bucket = self._get_s3_bucket(name=bucket_name)
            filekey = bucket.get_key(item_name)
            if not count and filekey:
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
            super(IrAttachment, self)._file_delete(fname)

    @api.model
    def _force_storage_s3(self):
        if not self.env['res.users'].browse(self.env.uid)._is_admin():
            raise exceptions.AccessError(
                _('Only administrators can execute this action.')
            )

        storage = self._storage()
        if not storage.startswith('s3'):
            return
        _logger.info('migrating files to the object storage')
        domain = ['!', ('store_fname', '=like', 's3://%'),
                  '|',
                  ('res_field', '=', False),
                  ('res_field', '!=', False)]
        with self.do_in_new_env() as new_env:
            attachment_model = new_env['ir.attachment']
            ids = attachment_model.search(domain).ids
            for attachment_id in ids:
                # This is a trick to avoid having the 'datas' function fields
                # computed for every attachment on each iteration of the loop.
                # The former issue being that it reads the content of the file
                # of ALL the attachments on each loop.
                new_env.clear()
                attachment = attachment_model.browse(attachment_id)
                _logger.info('inspecting attachment %s (%d)',
                             attachment.name, attachment.id)
                fname = attachment.store_fname
                if fname:
                    # migrating from filesystem filestore
                    # or from the old 'store_fname' without the bucket name
                    _logger.info('moving %s on the object storage', fname)
                    attachment.write({'datas': attachment.datas,
                                      # this is required otherwise the
                                      # mimetype gets overriden with
                                      # 'application/octet-stream'
                                      # on assets
                                      'mimetype': attachment.mimetype})
                    _logger.info('moved %s on the object storage', fname)
                    full_path = attachment_model._full_path(fname)
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
                new_env.cr.commit()

    @contextmanager
    def do_in_new_env(self):
        """ Context manager that yields a new environment

        Using a new Odoo Environment thus a new PG transaction.
        """
        with api.Environment.manage():
            registry = openerp.modules.registry.RegistryManager.get(
                self.env.cr.dbname
            )
            with closing(registry.cursor()) as cr:
                try:
                    new_env = openerp.api.Environment(cr, self.env.uid,
                                                      self.env.context)
                    yield new_env
                except:
                    cr.rollback()
                    raise
                else:
                    cr.commit()

    @api.model
    def force_storage(self):
        storage = self._storage()
        if storage.startswith('s3'):
            self._force_storage_s3()
        else:
            return super(IrAttachment, self).force_storage()

    @api.cr
    def _register_hook(self, cr):
        # We need to call the migration on the loading of the model
        # because when we are upgrading addons, some of them might
        # add attachments, and to be sure the are migrated to S3,
        # we need to call the migration here.
        super(IrAttachment, self)._register_hook(cr)
        env = api.Environment(cr, SUPERUSER_ID, {})
        env['ir.attachment']._force_storage_s3()
