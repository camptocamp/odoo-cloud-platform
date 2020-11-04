# Copyright 2017-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


import logging
import os
from ..swift_uri import SwiftUri

from odoo import api, exceptions, models, _

_logger = logging.getLogger(__name__)

try:
    import swiftclient
    import keystoneauth1
    import keystoneauth1.identity
    import keystoneauth1.session
    from swiftclient.exceptions import ClientException
except ImportError:
    swiftclient = None
    ClientException = None
    _logger.debug("Cannot 'import swiftclient'.")


SWIFT_TIMEOUT = 15


class SwiftSessionStore(object):
    """Keep in memory the current Swift Auth session

    The auth endpoint has a rate limit on swift, if every operation
    on the filestore authenticate, the limit is exhausted and
    operations rejected with an HTTP error code 429.

    Swift connections can reuse the same session by asking a session
    matching their connection parameters with ``get_session``.

    The keystoneauth1's session automatically creates a new token
    if the previous one is expired.

    The best documentation I found about sessions is
    https://docs.openstack.org/keystoneauth/latest/using-sessions.html
    """

    def __init__(self):
        self._sessions = {}

    def _get_key(self, auth_url, username, password, project_name):
        return (auth_url, username, password, project_name)

    def get_session(self, auth_url=None, username=None, password=None,
                    project_name=None):
        key = self._get_key(auth_url, username, password, project_name)
        session = self._sessions.get(key)
        if not session:
            auth = keystoneauth1.identity.v3.Password(
                username=username,
                password=password,
                project_name=project_name,
                auth_url=auth_url,
                project_domain_id='default',
                user_domain_id='default',
            )
            session = keystoneauth1.session.Session(
                auth=auth,
                timeout=SWIFT_TIMEOUT,
            )
            self._sessions[key] = session
        return session


swift_session_store = SwiftSessionStore()


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _get_stores(self):
        l = ['swift']
        l += super()._get_stores()
        return l

    @api.model
    def _get_swift_connection(self):
        """ Returns a connection object for the Swift object store """
        host = os.environ.get('SWIFT_AUTH_URL')
        account = os.environ.get('SWIFT_ACCOUNT')
        password = os.environ.get('SWIFT_PASSWORD')
        project_name = os.environ.get('SWIFT_PROJECT_NAME')
        if not project_name and os.environ.get('SWIFT_TENANT_NAME'):
            project_name = os.environ['SWIFT_TENANT_NAME']
            _logger.warning(
                "SWIFT_TENANT_NAME is deprecated and "
                "must be replaced by SWIFT_PROJECT_NAME"
            )
        region = os.environ.get('SWIFT_REGION_NAME')
        os_options = {}
        if region:
            os_options['region_name'] = region
        if not (host and account and password and project_name):
            raise exceptions.UserError(_(
                "Problem connecting to Swift store, are the env variables "
                "(SWIFT_AUTH_URL, SWIFT_ACCOUNT, SWIFT_PASSWORD, "
                "SWIFT_TENANT_NAME) properly set?"
            ))
        try:
            session = swift_session_store.get_session(
                username=account,
                password=password,
                project_name=project_name,
                auth_url=host,
            )
            conn = swiftclient.client.Connection(
                session=session,
                os_options=os_options,
            )
        except ClientException:
            _logger.exception('Error connecting to Swift object store')
            raise exceptions.UserError(_('Error on Swift connection'))
        return conn

    @api.model
    def _store_file_read(self, fname):
        if fname.startswith('swift://'):
            swifturi = SwiftUri(fname)
            try:
                conn = self._get_swift_connection()
            except exceptions.UserError:
                _logger.exception(
                    "error reading attachment '%s' from object storage", fname
                )
                return ''
            try:
                resp, read = conn.get_object(
                    swifturi.container(),
                    swifturi.item()
                )
            except ClientException:
                read = ''
                _logger.exception(
                    'Error reading object from Swift object store')
            return read
        else:
            return super()._store_file_read(fname)

    def _store_file_write(self, key, bin_data):
        if self._storage() == 'swift':
            container = os.environ.get('SWIFT_WRITE_CONTAINER')
            conn = self._get_swift_connection()
            conn.put_container(container)
            filename = 'swift://{}/{}'.format(container, key)
            try:
                conn.put_object(container, key, bin_data)
            except ClientException:
                _logger.exception('Error writing to Swift object store')
                raise exceptions.UserError(_('Error writing to Swift'))
        else:
            _super = super()
            filename = _super._store_file_write(key, bin_data)
        return filename

    @api.model
    def _store_file_delete(self, fname):
        if fname.startswith('swift://'):
            swifturi = SwiftUri(fname)
            container = swifturi.container()
            # delete the file only if it is on the current configured bucket
            # otherwise, we might delete files used on a different environment
            if container == os.environ.get('SWIFT_WRITE_CONTAINER'):
                conn = self._get_swift_connection()
                try:
                    conn.delete_object(container, swifturi.item())
                except ClientException:
                    _logger.exception(
                        _('Error deleting an object on the Swift store'))
                    # we ignore the error, file will stay on the object
                    # storage but won't disrupt the process
        else:
            super()._file_delete_from_store(fname)
