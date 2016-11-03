# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)


{'name': 'Cloud Platform',
 'summary': 'Addons required for the Camptocamp Cloud Platform',
 'version': '9.0.1.0.0',
 'author': 'Camptocamp,Odoo Community Association (OCA)',
 'license': 'AGPL-3',
 'category': 'Extra Tools',
 'depends': [
     'attachment_s3',
     'session_redis',
     'monitoring_status',
     'logging_json',
     # 'monitoring_log_requests',
     'monitoring_statsd',
     'server_environment',  # OCA/server-tools
 ],
 'website': 'http://www.camptocamp.com',
 'data': [],
 'installable': True,
 }
