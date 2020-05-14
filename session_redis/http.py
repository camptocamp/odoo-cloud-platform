# Copyright 2016-2018 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os

from distutils.util import strtobool

import odoo
from odoo import http
from odoo.tools.func import lazy_property

from .session import RedisSessionStore

_logger = logging.getLogger(__name__)

try:
    import redis
    from redis.sentinel import Sentinel
except ImportError:
    redis = None  # noqa
    _logger.debug("Cannot 'import redis'.")


def is_true(strval):
    return bool(strtobool(strval or '0'.lower()))


sentinel_host = os.environ.get('ODOO_SESSION_REDIS_SENTINEL_HOST')
sentinel_master_name = os.environ.get(
    'ODOO_SESSION_REDIS_SENTINEL_MASTER_NAME'
)
if sentinel_host and not sentinel_master_name:
    raise Exception(
        "ODOO_SESSION_REDIS_SENTINEL_MASTER_NAME must be defined "
        "when using session_redis"
    )
sentinel_port = int(os.environ.get('ODOO_SESSION_REDIS_SENTINEL_PORT', 26379))
host = os.environ.get('ODOO_SESSION_REDIS_HOST', 'localhost')
port = int(os.environ.get('ODOO_SESSION_REDIS_PORT', 6379))
prefix = os.environ.get('ODOO_SESSION_REDIS_PREFIX')
url = os.environ.get('ODOO_SESSION_REDIS_URL')
password = os.environ.get('ODOO_SESSION_REDIS_PASSWORD')
expiration = os.environ.get('ODOO_SESSION_REDIS_EXPIRATION')
anon_expiration = os.environ.get('ODOO_SESSION_REDIS_EXPIRATION_ANONYMOUS')


@lazy_property
def session_store(self):
    if sentinel_host:
        sentinel = Sentinel([(sentinel_host, sentinel_port)],
                            password=password)
        redis_client = sentinel.master_for(sentinel_master_name)
    elif url:
        redis_client = redis.from_url(url)
    else:
        redis_client = redis.Redis(host=host, port=port, password=password)
    return RedisSessionStore(redis=redis_client, prefix=prefix,
                             expiration=expiration,
                             anon_expiration=anon_expiration,
                             session_class=http.OpenERPSession)


def session_gc(session_store):
    """ Do not garbage collect the sessions

    Redis keys are automatically cleaned at the end of their
    expiration.
    """
    return


def purge_fs_sessions(path):
    for fname in os.listdir(path):
        path = os.path.join(path, fname)
        try:
            os.unlink(path)
        except OSError:
            pass


def copy_fs_sessions(path):
    from odoo.http import OpenERPSession
    from werkzeug.contrib.sessions import FilesystemSessionStore
    werkzeug_session_store = FilesystemSessionStore(path, session_class=OpenERPSession)
    session_store = http.Root().session_store
    filename_prefix_len = len('werkzeug_')
    filename_suffix_len = len('.sess')

    for fname in os.listdir(path):
        session_file = fname[filename_prefix_len:filename_suffix_len * -1]
        session = werkzeug_session_store.get(session_file)
        session_store.save(session)


if is_true(os.environ.get('ODOO_SESSION_REDIS')):
    if sentinel_host:
        _logger.debug("HTTP sessions stored in Redis with prefix '%s'. "
                      "Using Sentinel on %s:%s",
                      prefix or '', sentinel_host, sentinel_port)
    else:
        _logger.debug("HTTP sessions stored in Redis with prefix '%s' on "
                      "%s:%s", prefix or '', host, port)

    http.Root.session_store = session_store
    http.session_gc = session_gc

    if is_true(os.environ.get('ODOO_SESSION_REDIS_COPY_EXISTING_FS_SESSIONS')):
        copy_fs_sessions(odoo.tools.config.session_dir)
    if is_true(os.environ.get('ODOO_SESSION_REDIS_PURGE_EXISTING_FS_SESSIONS')):
        # clean the existing sessions on the file system
        purge_fs_sessions(odoo.tools.config.session_dir)
