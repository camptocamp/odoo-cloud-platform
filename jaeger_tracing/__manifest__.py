# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


{'name': 'Jaeger Tracing',
 'summary': 'Tracing application code with jaeger tracing',
 'version': '10.0.1.0.0',
 'author': 'Camptocamp,Odoo Community Association (OCA)',
 'license': 'AGPL-3',
 'category': 'Extra Tools',
 'depends': ['base'],
 'external_dependencies': {
     'python': [
         'jaeger_client',  # jaeger-client
         'opentracing_instrumentation',
         'past',  # futures
    ],
 },
 'website': 'https://www.camptocamp.com',
 'data': [],
 'installable': True,
 }
