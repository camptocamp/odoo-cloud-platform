# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from pickle import dumps, loads, HIGHEST_PROTOCOL
import logging

from werkzeug.contrib.sessions import SessionStore

# this is equal to the duration of the session garbage collector in
# openerp.http.session_gc()
DEFAULT_SESSION_TIMEOUT = 60 * 60 * 24 * 7  # 7 days in seconds
DEFAULT_SESSION_TIMEOUT_ANONYMOUS = 60 * 60 * 3  # 3 hours in seconds

_logger = logging.getLogger(__name__)


class RedisSessionStore(SessionStore):
    """ SessionStore that saves session to redis """

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
        self.prefix = u'session:'
        if prefix:
            self.prefix = u'%s:%s:' % (
                self.prefix, prefix
            )

    def build_key(self, sid):
        if isinstance(sid, unicode):
            sid = sid.encode('utf-8')
        return '%s%s' % (self.prefix, sid)

    def save(self, session):
        key = self.build_key(session.sid)
        # `session` is the Werkzeug wrapper that contains
        # the "real" session object `OpenERPSession`.
        # That's why we need to look for the first item in it to get the
        # expiration parameter
        session_oe = session.itervalues().next()

        # allow to set a custom expiration for a session
        # such as a very short one for monitoring requests
        if session_oe._uid:
            expiration = getattr(session_oe, 'expiration', self.expiration)
        else:
            expiration = getattr(
                session_oe, 'expiration', self.anon_expiration
            )
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("saving session with key '%s' and "
                          "expiration of %s seconds",
                          key, expiration)

        if self.redis.set(key, dumps(dict(session), HIGHEST_PROTOCOL)):
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
            data = loads(saved)
        except ValueError:
            _logger.debug("session for key '%s' has been asked but its json "
                          "content could not be read, it has been reset", key)
            data = {}
        return self.session_class(data, sid, False)

    def list(self):
        keys = self.redis.keys('%s*' % self.prefix)
        _logger.debug("a listing redis keys has been called")
        return [key[len(self.prefix):] for key in keys]
