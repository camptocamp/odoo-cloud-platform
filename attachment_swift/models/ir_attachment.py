# -*- coding: utf-8 -*-
# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


import base64
import logging
import os
from ..swift_uri import SwiftUri

from openerp.tools.translate import _
from openerp.osv import osv
from openerp.osv.orm import except_orm

_logger = logging.getLogger(__name__)

try:
    import swiftclient
    from swiftclient.exceptions import ClientException
except ImportError:
    swiftclient = None
    ClientException = None
    _logger.debug("Cannot 'import swiftclient'.")


class IrAttachment(osv.osv):
    _inherit = 'ir.attachment'

    def _get_stores(self):
        return ['swift'] + super(IrAttachment, self)._get_stores()

    def _get_swift_connection(self):
        """ Returns a connection object for the Swift object store """
        host = os.environ.get('SWIFT_AUTH_URL')
        account = os.environ.get('SWIFT_ACCOUNT')
        password = os.environ.get('SWIFT_PASSWORD')
        tenant_name = os.environ.get('SWIFT_TENANT_NAME')
        region = os.environ.get('SWIFT_REGION_NAME')
        os_options = {}
        if region:
            os_options['region_name'] = region
        if not (host and account and password and tenant_name):
            raise except_orm(
                _("Error"),
                _("Problem connecting to Swift store, are the env variables "
                  "(SWIFT_AUTH_URL, SWIFT_ACCOUNT, SWIFT_PASSWORD, "
                  "SWIFT_TENANT_NAME) properly set?")
            )
        try:
            conn = swiftclient.client.Connection(authurl=host,
                                                 user=account,
                                                 key=password,
                                                 tenant_name=tenant_name,
                                                 auth_version='2.0',
                                                 os_options=os_options,
                                                 )
        except ClientException:
            _logger.exception('Error connecting to Swift object store')
            raise except_orm(
                _("Error"),
                _('Error on Swift connection'))
        return conn

    def _store_file_read(self, fname, bin_size=False):
        if fname.startswith('swift://'):
            swifturi = SwiftUri(fname)
            try:
                conn = self._get_swift_connection()
            except except_orm:
                _logger.exception(
                    "error reading attachment '%s' from object storage", fname
                )
                return ''
            try:
                resp, obj_content = conn.get_object(swifturi.container(),
                                                    swifturi.item())
                read = base64.b64encode(obj_content)
            except ClientException:
                read = ''
                _logger.exception(
                    'Error reading object from Swift object store')
            return read
        else:
            return super(IrAttachment, self)._store_file_read(fname, bin_size)

    def _store_file_write(self, storage, key, bin_data, container=None):
        if storage == 'swift':
            if container is None:
                container = os.environ.get('SWIFT_WRITE_CONTAINER')
            conn = self._get_swift_connection()
            conn.put_container(container)
            filename = 'swift://{}/{}'.format(container, key)
            try:
                conn.put_object(container, key, bin_data)
            except ClientException:
                _logger.exception('Error writing to Swift object store')
                raise except_orm(
                    _("Error"),
                    _('Error writing to Swift'))
        else:
            _super = super(IrAttachment, self)
            filename = _super._store_file_write(key, bin_data)
        return filename

    def _store_file_delete(self, fname, container=None):
        if fname.startswith('swift://'):
            swifturi = SwiftUri(fname)
            uri_container = swifturi.container()
            if container is None:
                container = os.environ.get('SWIFT_WRITE_CONTAINER')
            # delete the file only if it is on the current configured bucket
            # otherwise, we might delete files used on a different environment
            if uri_container == container:
                conn = self._get_swift_connection()
                try:
                    conn.delete_object(container, swifturi.item())
                except ClientException:
                    _logger.exception(
                        _('Error deleting an object on the Swift store'))
                    # we ignore the error, file will stay on the object
                    # storage but won't disrupt the process
        else:
            super(IrAttachment, self)._store_file_delete(fname)
