# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os
import re

from collections import namedtuple

from distutils.util import strtobool

from openerp import SUPERUSER_ID
from openerp.osv import osv
from openerp.tools.config import config


_logger = logging.getLogger(__name__)


def is_true(strval):
    return bool(strtobool(strval or "0".lower()))


PlatformConfig = namedtuple("PlatformConfig", "filestore")


class FilestoreKind(object):
    db = "db"
    s3 = "s3"  # or compatible s3 object storage
    swift = "swift"
    file = "file"
    azure = "azure"


class CloudPlatform(osv.osv_abstract):
    _name = "cloud.platform"

    def _platform_kinds(self):
        # XXX for backward compatibility, we need this one here, move
        # it in cloud_platform_exoscale in V11
        return ["exoscale"]

    def _filestore_kinds(self):
        # XXX for backward compatibility, we need this one here, move
        # it in cloud_platform_exoscale in V11
        return ["exoscale"]

    # XXX for backward compatibility, we need this one here, move
    # it in cloud_platform_exoscale in V11
    def _config_by_server_env_for_exoscale(self):
        configs = {
            "prod": PlatformConfig(filestore=FilestoreKind.s3),
            "integration": PlatformConfig(filestore=FilestoreKind.s3),
            "test": PlatformConfig(filestore=FilestoreKind.db),
            "dev": PlatformConfig(filestore=FilestoreKind.db),
        }
        return configs

    def _config_by_server_env(self, platform_kind, environment):
        configs_getter = getattr(
            self, "_config_by_server_env_for_%s" % platform_kind, None
        )
        configs = configs_getter() if configs_getter else {}
        return configs.get(environment) or FilestoreKind.db

    def _get_running_env(self):
        environment_name = config["running_env"]
        if environment_name.startswith("labs"):
            # We allow to have environments such as 'labs-logistics'
            # or 'labs-finance', in order to have the matching ribbon.
            environment_name = "labs"
        return environment_name

    # Due to the addition of the ovh cloud platform
    # This will be moved to cloud_platform_exoscale on v11
    def install_exoscale(self, cr, uid, context=None):
        self.install(cr, uid, "exoscale", context)

    def install(self, cr, uid, platform_kind, context=None):
        assert platform_kind in self._platform_kinds()
        params = self.pool.get("ir.config_parameter")
        params.set_param(
            cr, SUPERUSER_ID, "cloud.platform.kind", platform_kind, context=context
        )
        environment_name = self._get_running_env()
        configs = self._config_by_server_env(platform_kind, environment_name)
        params.set_param(
            cr,
            SUPERUSER_ID,
            "ir_attachment.location",
            configs.filestore,
            context=context,
        )
        self.check(cr, uid, context)
        if configs.filestore in [FilestoreKind.swift, FilestoreKind.s3]:
            self.pool.get("ir.attachment").force_storage(
                cr, SUPERUSER_ID, context=context
            )
        _logger.info("cloud platform configured for {}".format(platform_kind))

    def _check_swift(self, cr, uid, environment_name, context=None):
        params = self.pool.get("ir.config_parameter")
        use_swift = (
            params.get_param(
                cr, SUPERUSER_ID, "ir_attachment.location", context=context
            )
            == FilestoreKind.swift
        )
        if environment_name in ("prod", "integration"):
            # Labs instances use swift or s3 by default, but we don't want
            # to enforce it in case we want to test something with a different
            # storage. At your own risks!
            assert use_swift, (
                "Swift must be used on production and integration instances. "
                "It is activated, setting 'ir_attachment.location.' to 'swift'"
                " The 'install_exoscale()' function sets this option "
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
            container_name = os.environ.get("SWIFT_WRITE_CONTAINER")
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
            assert (
                params.get_param(
                    cr, SUPERUSER_ID, "ir_attachment.location", context=context
                )
                == "db"
            ), (
                "In test instances, files must be stored in the database with "
                "'ir_attachment.location' set to 'db'. This is "
                "automatically set by the function 'install_ovh()'."
            )

    def _check_s3(self, cr, uid, environment_name, context=None):
        params = self.pool.get("ir.config_parameter")
        use_s3 = (
            params.get_param(
                cr, SUPERUSER_ID, "ir_attachment.location", context=context
            )
            == FilestoreKind.s3
        )
        if environment_name in ("prod", "integration"):
            # Labs instances use swift or s3 by default, but we don't want
            # to enforce it in case we want to test something with a different
            # storage. At your own risks!
            assert use_s3, (
                "S3 must be used on production and integration instances. "
                "It is activated by setting 'ir_attachment.location.' to 's3'."
                " The 'install_exoscale()' function sets this option "
                "automatically."
            )
        if use_s3:
            assert os.environ.get("AWS_ACCESS_KEY_ID"), (
                "AWS_ACCESS_KEY_ID environment variable is required when "
                "ir_attachment.location is 's3'."
            )
            assert os.environ.get("AWS_SECRET_ACCESS_KEY"), (
                "AWS_SECRET_ACCESS_KEY environment variable is required when "
                "ir_attachment.location is 's3'."
            )
            bucket_name = os.environ.get("AWS_BUCKETNAME")
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
            prod_bucket = bool(re.match(r"[a-z-0-9]+-odoo-prod", bucket_name))
            if environment_name == "prod":
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

        elif environment_name == "test":
            # store in DB so we don't have files local to the host
            assert (
                params.get_param(
                    cr, SUPERUSER_ID, "ir_attachment.location", context=context
                )
                == "db"
            ), (
                "In test instances, files must be stored in the database with "
                "'ir_attachment.location' set to 'db'. This is "
                "automatically set by the function 'install_exoscale()'."
            )

    def _check_azure(self, cr, uid, environment_name, context=None):
        params = self.pool.get("ir.config_parameter")
        use_azure = (
            params.get_param(
                cr, SUPERUSER_ID, "ir_attachment.location", context=context
            )
            == FilestoreKind.azure
        )
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
            assert (
                params.get_param(
                    cr, SUPERUSER_ID, "ir_attachment.location", context=context
                )
                == "db"
            ), (
                "In test instances, files must be stored in the database with "
                "'ir_attachment.location' set to 'db'. This is "
                "automatically set by the function 'install()'."
            )

    def _check_redis(self, cr, uid, environment_name, context=None):
        if environment_name in ("prod", "integration", "labs", "test"):
            assert is_true(os.environ.get("ODOO_SESSION_REDIS")), (
                "Redis must be activated on prod, integration, labs,"
                " test instances. This is done by setting ODOO_SESSION_REDIS=1."
            )
            assert os.environ.get("ODOO_SESSION_REDIS_URL") or os.environ.get(
                "ODOO_SESSION_REDIS_SENTINEL_URL"
            ), (
                "ODOO_SESSION_REDIS_URL or ODOO_SESSION_REDIS_SENTINEL_URL "
                "environment variable is required to connect on Redis"
            )
            assert os.environ.get("ODOO_SESSION_REDIS_PREFIX"), (
                "ODOO_SESSION_REDIS_PREFIX environment variable is required "
                "to store sessions on Redis"
            )

            prefix = os.environ["ODOO_SESSION_REDIS_PREFIX"]
            assert re.match(r"^[a-z-0-9]+-odoo-[a-z-0-9]+$", prefix), (
                "ODOO_SESSION_REDIS_PREFIX must match '<client>-odoo-<env>'"
                ", we got: '%s'" % (prefix,)
            )

    def check(self, cr, uid, context=None):
        if is_true(os.environ.get("ODOO_CLOUD_PLATFORM_UNSAFE")):
            _logger.warning("cloud platform checks disabled, this is not safe")
            return
        params = self.pool.get("ir.config_parameter")
        kind = params.get_param(cr, SUPERUSER_ID, "cloud.platform.kind", context=None)
        if not kind:
            _logger.warning(
                "cloud platform not configured, you should "
                "probably run 'env['cloud.platform'].install_exoscale()'"
            )
            return
        environment_name = self._get_running_env()
        if kind == "exoscale":
            self._check_s3(cr, uid, environment_name, context)
        elif kind == "ovh":
            self._check_swift(cr, uid, environment_name, context)
        elif kind == "azure":
            self._check_azure(cr, uid, environment_name, context)
        self._check_redis(cr, uid, environment_name, context)

    def _register_hook(self, cr):
        super(CloudPlatform, self)._register_hook(cr)
        self.pool.get("cloud.platform").check(cr, SUPERUSER_ID)
