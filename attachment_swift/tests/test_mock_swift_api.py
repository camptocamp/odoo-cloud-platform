# Copyright 2017-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
import mock
import os

from mock import patch

import keystoneauth1

from odoo.addons.base.tests.test_ir_attachment import TestIrAttachment
from odoo.addons.attachment_swift.models.ir_attachment import SwiftSessionStore
from odoo.addons.attachment_swift.swift_uri import SwiftUri


class TestAttachmentSwift(TestIrAttachment):

    def setup(self):
        super().setUp()
        self.env['ir.config_parameter'].set_param('ir_attachment.location',
                                                  'swift')

    def test_session_store_get_session(self):
        auth_url = 'auth_url'
        username = 'username'
        password = 'password'
        project_name = 'project_name'
        store = SwiftSessionStore()
        session = store.get_session(
            auth_url=auth_url,
            username=username,
            password=password,
            project_name=project_name,
        )
        self.assertEqual(session.auth.auth_url, auth_url)
        self.assertEqual(session.auth.get_cache_id_elements().get(
            'password_username'), username)
        self.assertEqual(session.auth.get_cache_id_elements().get(
            'password_password'), password)
        self.assertEqual(session.auth.project_name, project_name)

        # get the same session on a second call
        self.assertEqual(
            store.get_session(
                auth_url=auth_url,
                username=username,
                password=password,
                project_name=project_name,
            ),
            session
        )

    @patch('swiftclient.client')
    def test_connection(self, mock_swift_client):
        """ Test the connection to the store"""
        os.environ['SWIFT_AUTH_URL'] = 'auth_url'
        os.environ['SWIFT_ACCOUNT'] = 'account'
        os.environ['SWIFT_PASSWORD'] = 'password'
        os.environ['SWIFT_PROJECT_NAME'] = 'project_name'
        os.environ['SWIFT_REGION_NAME'] = 'NOWHERE'
        attachment = self.Attachment
        attachment._get_swift_connection()
        mock_swift_client.Connection.assert_called_once_with(
            session=mock.ANY,
            os_options={'region_name': os.environ.get('SWIFT_REGION_NAME')},
        )
        __, kwargs = mock_swift_client.Connection.call_args
        session = kwargs['session']
        self.assertTrue(isinstance(session, keystoneauth1.session.Session))
        self.assertEqual(session.auth.auth_url, os.environ['SWIFT_AUTH_URL'])
        self.assertEqual(session.auth.get_cache_id_elements().get(
            'password_username'), os.environ['SWIFT_ACCOUNT'])
        self.assertEqual(session.auth.get_cache_id_elements().get(
            'password_password'), os.environ['SWIFT_PASSWORD'])
        self.assertEqual(session.auth.project_name,
                         os.environ['SWIFT_PROJECT_NAME'])

    def test_store_file_on_swift(self):
        """
            Test writing a file
        """
        (self.env['ir.config_parameter'].
            set_param('ir_attachment.location', 'swift'))
        os.environ['SWIFT_AUTH_URL'] = 'auth_url'
        os.environ['SWIFT_ACCOUNT'] = 'account'
        os.environ['SWIFT_PASSWORD'] = 'password'
        os.environ['SWIFT_PROJECT_NAME'] = 'project_name'
        os.environ['SWIFT_WRITE_CONTAINER'] = 'my_container'
        container = os.environ.get('SWIFT_WRITE_CONTAINER')
        attachment = self.Attachment
        bin_data = base64.b64decode(self.blob1_b64)
        with patch('swiftclient.client.Connection') as MockConnection:
            conn = MockConnection.return_value
            attachment.create({'name': 'a5', 'datas': self.blob1_b64})
            conn.put_object.assert_called_with(
                container,
                attachment._compute_checksum(bin_data),
                bin_data)

    def test_delete_file_on_swift(self):
        """
            Test deleting a file
        """
        (self.env['ir.config_parameter'].
            set_param('ir_attachment.location', 'swift'))
        os.environ['SWIFT_AUTH_URL'] = 'auth_url'
        os.environ['SWIFT_ACCOUNT'] = 'account'
        os.environ['SWIFT_PASSWORD'] = 'password'
        os.environ['SWIFT_PROJECT_NAME'] = 'project_name'
        os.environ['SWIFT_WRITE_CONTAINER'] = 'my_container'

        attachment = self.Attachment
        container = os.environ.get('SWIFT_WRITE_CONTAINER')
        with patch('swiftclient.client.Connection') as MockConnection:
            conn = MockConnection.return_value
            a5 = attachment.create({'name': 'a5', 'datas': self.blob1_b64})
            uri = SwiftUri(a5.store_fname)
            a5.unlink()
            conn.delete_object.assert_called_with(container, uri.item())
