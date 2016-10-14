# -*- coding: utf-8 -*-
# Copyright 2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json

from werkzeug.contrib.sessions import SessionStore

# this is equal to the duration of the session garbage collector in
# openerp.http.session_gc()
DEFAULT_SESSION_TIMEOUT = 60 * 60 * 24 * 7  # 7 days in seconds


class RedisSessionStore(SessionStore):
    """ SessionStore that saves session to redis """

    def __init__(self, redis, session_class=None,
                 prefix='', expiration=None):
        super(RedisSessionStore, self).__init__(session_class=session_class)
        self.redis = redis
        if expiration is None:
            self.expiration = DEFAULT_SESSION_TIMEOUT
        else:
            self.expiration = expiration
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
        if self.redis.set(key, json.dumps(dict(session))):
            return self.redis.expire(key, self.expiration)

    def delete(self, session):
        key = self.build_key(session.sid)
        return self.redis.delete(key)

    def get(self, sid):
        if not self.is_valid_key(sid):
            return self.new()

        key = self.build_key(sid)
        saved = self.redis.get(key)
        if not saved:
            return self.new()
        try:
            data = json.loads(saved)
        except ValueError:
            data = {}
        return self.session_class(data, sid, False)

    def list(self):
        keys = self.redis.keys('%s*' % self.prefix)
        return [key[len(self.prefix):] for key in keys]
