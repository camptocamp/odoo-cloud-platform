# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import os
from . import models
from . import controllers

from odoo import api, SUPERUSER_ID


def _post_init_hook(cr, registry):
    # create the S3 bucket after module installation
    if os.environ.get("AWS_BUCKETNAME", False):
        env = api.Environment(cr, SUPERUSER_ID, {})
        env["ir.attachment"]._get_s3_bucket()
        env["ir.config_parameter"].create(
            {"key": "ir_attachment.location", "value": "s3"}
        )
        env["ir.attachment"].force_storage()