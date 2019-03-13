# Copyright 2019 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
import base64

from odoo.tests import TransactionCase
from odoo.modules.module import get_module_resource
from odoo.exceptions import ValidationError


class TestFileUrlFields(TransactionCase):

    def test_fileurl_fields(self):
        file_path = get_module_resource('test_base_fileurl_field', 'data',
                                        'sample.txt')
        image_path = get_module_resource('test_base_fileurl_field', 'data',
                                         'pattern.png')
        partner = self.env.ref('base.main_partner')
        with open(file_path, 'rb') as f:
            with open(image_path, 'rb') as i:
                partner.write({
                    'url_file': base64.b64encode(f.read()),
                    'url_file_fname': 'sample.txt',
                    'url_image': base64.b64encode(i.read()),
                    'url_image_fname': 'pattern.png',
                })

        with open(file_path, 'rb') as f:
            self.assertEqual(base64.decodebytes(partner.url_file), f.read())

        with open(image_path, 'rb') as i:
            self.assertEqual(base64.decodebytes(partner.url_image), i.read())

        partner2 = self.env.ref('base.partner_admin')
        with open(file_path, 'rb') as f:
            with self.assertRaises(ValidationError):
                partner2.write({
                    'url_file': base64.b64encode(f.read()),
                    'url_file_fname': 'sample.txt',
                })
