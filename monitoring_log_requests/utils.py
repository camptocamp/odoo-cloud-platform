# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from distutils.util import strtobool
from os import environ


def is_enabled():
    env_val = environ.get('ODOO_REQUESTS_LOGGING')
    return bool(strtobool(env_val or '0'.lower()))
