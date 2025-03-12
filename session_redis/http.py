# Copyright 2016-2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os
from pathlib import Path
from typing import Optional

from odoo import http
from odoo.tools import config
from odoo.tools.func import lazy_property

from .session import RedisSessionStore
from .strtobool import strtobool

_logger = logging.getLogger(__name__)

try:
    import redis
    from redis.sentinel import Sentinel
except ImportError:
    redis = None  # noqa
    _logger.debug("Cannot 'import redis'.")


def is_true(strval: Optional[str]) -> bool:
    """Convert string value to boolean."""
    return bool(strtobool((strval or "0").lower()))


sentinel_host = os.getenv("ODOO_SESSION_REDIS_SENTINEL_HOST")
sentinel_master_name = os.getenv("ODOO_SESSION_REDIS_SENTINEL_MASTER_NAME")
if sentinel_host and not sentinel_master_name:
    raise Exception(
        "ODOO_SESSION_REDIS_SENTINEL_MASTER_NAME must be defined "
        "when using session_redis"
    )
sentinel_port = int(os.getenv("ODOO_SESSION_REDIS_SENTINEL_PORT", 26379))
host = os.getenv("ODOO_SESSION_REDIS_HOST", "localhost")
port = int(os.getenv("ODOO_SESSION_REDIS_PORT", 6379))
prefix = os.getenv("ODOO_SESSION_REDIS_PREFIX")
url = os.getenv("ODOO_SESSION_REDIS_URL")
password = os.getenv("ODOO_SESSION_REDIS_PASSWORD")
expiration = os.getenv("ODOO_SESSION_REDIS_EXPIRATION")
anon_expiration = os.getenv("ODOO_SESSION_REDIS_EXPIRATION_ANONYMOUS")


@lazy_property
def session_store(self) -> RedisSessionStore:
    """Configure Redis session storage."""
    if sentinel_host:
        sentinel = Sentinel([(sentinel_host, sentinel_port)], password=password)
        redis_client = sentinel.master_for(sentinel_master_name)
    elif url:
        redis_client = redis.from_url(url)
    else:
        redis_client = redis.Redis(host=host, port=port, password=password)
    return RedisSessionStore(
        redis=redis_client,
        prefix=prefix,
        expiration=expiration,
        anon_expiration=anon_expiration,
        session_class=http.Session,
    )


def purge_fs_sessions(path):
    """Remove old file-based sessions."""
    session_path = Path(path)
    if not session_path.exists():
        _logger.warning(f"Session directory '{session_path}' does not exist.")
        return

    for session_file in session_path.iterdir():
        try:
            session_file.unlink()
            _logger.debug(f"Deleted session file: {session_file}")
        except PermissionError:
            _logger.warning(
                f"Permission denied while deleting session file: {session_file}"
            )
        except OSError as e:
            _logger.warning(f"Error deleting session file {session_file}: {str(e)}")


if is_true(os.getenv("ODOO_SESSION_REDIS")):
    storage_info = f"Redis with prefix '{prefix}' on "
    if sentinel_host:
        storage_info += f"Sentinel {sentinel_host}:{sentinel_port}"
    else:
        storage_info += f"{host}:{port}"

    _logger.debug("HTTP sessions stored in %s.", storage_info)

    http.Application.session_store = session_store

    # Clean existing sessions stored in the file system
    purge_fs_sessions(config.session_dir)
