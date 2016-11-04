# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os
import re

from collections import namedtuple

from distutils.util import strtobool

from openerp import api, models, SUPERUSER_ID
from openerp.tools.config import config


_logger = logging.getLogger(__name__)


def is_true(strval):
    return bool(strtobool(strval or '0'.lower()))


PlatformConfig = namedtuple(
    'PlatformConfig',
    'filestore'
)


class FilestoreKind(object):
    db = 'db'
    s3 = 's3'  # or compatible s3 object storage
    file = 'file'


class CloudPlatform(models.AbstractModel):
    _name = 'cloud.platform'

    @api.model
    def _config_by_server_env(self, environment):
        configs = {
            'prod': PlatformConfig(filestore=FilestoreKind.s3),
            'integration': PlatformConfig(filestore=FilestoreKind.s3),
            'test': PlatformConfig(filestore=FilestoreKind.db),
            'dev': PlatformConfig(filestore=FilestoreKind.db),
        }
        return configs.get(environment) or configs['dev']

    @api.model
    def install_exoscale(self):
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('cloud.platform.kind', 'exoscale')
        environment = config['running_env']
        configs = self._config_by_server_env(environment)
        params.set_param('ir_attachment.location', configs.filestore)
        self.check()
        if configs.filestore == FilestoreKind.s3:
            self.env['ir.attachment'].sudo().force_storage()
        _logger.info('cloud platform configured for exoscale')

    @api.model
    def _check_s3(self, environment_name):
        params = self.env['ir.config_parameter'].sudo()
        use_s3 = params.get_param('ir_attachment.location') == FilestoreKind.s3
        if environment_name in ('prod', 'integration'):
            assert use_s3
        if use_s3:
            assert os.environ.get('AWS_ACCESS_KEY_ID')
            assert os.environ.get('AWS_SECRET_ACCESS_KEY')
            assert os.environ.get('AWS_BUCKETNAME')
            bucket_name = os.environ['AWS_BUCKETNAME']
            prod_bucket = bool(re.match(r'[a-z]+-odoo-prod', bucket_name))
            if environment_name == 'prod':
                assert prod_bucket, (
                    "AWS_BUCKETNAME should match '<client>-odoo-prod', "
                    "we got: '%s'" % (bucket_name,)
                )
            else:
                # if we are using the prod bucket on another instance
                # such as an integration, we must be sure to be in read only!
                assert not prod_bucket, (
                    "AWS_BUCKETNAME should not match '<client>-odoo-prod', "
                    "we got: '%s'" % (bucket_name,)
                )

        elif environment_name == 'test':
            # store in DB so we don't have files local to the host
            assert params.get_param('ir_attachment.location') == 'db'

    @api.model
    def _check_redis(self, environment_name):
        if environment_name in ('prod', 'integration', 'test'):
            assert is_true(os.environ.get('ODOO_SESSION_REDIS'))
            assert os.environ.get('ODOO_SESSION_REDIS_HOST')
            assert os.environ.get('ODOO_SESSION_REDIS_PREFIX')
            prefix = os.environ['ODOO_SESSION_REDIS_PREFIX']
            assert re.match(r'[a-z]+-odoo-[a-z]+', prefix), (
                "ODOO_SESSION_REDIS_PREFIX should match '<client>-odoo-<env>'"
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
                "probably run 'env['cloud.platform'].install_exoscale()'"
            )
            return
        environment_name = config['running_env']
        self._check_s3(environment_name)
        self._check_redis(environment_name)

    @api.cr
    def _register_hook(self, cr):
        super(CloudPlatform, self)._register_hook(cr)
        env = api.Environment(cr, SUPERUSER_ID, {})
        env['cloud.platform'].check()
