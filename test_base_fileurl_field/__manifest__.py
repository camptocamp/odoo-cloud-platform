# Copyright 2019 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
{
    'name': 'test base fileurl fields',
    'version': '12.0.1.0.0',
    'category': 'Tests',
    'description': """A module to verify fileurl field.""",
    'depends': [
        'base_fileurl_field'
    ],
    'data': [
        "views/res_partner.xml",
        "views/res_users.xml",
    ],
    'installable': True,
    'auto_install': False,
}
