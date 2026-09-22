# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import os

from . import controllers
from . import models


def _post_init_hook(env):
    # Create the S3 bucket after module installation and migrate files.
    if not os.environ.get("AWS_BUCKETNAME"):
        return
    env["ir.attachment"]._get_s3_bucket()
    env["ir.config_parameter"].set_param("ir_attachment.location", "s3")
    env["ir.attachment"].force_storage()
