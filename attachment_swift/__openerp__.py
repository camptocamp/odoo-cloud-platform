# -*- coding: utf-8 -*-
# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


{'name': 'Attachments on Swift storage',
 'summary': 'Store assets and attachments on a Swift compatible object store',
 'version': '7.0.1.0.0',
 'author': 'Camptocamp,Odoo Community Association (OCA)',
 'license': 'AGPL-3',
 'category': 'Knowledge Management',
 'depends': ['base_attachment_object_storage'],
 'external_dependencies': {
     'python': ['swiftclient',
                'keystoneclient',
                ],
 },
 'website': 'https://www.camptocamp.com',
 'data': [],
 'installable': True,
 }
