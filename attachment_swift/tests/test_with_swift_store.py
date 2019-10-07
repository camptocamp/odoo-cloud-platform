# Copyright 2017-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from odoo.addons.base.tests.test_ir_attachment import TestIrAttachment
from ..swift_uri import SwiftUri
from swiftclient.exceptions import ClientException


class TestAttachmentSwift(TestIrAttachment):
    """
    Those tests are made to be run against a real Swift store (local or remote)
    """

    def setup(self):
        super().setUp()
        self.env['ir.config_parameter'].set_param('ir_attachment.location',
                                                  'swift')

    def test_connection(self):
        """ Test the connection to the Swift object store """
        conn = self.Attachment._get_swift_connection()
        self.assertNotEqual(conn, False)

    def test_store_file_on_swift(self):
        """ Test writing a file and then reading it """
        (self.env['ir.config_parameter'].
            set_param('ir_attachment.location', 'swift'))
        a5 = self.Attachment.create({'name': 'a5', 'datas': self.blob1_b64})
        a5bis = self.Attachment.browse(a5.id)[0]
        self.assertEqual(a5.datas, a5bis.datas)

    def test_delete_file_on_swift(self):
        """ Create a file and then test the deletion """
        (self.env['ir.config_parameter'].
            set_param('ir_attachment.location', 'swift'))
        a5 = self.Attachment.create({'name': 'a5', 'datas': self.blob1_b64})
        uri = SwiftUri(a5.store_fname)
        con = self.Attachment._get_swift_connection()
        con.get_object(uri.container(), uri.item())
        a5.unlink()
        with self.assertRaises(ClientException):
            con.get_object(uri.container(), uri.item())
