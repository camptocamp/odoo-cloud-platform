# Copyright 2016-2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import re
import os

from openerp.osv import osv
from openerp.addons.cloud_platform.models.cloud_platform import FilestoreKind
from openerp.addons.cloud_platform.models.cloud_platform import PlatformConfig


class CloudPlatform(osv.osv):
    _inherit = "cloud.platform"

    def _filestore_kinds(self):
        kinds = super(CloudPlatform, self)._filestore_kinds()
        kinds.append("azure")
        return kinds

    def _platform_kinds(self):
        kinds = super(CloudPlatform, self)._platform_kinds()
        kinds.append("azure")
        return kinds

    def _config_by_server_env_for_azure(self):
        fs_kinds = self._filestore_kinds()
        configs = {
            "prod": PlatformConfig(filestore=fs_kinds["azure"]),
            "integration": PlatformConfig(filestore=fs_kinds["azure"]),
            "labs": PlatformConfig(filestore=fs_kinds["azure"]),
            "test": PlatformConfig(filestore=fs_kinds["db"]),
            "dev": PlatformConfig(filestore=fs_kinds["db"]),
        }
        return configs

    def install_azure(self, cr, uid, context=None):
        self.install(cr, uid, "azure", context)
