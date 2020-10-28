# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os
from odoo import models, api

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.cloud_platform.models.cloud_platform import FilestoreKind
    from odoo.addons.cloud_platform.models.cloud_platform import PlatformConfig
except ImportError:
    FilestoreKind = None
    PlatformConfig = None
    _logger.debug("Cannot 'import from cloud_platform'")


class CloudPlatform(models.AbstractModel):
    _inherit = 'cloud.platform'

    @api.model
    def _platform_kinds(self):
        kinds = super(CloudPlatform, self)._platform_kinds()
        kinds.append('gcp')
        return kinds

    @api.model
    def _config_by_server_env_for_gcp(self):
        configs = {
            'prod': PlatformConfig(filestore=FilestoreKind.s3),
            'integration': PlatformConfig(filestore=FilestoreKind.s3),
            'labs': PlatformConfig(filestore=FilestoreKind.s3),
            'test': PlatformConfig(filestore=FilestoreKind.db),
            'dev': PlatformConfig(filestore=FilestoreKind.db),
        }
        return configs

    # TODO: Assert that AWS_HOST is set to 'storage.googleapis.com'
    @api.model
    def check(self):
        assert os.environ.get('AWS_HOST') == 'storage.googleapis.com', (
            "AWS_ACCESS_KEY_ID environment variable is required when "
            "ir_attachment.location is 's3'."
        )
        assert int(os.environ.get('AWS_MULTIPART_THRESHOLD')) >= 8092, (
            "AWS_MULTIPART_THRESHOLD has to be set to max to disable multi-part operations "
            "in google cloud"
        )

    super(CloudPlatform, self).check()


    @api.model
    def install_gcp(self):
        self.install('gcp')
