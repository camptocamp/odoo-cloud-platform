# -*- coding: utf-8 -*-
# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging

from openerp.osv import osv

_logger = logging.getLogger(__name__)

try:
    from openerp.addons.cloud_platform.models.cloud_platform \
        import FilestoreKind
    from openerp.addons.cloud_platform.models.cloud_platform \
        import PlatformConfig
except ImportError:
    FilestoreKind = None
    PlatformConfig = None
    _logger.debug("Cannot 'import from cloud_platform'")


class CloudPlatform(osv.osv_abstract):
    _inherit = 'cloud.platform'

    def _platform_kinds(self):
        kinds = super(CloudPlatform, self)._platform_kinds()
        kinds.append('ovh')
        return kinds

    def _config_by_server_env_for_ovh(self):
        configs = {
            'prod': PlatformConfig(filestore=FilestoreKind.swift),
            'integration': PlatformConfig(filestore=FilestoreKind.swift),
            'labs': PlatformConfig(filestore=FilestoreKind.swift),
            'test': PlatformConfig(filestore=FilestoreKind.db),
            'dev': PlatformConfig(filestore=FilestoreKind.db),
        }
        return configs

    def install_ovh(self, cr, uid, context=None):
        self.install(cr, uid, 'ovh', context)
