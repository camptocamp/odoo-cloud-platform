# Copyright 2016-2025 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os
import re
from collections import namedtuple

from odoo import api, models
from odoo.tools.config import config

from .strtobool import strtobool

_logger = logging.getLogger(__name__)


def is_true(strval):
    return bool(strtobool(strval or "0"))


class CloudPlatform(models.AbstractModel):
    _name = "cloud.platform"
    _description = "cloud.platform"

    def _get_running_env(self):
        environment_name = config["running_env"]
        if environment_name.startswith("labs"):
            # We allow to have environments such as 'labs-logistics'
            # or 'labs-finance', in order to have the matching ribbon.
            environment_name = "labs"
        return environment_name

    @api.model
    def _install(self, environment):
        self.check()
        _logger.info(f"cloud platform configured for {environment}")

    @api.model
    def _check_redis(self, environment_name):
        if environment_name in ("prod", "integration", "labs", "test"):
            assert is_true(os.environ.get("ODOO_SESSION_REDIS")), (
                "Redis must be activated on prod, integration, labs,"
                " test instances. This is done by setting ODOO_SESSION_REDIS=1."
            )
            assert (
                os.environ.get("ODOO_SESSION_REDIS_HOST")
                or os.environ.get("ODOO_SESSION_REDIS_SENTINEL_HOST")
                or os.environ.get("ODOO_SESSION_REDIS_URL")
            ), (
                "ODOO_SESSION_REDIS_HOST or "
                "ODOO_SESSION_REDIS_SENTINEL_HOST or "
                "ODOO_SESSION_REDIS_URL "
                "environment variable is required to connect on Redis"
            )
            assert os.environ.get("ODOO_SESSION_REDIS_PREFIX"), (
                "ODOO_SESSION_REDIS_PREFIX environment variable is required "
                "to store sessions on Redis"
            )

            prefix = os.environ["ODOO_SESSION_REDIS_PREFIX"]
            assert re.match(r"^[a-z-0-9]+-odoo-[a-z-0-9]+$", prefix), (
                "ODOO_SESSION_REDIS_PREFIX must match '<client>-odoo-<env>'"
                f", we got: '{prefix}'"
            )

    @api.model
    def check(self):
        environment_name = self._get_running_env()
        self._check_redis(environment_name)

    def _register_hook(self):
        super()._register_hook()
        self.sudo().check()
