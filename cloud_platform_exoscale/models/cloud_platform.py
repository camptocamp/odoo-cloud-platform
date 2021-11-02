# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import re
import os

from odoo import models, api
from odoo.addons.cloud_platform.models.cloud_platform import FilestoreKind
from odoo.addons.cloud_platform.models.cloud_platform import PlatformConfig


S3_STORE_KIND = FilestoreKind('s3', 'remote')


class CloudPlatform(models.AbstractModel):
    _inherit = 'cloud.platform'

    @api.model
    def _filestore_kinds(self):
        kinds = super(CloudPlatform, self)._filestore_kinds()
        kinds['s3'] = S3_STORE_KIND
        return kinds

    @api.model
    def _platform_kinds(self):
        kinds = super(CloudPlatform, self)._platform_kinds()
        kinds.append('exoscale')
        return kinds

    @api.model
    def _config_by_server_env_for_exoscale(self):
        fs_kinds = self._filestore_kinds()
        configs = {
            'prod': PlatformConfig(filestore=fs_kinds['s3']),
            'integration': PlatformConfig(filestore=fs_kinds['s3']),
            'labs': PlatformConfig(filestore=fs_kinds['s3']),
            'test': PlatformConfig(filestore=fs_kinds['db']),
            'dev': PlatformConfig(filestore=fs_kinds['db']),
        }
        return configs

    @api.model
    def _check_filestore(self, environment_name):
        params = self.env['ir.config_parameter'].sudo()
        use_s3 = (params.get_param('ir_attachment.location') ==
                  S3_STORE_KIND.name)
        if environment_name in ('prod', 'integration'):
            # Labs instances use s3 by default, but we don't want
            # to enforce it in case we want to test something with a different
            # storage. At your own risks!
            assert use_s3, (
                "S3 must be used on production and integration instances. "
                "It is activated by setting 'ir_attachment.location.' to 's3'."
                " The 'install()' function sets this option "
                "automatically."
            )
        if use_s3:
            assert os.environ.get('AWS_ACCESS_KEY_ID'), (
                "AWS_ACCESS_KEY_ID environment variable is required when "
                "ir_attachment.location is 's3'."
            )
            assert os.environ.get('AWS_SECRET_ACCESS_KEY'), (
                "AWS_SECRET_ACCESS_KEY environment variable is required when "
                "ir_attachment.location is 's3'."
            )
            bucket_name = os.environ.get('AWS_BUCKETNAME', '')
            if environment_name in ('prod', 'integration', 'labs'):
                assert bucket_name, (
                    "AWS_BUCKETNAME environment variable is required when "
                    "ir_attachment.location is 's3'.\n"
                    "Normally, 's3' is activated on labs, integration "
                    "and production, but should not be used in dev environment"
                    " (or using a dedicated dev bucket, never using the "
                    "integration/prod bucket).\n"
                    "If you don't actually need a bucket, change the"
                    " 'ir_attachment.location' parameter."
                )
            # A bucket name is defined under the following format
            # <client>-odoo-<env>
            #
            # Use AWS_BUCKETNAME_UNSTRUCTURED to by-pass check on bucket name
            # structure
            if os.environ.get('AWS_BUCKETNAME_UNSTRUCTURED'):
                return
            prod_bucket = bool(re.match(r'[a-z-0-9]+-odoo-prod', bucket_name))
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
            assert params.get_param('ir_attachment.location') == 'db', (
                "In test instances, files must be stored in the database with "
                "'ir_attachment.location' set to 'db'. This is "
                "automatically set by the function 'install()'."
            )

    @api.model
    def install(self):
        self._install('exoscale')
