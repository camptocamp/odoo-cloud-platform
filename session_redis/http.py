# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import glob
import logging
import os

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


def is_true(strval):
    return bool(strtobool(strval or "0".lower()))


sentinel_host = os.environ.get("ODOO_SESSION_REDIS_SENTINEL_HOST")
sentinel_master_name = os.environ.get("ODOO_SESSION_REDIS_SENTINEL_MASTER_NAME")
if sentinel_host and not sentinel_master_name:
    raise Exception(
        "ODOO_SESSION_REDIS_SENTINEL_MASTER_NAME must be defined "
        "when using session_redis"
    )
sentinel_port = int(os.environ.get("ODOO_SESSION_REDIS_SENTINEL_PORT", 26379))
host = os.environ.get("ODOO_SESSION_REDIS_HOST", "localhost")
port = int(os.environ.get("ODOO_SESSION_REDIS_PORT", 6379))
prefix = os.environ.get("ODOO_SESSION_REDIS_PREFIX")
url = os.environ.get("ODOO_SESSION_REDIS_URL")
password = os.environ.get("ODOO_SESSION_REDIS_PASSWORD")
expiration = os.environ.get("ODOO_SESSION_REDIS_EXPIRATION")
anon_expiration = os.environ.get("ODOO_SESSION_REDIS_EXPIRATION_ANONYMOUS")


@lazy_property
def session_store(self):
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
    # Same logic as odoo.http.FilesystemSessionStore.vacuum
    for fname in glob.iglob(os.path.join(path, '*', '*')):
        session_file = os.path.join(path, fname)
        try:
            os.unlink(session_file)
        except OSError:
            _logger.exception(f"OS Error during purge of old sessions: {session_file}")


if is_true(os.environ.get("ODOO_SESSION_REDIS")):
    if sentinel_host:
        _logger.debug(
            "HTTP sessions stored in Redis with prefix '%s'. "
            "Using Sentinel on %s:%s",
            prefix or "",
            sentinel_host,
            sentinel_port,
        )
    else:
        _logger.debug(
            "HTTP sessions stored in Redis with prefix '%s' on " "%s:%s",
            prefix or "",
            host,
            port,
        )
    target = http.Application
    if not hasattr(target, "session_store"):
        # Some other module (at least OCA/server-tools/sentry) has replaced
        # Application with a different object, hopefully wrapping it instead of
        # completely overwriting it
        # Try and see if we can extract the proper object from http.root instead
        if not hasattr(http.root, "session_store"):
            raise Exception(
                "session_redis: unable to find correct objects to patch for "
                "session management. Has another module overwritten "
                "odoo.http.Application with a different object?"
            )
        else:
            _logger.warning(
                "Extracting underlying web app object from odoo.http.root, as "
                "the actual Application object has been replaced. This may not "
                "work correctly: if you can affect load order, try to make "
                "session_redis load before other server-wide modules."
            )
            target = type(http.root)
    target.session_store = session_store
    # clean the existing sessions on the file system
    purge_fs_sessions(config.session_dir)
