# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os
import re

from collections import namedtuple
from distutils.util import strtobool

from openerp import api, models, SUPERUSER_ID


_logger = logging.getLogger(__name__)


def is_true(strval):
    return bool(strtobool(strval or '0'.lower()))


PlatformConfig = namedtuple(
    'PlatformConfig',
    'filestore'
)


FilestoreKind = namedtuple(
    'FilestoreKind',
    ['name', 'location']
)


class CloudPlatform(models.AbstractModel):
    _name = 'cloud.platform'

    @api.model
    def _default_config(self):
        return PlatformConfig(self._filestore_kinds()['db'])

    @api.model
    def _filestore_kinds(self):
        return {
            'db': FilestoreKind('db', 'local'),
            'file': FilestoreKind('file', 'local'),
        }

    @api.model
    def _platform_kinds(self):
        # XXX for backward compatibility, we need this one here, move
        # it in cloud_platform_exoscale in V11
        return ['exoscale']

    # XXX for backward compatibility, we need this one here, move
    # it in cloud_platform_exoscale in V11
    @api.model
    def _config_by_server_env_for_exoscale(self):
        configs = {
            'prod': PlatformConfig(filestore=FilestoreKind.s3),
            'integration': PlatformConfig(filestore=FilestoreKind.s3),
            'test': PlatformConfig(filestore=FilestoreKind.db),
            'dev': PlatformConfig(filestore=FilestoreKind.db),
        }
        return configs

    @api.model
    def _config_by_server_env(self, platform_kind, environment):
        configs_getter = getattr(
            self,
            '_config_by_server_env_for_%s' % platform_kind,
            None
        )
        configs = configs_getter() if configs_getter else {}
        return configs.get(environment) or self._default_config()

    # Due to the addition of the ovh cloud platform
    # This will be moved to cloud_platform_exoscale on v11
    @api.model
    def install_exoscale(self):
        self.install('exoscale')

    @api.model
    def _install(self, platform_kind):
        assert platform_kind in self._platform_kinds()
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('cloud.platform.kind', platform_kind)
        environment_name = self._get_running_env()
        configs = self._config_by_server_env(platform_kind, environment_name)
        params.set_param('ir_attachment.location', configs.filestore.name)
        self.check()
        if configs.filestore.location == 'remote':
            self.env['ir.attachment'].sudo().force_storage()
        _logger.info('cloud platform configured for {}'.format(platform_kind))

    @api.model
    def install(self):
        raise NotImplementedError

    @api.model
    def _check_filestore(self, environment_name):
        raise NotImplementedError

    @api.model
    def _check_redis(self, environment_name):
        if environment_name in ('prod', 'integration', 'test'):
            assert is_true(os.environ.get('ODOO_SESSION_REDIS')), (
                "Redis must be activated on prod, integration, test instances."
                "This is done by setting ODOO_SESSION_REDIS=1."
            )
            assert (os.environ.get('ODOO_SESSION_REDIS_HOST') or
                    os.environ.get('ODOO_SESSION_REDIS_SENTINEL_HOST')), (
                "ODOO_SESSION_REDIS_HOST or ODOO_SESSION_REDIS_SENTINEL_HOST "
                "environment variable is required to connect on Redis"
            )
            assert os.environ.get('ODOO_SESSION_REDIS_PREFIX'), (
                "ODOO_SESSION_REDIS_PREFIX environment variable is required "
                "to store sessions on Redis"
            )

            prefix = os.environ['ODOO_SESSION_REDIS_PREFIX']
            assert re.match(r'[a-z]+-odoo-[a-z]+', prefix), (
                "ODOO_SESSION_REDIS_PREFIX must match '<client>-odoo-<env>'"
                ", we got: '%s'" % (prefix,)
            )

    @api.model
    def check(self):
        if is_true(os.environ.get('ODOO_CLOUD_PLATFORM_UNSAFE')):
            _logger.warning(
                "cloud platform checks disabled, this is not safe"
            )
            return
        params = self.env['ir.config_parameter'].sudo()
        kind = params.get_param('cloud.platform.kind')
        if not kind:
            _logger.warning(
                "cloud platform not configured, you should "
                "probably run 'env['cloud.platform'].install()'"
            )
            return
        environment_name = self._get_running_env()
        self._check_filestore(environment_name)
        self._check_redis(environment_name)

    @api.cr
    def _register_hook(self, cr):
        super(CloudPlatform, self)._register_hook(cr)
        env = api.Environment(cr, SUPERUSER_ID, {})
        env['cloud.platform'].check()
