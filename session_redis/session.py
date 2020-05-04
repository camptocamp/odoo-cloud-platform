# Copyright 2016-2019 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json
import logging

from werkzeug.contrib.sessions import SessionStore

from . import json_encoding

# this is equal to the duration of the session garbage collector in
# odoo.http.session_gc()
DEFAULT_SESSION_TIMEOUT = 60 * 60 * 24 * 7  # 7 days in seconds
DEFAULT_SESSION_TIMEOUT_ANONYMOUS = 60 * 60 * 3  # 3 hours in seconds

_logger = logging.getLogger(__name__)


class RedisSessionStore(SessionStore):
    """ SessionStore that saves session to redis """

    def __init__(self, redis, session_class=None,
                 prefix='', expiration=None, anon_expiration=None):
        super().__init__(session_class=session_class)
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

        data = json.dumps(
            dict(session), cls=json_encoding.SessionEncoder
        ).encode('utf-8')
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
            data = json.loads(
                saved.decode('utf-8'), cls=json_encoding.SessionDecoder
            )
        except ValueError:
            _logger.debug("session for key '%s' has been asked but its json "
                          "content could not be read, it has been reset", key)
            data = {}
        return self.session_class(data, sid, False)

    def list(self):
        keys = self.redis.keys('%s*' % self.prefix)
        _logger.debug("a listing redis keys has been called")
        return [key[len(self.prefix):] for key in keys]
