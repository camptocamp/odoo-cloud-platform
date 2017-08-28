# -*- coding: utf-8 -*-
# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


import base64
import logging
import os
import swiftclient
from swiftclient.exceptions import ClientException
from ..swift_uri import SwiftUri

from odoo import api, exceptions, models, _

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.multi
    def _store_in_db_when_swift(self):
        # For testing lets save everything in Swift object store
        # TODO: same than in attachment_s3
        return False

    @api.model
    def _get_swift_connection(self):
        """ Returns a connection object for the Swift object store """
        host = os.environ.get('SWIFT_HOST')
        account = os.environ.get('SWIFT_ACCOUNT')
        password = os.environ.get('SWIFT_PASSWORD')
        if not (host and account and password):
            raise exceptions.UserError(
                _('Problem connecting to Swift store, are not the env variables set ?'))
        print 'Connection to host: {}, account: {}, password: {}'.format(host, account, password)
        try:
            conn = swiftclient.client.Connection(authurl=host, user=account, key=password)
        except ClientException:
            _logger.exception('Error connecting to Swift object store')
            raise exceptions.UserError('Error connection to Swift')
        return conn

    @api.model
    def _file_read_swift(self, fname, bin_size=False):
        swifturi = SwiftUri(fname)
        conn = self._get_swift_connection()
        print 'Swift reading on {} of {} '.format(swifturi.container(), swifturi.item())
        try:
            resp_headers, obj_content = conn.get_object(swifturi.container(), swifturi.item())
            read = base64.b64encode(obj_content)
        except ClientException:
            _logger.exception('Error reading object from Swift object store');
            #raise exceptions.UserError('Error reading to Swift')
            return ''
        return read

    @api.model
    def _file_read(self, fname, bin_size=False):
        if fname.startswith('swift://'):
            return self._file_read_swift(fname, bin_size=bin_size)
        else:
            _super = super(IrAttachment, self)
            return _super._file_read(fname, bin_size=bin_size)

    def _file_write_swift(self, value, checksum):
        container = os.environ.get('SWIFT_WRITE_CONTAINER')
        conn = self._get_swift_connection()
        conn.put_container(container)
        bin_data = value.decode('base64')
        # No keys given by the store, use checksum !?
        key = self._compute_checksum(bin_data)
        filename = 'swift://{}/{}'.format(container, key)
        print 'Saving {}'.format(filename)
        try:
            conn.put_object(container, key, bin_data)
        except ClientException:
            _logger.exception('Error connecting to Swift object store')
            raise exceptions.UserError('Error writting to Swift')
        return filename

    def _file_write(self, value, checksum):
        storage = self._storage()
        if storage == 'swift':
            filename = self._file_write_swift(value, checksum)
        else:
            filename = super(IrAttachment, self)._file_write(value, checksum)
        return filename

    @api.model
    def _file_delete(self, fname):
        if fname.startswith('swift://'):
            swifturi = SwiftUri(fname)
            container = swifturi.container()
            print 'Deleting... container: {} | filename: {}'.format(container, swifturi.item())
            if container == os.environ.get('SWIFT_WRITE_CONTAINER'):
                conn = self._get_swift_connection()
                try:
                    conn.delete_object(container, swifturi.item())
                except ClientException as error:
                    _logger.exception('Error connecting to Swift object store');
                    raise exceptions.UserError('Error deleting in Swift')
        else:
            super(IrAttachment, self)._file_delete(fname)

    @api.model
    def _force_storage_swift(self, new_cr=False):
        return

    @api.model
    def force_storage(self):
        storage = self._storage()
        if storage == 'swift':
            self._force_storage_swift()
        else:
            return super(IrAttachment, self).force_storage()
