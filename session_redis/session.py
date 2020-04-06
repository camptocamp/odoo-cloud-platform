# Copyright 2016-2018 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import datetime
import json
import logging

from werkzeug.contrib.sessions import SessionStore

from odoo import fields

# this is equal to the duration of the session garbage collector in
# odoo.http.session_gc()
DEFAULT_SESSION_TIMEOUT = 60 * 60 * 24 * 7  # 7 days in seconds
DEFAULT_SESSION_TIMEOUT_ANONYMOUS = 60 * 60 * 3  # 3 hours in seconds

_logger = logging.getLogger(__name__)


class RedisSessionStore(SessionStore):
    """ SessionStore that saves session to redis """

    py_date_prefix = '__py__date_'
    py_datetime_prefix = '__py__datetime_'
    py_set_prefix = '__py__set'

    def __init__(self, redis, session_class=None,
                 prefix='', expiration=None, anon_expiration=None):
        super(RedisSessionStore, self).__init__(session_class=session_class)
        self.redis = redis
        if expiration is None:
            self.expiration = DEFAULT_SESSION_TIMEOUT
        else:
            self.expiration = expiration
        if anon_expiration is None:
            self.anon_expiration = DEFAULT_SESSION_TIMEOUT_ANONYMOUS
        else:
            self.anon_expiration = anon_expiration
        self.prefix = 'session:'
        if prefix:
            self.prefix = '%s:%s:' % (
                self.prefix, prefix
            )

    def session_json_pack(self, session):
        """Attempt to store python objects as json serializable values"""
        session_jsonified = {}
        for key, val in session.items():
            if isinstance(val, datetime.datetime):
                key = self.py_datetime_prefix + key
                val = fields.Datetime.to_string(val)
            elif isinstance(val, datetime.date):
                key = self.py_date_prefix + key
                val = fields.Date.to_string(val)
            elif isinstance(val, set):
                key = self.py_set_prefix + key
                val = list(val)
            session_jsonified[key] = val
        return session_jsonified

    def session_json_unpack(self, session):
        """Attempt to restore python objects from json serialized vals"""
        session_py = {}
        for key, val in session.items():
            if key.startswith(self.py_datetime_prefix):
                key = key.split(self.py_datetime_prefix)[1]
                val = fields.Datetime.from_string(val)
            elif key.startswith(self.py_date_prefix):
                key = key.split(self.py_date_prefix)[1]
                val = fields.Date.from_string(val)
            elif key.startswith(self.py_set_prefix):
                key = key.split(self.py_set_prefix)[1]
                val = set(val)
            session_py[key] = val
        return session_py

    def build_key(self, sid):
        return '%s%s' % (self.prefix, sid)

    def save(self, session):
        key = self.build_key(session.sid)

        # allow to set a custom expiration for a session
        # such as a very short one for monitoring requests
        if session.uid:
            expiration = session.expiration or self.expiration
        else:
            expiration = session.expiration or self.anon_expiration
        if _logger.isEnabledFor(logging.DEBUG):
            if session.uid:
                user_msg = "user '%s' (id: %s)" % (
                    session.login, session.uid)
            else:
                user_msg = "anonymous user"
            _logger.debug("saving session with key '%s' and "
                          "expiration of %s seconds for %s",
                          key, expiration, user_msg)

        session_jsonified = self.session_json_pack(dict(session))
        data = json.dumps(session_jsonified).encode('utf-8')
        if self.redis.set(key, data):
            return self.redis.expire(key, expiration)

    def delete(self, session):
        key = self.build_key(session.sid)
        _logger.debug('deleting session with key %s', key)
        return self.redis.delete(key)

    def get(self, sid):
        if not self.is_valid_key(sid):
            _logger.debug("session with invalid sid '%s' has been asked, "
                          "returning a new one", sid)
            return self.new()

        key = self.build_key(sid)
        saved = self.redis.get(key)
        if not saved:
            _logger.debug("session with non-existent key '%s' has been asked, "
                          "returning a new one", key)
            return self.new()
        try:
            data = json.loads(saved.decode('utf-8'))
            data = self.session_json_unpack(data)
        except ValueError:
            _logger.debug("session for key '%s' has been asked but its json "
                          "content could not be read, it has been reset", key)
            data = {}
        return self.session_class(data, sid, False)

    def list(self):
        keys = self.redis.keys('%s*' % self.prefix)
        _logger.debug("a listing redis keys has been called")
        return [key[len(self.prefix):] for key in keys]
