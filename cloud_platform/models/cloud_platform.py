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
    'filestore filestore_readonly'
)


class FilestoreKind(object):
    db = 'db'
    s3 = 's3://'  # or compatible s3 object storage
    file = 'file'



class CloudPlatform(models.AbstractModel):
    _name = 'cloud.platform'

    @api.model
    def _config_by_server_env(self, environment):
        configs = {
            'prod': PlatformConfig(filestore=FilestoreKind.s3,
                                   filestore_readonly=False),
            'integration': PlatformConfig(filestore=FilestoreKind.s3,
                                          filestore_readonly=True),
            'test': PlatformConfig(filestore=FilestoreKind.db,
                                   filestore_readonly=True),
            'dev': PlatformConfig(filestore=FilestoreKind.db,
                                  filestore_readonly=True),
        }
        return configs.get(environment) or configs['dev']

    @api.model
    def install_exoscale(self):
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('cloud.platform.kind', 'exoscale')
        environment = config['running_env']
        configs = self._config_by_server_env(environment)
        params.set_param('ir_attachment.location', configs.filestore)
        self.check(self.env)
        if configs.filestore == FilestoreKind.s3:
            self.env['ir.attachment'].sudo().force_storage()
        _logger.info('cloud platform configured for exoscale')

    @api.model
    def _check_s3(self, environment_name):
        params = self.env['ir.config_parameter'].sudo()
        attachment_readonly = is_true(
            os.environ.get('AWS_ATTACHMENT_READONLY')
        )
        if environment_name in ('prod', 'integration'):
            assert os.environ.get('AWS_ACCESS_KEY_ID')
            assert os.environ.get('AWS_SECRET_ACCESS_KEY')
            assert os.environ.get('AWS_BUCKETNAME')
            bucket_name = os.environ['AWS_BUCKETNAME']
            assert re.match(r'[a-z]+-odoo-prod', bucket_name), (
                "AWS_BUCKETNAME should match '<client>-odoo-prod', "
                "we got: '%s'" % (bucket_name,)
            )
            assert params.get_param('ir_attachment.location') == 's3://'
            # on the integration, we read the filestore from the production
            # s3, but we must be readonly!
            if environment_name == 'integration':
                assert attachment_readonly
            else:
                assert not attachment_readonly
        elif environment_name == 'test':
            assert params.get_param('ir_attachment.location') == 'db'
        else:
            assert params.get_param('ir_attachment.location') in ('db', 'file')

    @api.model
    def _check_redis(self, environment_name):
        assert is_true(os.environ.get('ODOO_SESSION_REDIS'))
        assert os.environ.get('ODOO_SESSION_REDIS_HOST')
        assert os.environ.get('ODOO_SESSION_REDIS_PREFIX')
        prefix = os.environ['ODOO_SESSION_REDIS_PREFIX']
        if environment_name in ('prod', 'integration', 'test'):
            assert re.match(r'[a-z]+-odoo-%s' % (environment_name,), prefix), (
                "ODOO_SESSION_REDIS_PREFIX should match '<client>-odoo-%s', "
                "we got: '%s'" % (environment_name, prefix)
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
        env = api.Environment(cr, SUPERUSER_ID, {})
        env['cloud.platform'].check()
