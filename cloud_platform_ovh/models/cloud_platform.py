# Copyright 2017-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import os
import re

from odoo import api, models

from odoo.addons.cloud_platform.models.cloud_platform import (
    FilestoreKind,
    PlatformConfig,
)

SWIFT_STORE_KIND = FilestoreKind("swift", "remote")


class CloudPlatform(models.AbstractModel):
    _inherit = "cloud.platform"

    @api.model
    def _filestore_kinds(self):
        kinds = super(CloudPlatform, self)._filestore_kinds()
        kinds["swift"] = SWIFT_STORE_KIND
        return kinds

    @api.model
    def _platform_kinds(self):
        kinds = super()._platform_kinds()
        kinds.append("ovh")
        return kinds

    @api.model
    def _config_by_server_env_for_ovh(self):
        fs_kinds = self._filestore_kinds()
        configs = {
            "prod": PlatformConfig(filestore=fs_kinds["swift"]),
            "integration": PlatformConfig(filestore=fs_kinds["swift"]),
            "labs": PlatformConfig(filestore=fs_kinds["swift"]),
            "test": PlatformConfig(filestore=fs_kinds["db"]),
            "dev": PlatformConfig(filestore=fs_kinds["db"]),
        }
        return configs

    @api.model
    def _check_filestore(self, environment_name):
        params = self.env["ir.config_parameter"].sudo()
        use_swift = params.get_param("ir_attachment.location") == SWIFT_STORE_KIND.name
        if environment_name in ("prod", "integration"):
            # Labs instances use swift by default, but we don't want
            # to enforce it in case we want to test something with a different
            # storage. At your own risks!
            assert use_swift, (
                "Swift must be used on production and integration instances. "
                "It is activated, setting 'ir_attachment.location.' to 'swift'"
                " The 'install()' function sets this option "
                "automatically."
            )
        if use_swift:
            assert os.environ.get("SWIFT_AUTH_URL"), (
                "SWIFT_AUTH_URL environment variable is required when "
                "ir_attachment.location is 'swift'."
            )
            assert os.environ.get("SWIFT_ACCOUNT"), (
                "SWIFT_ACCOUNT environment variable is required when "
                "ir_attachment.location is 'swift'."
            )
            assert os.environ.get("SWIFT_PASSWORD"), (
                "SWIFT_PASSWORD environment variable is required when "
                "ir_attachment.location is 'swift'."
            )
            container_name = os.environ.get("SWIFT_WRITE_CONTAINER", "")
            if environment_name in ("prod", "integration", "labs"):
                assert container_name, (
                    "SWIFT_WRITE_CONTAINER environment variable is required when "
                    "ir_attachment.location is 'swift'.\n"
                    "Normally, 'swift' is activated on labs, integration "
                    "and production, but should not be used in dev environment"
                    " (or using a dedicated dev bucket, never using the "
                    "integration/prod bucket).\n"
                    "If you don't actually need a bucket, change the"
                    " 'ir_attachment.location' parameter."
                )
            prod_container = bool(re.match(r"[a-z0-9-]+-odoo-prod", container_name))
            # A bucket name is defined under the following format
            # <client>-odoo-<env>
            #
            # Use SWIFT_WRITE_CONTAINER_UNSTRUCTURED to by-pass check on bucket name
            # structure
            if os.environ.get("SWIFT_WRITE_CONTAINER_UNSTRUCTURED"):
                return
            if environment_name == "prod":
                assert prod_container, (
                    "SWIFT_WRITE_CONTAINER should match '<client>-odoo-prod', "
                    "we got: '%s'" % (container_name,)
                )
            else:
                # if we are using the prod bucket on another instance
                # such as an integration, we must be sure to be in read only!
                assert not prod_container, (
                    "SWIFT_WRITE_CONTAINER should not match "
                    "'<client>-odoo-prod', we got: '%s'" % (container_name,)
                )
        elif environment_name == "test":
            # store in DB so we don't have files local to the host
            assert params.get_param("ir_attachment.location") == "db", (
                "In test instances, files must be stored in the database with "
                "'ir_attachment.location' set to 'db'. This is "
                "automatically set by the function 'install()'."
            )

    @api.model
    def install(self):
        self._install("ovh")
