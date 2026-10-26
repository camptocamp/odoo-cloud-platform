# Copyright 2016-2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
import logging
import os

from odoo.http import session as http_session
from odoo.tools import config

from .session import RedisSessionStore
from .strtobool import strtobool

_logger = logging.getLogger(__name__)

try:
    import redis
    from redis.sentinel import Sentinel
except ImportError:
    redis = None
    _logger.debug("Cannot 'import redis'.")


def is_true(strval):
    return bool(strtobool(strval or "0".lower()))


sentinel_host = os.getenv("ODOO_SESSION_REDIS_SENTINEL_HOST")
sentinel_master_name = os.getenv("ODOO_SESSION_REDIS_SENTINEL_MASTER_NAME")
if sentinel_host and not sentinel_master_name:
    raise ValueError(
        "ODOO_SESSION_REDIS_SENTINEL_MASTER_NAME must be defined "
        "when using session_redis"
    )
sentinel_port = int(os.getenv("ODOO_SESSION_REDIS_SENTINEL_PORT", "26379"))
host = os.getenv("ODOO_SESSION_REDIS_HOST", "localhost")
port = int(os.getenv("ODOO_SESSION_REDIS_PORT", "6379"))
prefix = os.getenv("ODOO_SESSION_REDIS_PREFIX")
url = os.getenv("ODOO_SESSION_REDIS_URL")
password = os.getenv("ODOO_SESSION_REDIS_PASSWORD")
expiration = os.getenv("ODOO_SESSION_REDIS_EXPIRATION")
anon_expiration = os.getenv("ODOO_SESSION_REDIS_EXPIRATION_ANONYMOUS")
# For non url connections
ssl = os.getenv("ODOO_SESSION_REDIS_SSL", "1")
ssl_cert_reqs = os.getenv("ODOO_SESSION_REDIS_SSL_CERT_REQS", "1")
redis_cluster = os.getenv("ODOO_SESSION_REDIS_CLUSTER", "0")


def redis_client():
    if sentinel_host:
        sentinel = Sentinel([(sentinel_host, sentinel_port)], password=password)
        return sentinel.master_for(sentinel_master_name)
    elif url:
        return redis.from_url(url)
    elif is_true(redis_cluster):
        return redis.RedisCluster(
            host=host,
            port=port,
            password=password,
            ssl=is_true(ssl),
            ssl_cert_reqs=is_true(ssl_cert_reqs),
        )
    else:
        return redis.Redis(
            host=host,
            port=port,
            password=password,
            ssl=is_true(ssl),
            ssl_cert_reqs=is_true(ssl_cert_reqs),
        )


class ConfiguredRedisSessionStore(RedisSessionStore):
    """RedisSessionStore configured from the environment variables

    Instantiated by odoo.http.session.session_store() with the same
    arguments as the filesystem session store it replaces.
    """

    def __init__(self, path=None, session_cls=http_session.Session):
        super().__init__(
            path=path,
            session_cls=session_cls,
            redis=redis_client(),
            prefix=prefix,
            expiration=expiration,
            anon_expiration=anon_expiration,
        )


def purge_fs_sessions(path):
    if not os.path.isdir(path):
        _logger.warning(f"Session directory '{path}' does not exist.")
        return

    for fname in os.listdir(path):
        path = os.path.join(path, fname)
        try:
            os.unlink(path)
        except OSError:
            _logger.warning("OS Error during purge of redis sessions.")


if is_true(os.getenv("ODOO_SESSION_REDIS")):
    if sentinel_host:
        _logger.debug(
            "HTTP sessions stored in Redis with prefix '%s'. Using Sentinel on %s:%s",
            prefix or "",
            sentinel_host,
            sentinel_port,
        )
    else:
        _logger.debug(
            "HTTP sessions stored in Redis with prefix '%s' on %s:%s",
            prefix or "",
            host,
            port,
        )
    # odoo.http.session.session_store() is a cached factory imported by name
    # in many places: replace the class it instantiates and drop the cached
    # filesystem store so that every caller gets the redis one.
    http_session.SessionStore = ConfiguredRedisSessionStore
    http_session.session_store.cache_clear()
    # clean the existing sessions on the file system
    purge_fs_sessions(config.session_dir)
