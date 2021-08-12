# Copyright 2016-2019 Camptocamp SA
# Copyright 2021 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import os

from . import models
from . import controllers

from odoo import api, SUPERUSER_ID


def _post_init_hook(cr, registry):
    # create the S3 bucket after module installation
    if os.environ.get("AZURE_STORAGE_CONNECTION_STRING", False):
        env = api.Environment(cr, SUPERUSER_ID, {})
        env["ir.attachment"]._get_azure_container()
        env["ir.config_parameter"].create(
            {"key": "ir_attachment.location", "value": "azure"}
        )
        env["ir.attachment"].force_storage()
