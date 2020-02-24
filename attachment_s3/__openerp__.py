# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


{'name': 'Attachments on S3 storage',
 'summary': 'Store assets and attachments on a S3 compatible object storage',
 'version': '9.0.1.3.0',
 'author': 'Camptocamp,Odoo Community Association (OCA)',
 'license': 'AGPL-3',
 'category': 'Knowledge Management',
 'depends': ['base'],
 'external_dependencies': {
     'python': ['boto3'],
 },
 'website': 'http://www.camptocamp.com',
 'data': [
     'views/res_partner_views.xml',
 ],
 'installable': True,
 }
