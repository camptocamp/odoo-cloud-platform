# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os
import re

from collections import namedtuple
from .strtobool import strtobool

from odoo import api, models
from odoo.tools.config import config


_logger = logging.getLogger(__name__)


def is_true(strval):
    return bool(strtobool(strval or '0'))


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
    _description = 'cloud.platform'

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
        return []

    @api.model
    def _config_by_server_env(self, platform_kind, environment):
        configs_getter = getattr(
            self,
            '_config_by_server_env_for_%s' % platform_kind,
            None
        )
        configs = configs_getter() if configs_getter else {}
        return configs.get(environment) or self._default_config()

    def _get_running_env(self):
        environment_name = config['running_env']
        if environment_name.startswith('labs'):
            # We allow to have environments such as 'labs-logistics'
            # or 'labs-finance', in order to have the matching ribbon.
            environment_name = 'labs'
        return environment_name

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
        if environment_name in ('prod', 'integration', 'labs', 'test'):
            assert is_true(os.environ.get('ODOO_SESSION_REDIS')), (
                "Redis must be activated on prod, integration, labs,"
                " test instances. This is done by setting ODOO_SESSION_REDIS=1."
            )
            assert (os.environ.get('ODOO_SESSION_REDIS_HOST') or
                    os.environ.get('ODOO_SESSION_REDIS_SENTINEL_HOST') or
                    os.environ.get('ODOO_SESSION_REDIS_URL')), (
                "ODOO_SESSION_REDIS_HOST or "
                "ODOO_SESSION_REDIS_SENTINEL_HOST or "
                "ODOO_SESSION_REDIS_URL "
                "environment variable is required to connect on Redis"
            )
            assert os.environ.get('ODOO_SESSION_REDIS_PREFIX'), (
                "ODOO_SESSION_REDIS_PREFIX environment variable is required "
                "to store sessions on Redis"
            )

            prefix = os.environ['ODOO_SESSION_REDIS_PREFIX']
            assert re.match(r'^[a-z-0-9]+-odoo-[a-z-0-9]+$', prefix), (
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

    def _register_hook(self):
        super(CloudPlatform, self)._register_hook()
        self.sudo().check()
