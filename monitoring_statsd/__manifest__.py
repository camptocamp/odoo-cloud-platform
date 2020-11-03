# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


{'name': 'Monitoring: Statsd Metrics',
 'version': "14.0.1.0.0",
 'author': 'Camptocamp,Odoo Community Association (OCA)',
 'license': 'AGPL-3',
 'category': 'category',
 'depends': ['base',
             'web',
             'server_environment',
             ],
 'website': 'http://www.camptocamp.com',
 'data': [],
 'external_dependencies': {
     'python': ['statsd'],
 },
 'installable': True,
 }
