# Copyright 2016-2021 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import os
import re

from odoo import api, models

from odoo.addons.cloud_platform.models.cloud_platform import (
    FilestoreKind,
    PlatformConfig,
)

AZURE_STORE_KIND = FilestoreKind("azure", "remote")


class CloudPlatform(models.AbstractModel):
    _inherit = "cloud.platform"

    @api.model
    def _filestore_kinds(self):
        kinds = super(CloudPlatform, self)._filestore_kinds()
        kinds["azure"] = AZURE_STORE_KIND
        return kinds

    @api.model
    def _platform_kinds(self):
        kinds = super(CloudPlatform, self)._platform_kinds()
        kinds.append("azure")
        return kinds

    @api.model
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

    @api.model
    def _check_filestore(self, environment_name):
        params = self.env["ir.config_parameter"].sudo()
        use_azure = params.get_param("ir_attachment.location") == AZURE_STORE_KIND.name
        if environment_name in ("prod", "integration"):
            # Labs instances use azure by default, but we don't want
            # to enforce it in case we want to test something with a different
            # storage. At your own risks!
            assert use_azure, (
                "azure must be used on production and integration instances. "
                "It is activated by setting 'ir_attachment.location.' to 'azure'."
                " The 'install()' function sets this option "
                "automatically."
            )
        if use_azure:
            key_sets = [
                ["AZURE_STORAGE_USE_AAD", "AZURE_STORAGE_ACCOUNT_URL"],
                ["AZURE_STORAGE_CONNECTION_STRING"],
                [
                    "AZURE_STORAGE_ACCOUNT_NAME",
                    "AZURE_STORAGE_ACCOUNT_URL",
                    "AZURE_STORAGE_ACCOUNT_KEY",
                ],
            ]
            is_valid = False
            for key_set in key_sets:
                if all([os.environ.get(key) for key in key_set]):
                    is_valid = True
                    break
            assert is_valid, (
                "When ir_attachment.location is set to 'azure', "
                "at least one of the following enviromnent variable set "
                "is required : {}".format(
                    " or ".join(
                        [" + ".join([key for key in key_set]) for key_set in key_sets]
                    )
                )
            )
            storage_name = os.environ.get("AZURE_STORAGE_NAME", "")
            if environment_name in ("prod", "integration", "labs"):
                assert storage_name, (
                    "AZURE_STORAGE_NAME environment variable is required when "
                    "ir_attachment.location is 'azure'.\n"
                    "Normally, 'azure' is activated on labs, integration "
                    "and production, but should not be used in dev environment"
                    " (or using a dedicated dev bucket, never using the "
                    "integration/prod bucket).\n"
                    "If you don't actually need a bucket, change the"
                    " 'ir_attachment.location' parameter."
                )
            # A bucket name is defined under the following format
            # ^[a-z]+\-[a-z]+\-\d+$
            # Anything other than prod bucket must be suffixed with env name
            #
            # Use AZURE_STORAGE_NAME_UNSTRUCTURED to by-pass check
            # on bucket name structure
            if os.environ.get("AZURE_STORAGE_NAME_UNSTRUCTURED"):
                return
            prod_bucket = bool(re.match(r"^[a-z]+\-[a-z]+\-\d+$", storage_name))
            if environment_name == "prod":
                assert prod_bucket, (
                    "AZURE_STORAGE_NAME should match '^[a-z]+\\-[a-z]+\\-\\d+$', "
                    "we got: '%s'" % (storage_name,)
                )
            else:
                # if we are using the prod bucket on another instance
                # such as an integration, we must be sure to be in read only!
                assert not prod_bucket, (
                    "AZURE_STORAGE_NAME should not match '^[a-z]+\\-[a-z]+\\-\\d+$', "
                    "we got: '%s'" % (storage_name,)
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
        self._install("azure")
