# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
import os

from distutils.util import strtobool

import openerp
from openerp.addons.web import http
from werkzeug.contrib.sessions import Session

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
password = os.environ.get('ODOO_SESSION_REDIS_PASSWORD')
expiration = os.environ.get('ODOO_SESSION_REDIS_EXPIRATION')


def session_store():
    if sentinel_host:
        sentinel = Sentinel([(sentinel_host, sentinel_port)],
                            password=password)
        redis_client = sentinel.master_for(sentinel_master_name)
    else:
        redis_client = redis.Redis(host=host, port=port, password=password)
    return RedisSessionStore(redis=redis_client, prefix=prefix,
                             expiration=expiration,
                             session_class=Session)


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


if is_true(os.environ.get('ODOO_SESSION_REDIS')):
    if sentinel_host:
        _logger.debug("HTTP sessions stored in Redis with prefix '%s'. "
                      "Using Sentinel on %s:%s",
                      sentinel_host, sentinel_port, prefix or '')
    else:
        _logger.debug("HTTP sessions stored in Redis with prefix '%s' on "
                      "%s:%s", host, port, prefix or '')

    store = session_store()
    for handler in openerp.service.wsgi_server.module_handlers:
        if hasattr(handler, 'session_store'):
            handler.session_store = store
    http.session_gc = session_gc
    # clean the existing sessions on the file system
    purge_fs_sessions(http.session_path())
