# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from unittest import mock

from odoo import http
from odoo.tests import BaseCase

from ..session import RedisSessionStore

DAY = 60 * 60 * 24
HOUR = 60 * 60


class FakeRedis:
    """In-memory Redis with a manual clock, for the commands used by the store"""

    def __init__(self):
        # a realistic epoch: odoo.http stores time.time() in the sessions
        self.now = 1_800_000_000.0
        self.data = {}
        self.expire_at = {}

    def advance(self, seconds):
        self.now += seconds

    def _purge(self, key):
        expire_at = self.expire_at.get(key)
        if expire_at is not None and expire_at <= self.now:
            self.data.pop(key, None)
            self.expire_at.pop(key, None)

    def set(self, key, value, ex=None, xx=False, keepttl=False):
        self._purge(key)
        if xx and key not in self.data:
            return None
        self.data[key] = value
        if ex is not None:
            self.expire_at[key] = self.now + int(ex)
        elif not keepttl:
            self.expire_at.pop(key, None)
        return True

    def get(self, key):
        self._purge(key)
        return self.data.get(key)

    def delete(self, key):
        self.expire_at.pop(key, None)
        return int(self.data.pop(key, None) is not None)

    def expire(self, key, seconds):
        self._purge(key)
        if key not in self.data:
            return False
        self.expire_at[key] = self.now + int(seconds)
        return True

    def ttl(self, key):
        self._purge(key)
        if key not in self.data:
            return -2
        if key not in self.expire_at:
            return -1
        return int(self.expire_at[key] - self.now)

    def time(self):
        return self.now


class TestRedisSessionStore(BaseCase):
    env = object()  # rotate() asserts an env for authenticated sessions

    def _get_store(self, **kwargs):
        self.redis = FakeRedis()
        # odoo.http.FilesystemSessionStore.rotate, reused by the store, uses
        # the clock and needs an env to compute the session token
        for target, new in (
            ("odoo.http.time", mock.Mock(time=self.redis.time)),
            (f"{RedisSessionStore.__module__}.time", mock.Mock(time=self.redis.time)),
            ("odoo.http.security.compute_session_token", mock.Mock(return_value="t")),
        ):
            patcher = mock.patch(target, new)
            patcher.start()
            self.addCleanup(patcher.stop)
        return RedisSessionStore(
            redis=self.redis,
            session_class=http.Session,
            expiration=7 * DAY,
            anon_expiration=3 * HOUR,
            **kwargs,
        )

    def _login(self, store):
        session = store.new()
        session.update({"uid": 1, "login": "admin"})
        store.save(session)
        return session

    def _ttl(self, store, session):
        return self.redis.ttl(store.build_key(session.sid))

    def _use(self, store, session):
        """Simulate a request of the user, which touches the session"""
        session = store.get(session.sid)
        session["context"] = {"lang": "en_US"}
        store.save(session)
        return session

    def test_sliding_expiration(self):
        """By default, each save renews the expiration of the session"""
        store = self._get_store()
        session = self._login(store)
        self.assertEqual(self._ttl(store, session), 7 * DAY)
        for __ in range(10):
            self.redis.advance(DAY)
            session = self._use(store, session)
            self.assertEqual(self._ttl(store, session), 7 * DAY)
        # still logged in after 10 days of daily use
        self.assertEqual(store.get(session.sid).uid, 1)

    def test_absolute_expiration(self):
        """The session expires 7 days after the login, whatever the use"""
        store = self._get_store(absolute_expiration=True)
        session = self._login(store)
        sid = session.sid
        for day in range(1, 7):
            self.redis.advance(DAY)
            session = self._use(store, session)
            self.assertEqual(session.uid, 1)
            self.assertEqual(self._ttl(store, session), (7 - day) * DAY)
        self.assertEqual(store.get(sid)["context"], {"lang": "en_US"})
        self.redis.advance(DAY)
        self.assertFalse(store.get(sid).uid)

    def test_absolute_expiration_not_recreated(self):
        """A request ending after the expiration does not revive the session"""
        store = self._get_store(absolute_expiration=True)
        session = self._login(store)
        session = store.get(session.sid)
        self.redis.advance(7 * DAY)
        session["context"] = {"lang": "en_US"}
        store.save(session)
        self.assertEqual(self._ttl(store, session), -2)

    def test_absolute_expiration_rotation(self):
        """A rotated session (login, logout, MFA) gets a full expiration"""
        store = self._get_store(absolute_expiration=True)
        session = self._login(store)
        old_sid = session.sid
        self.redis.advance(3 * DAY)
        store.rotate(session, self.env)
        self.assertNotEqual(session.sid, old_sid)
        self.assertIsNone(self.redis.get(store.build_key(old_sid)))
        self.assertEqual(self._ttl(store, session), 7 * DAY)

    def test_absolute_expiration_anonymous(self):
        """Anonymous sessions keep a sliding expiration"""
        store = self._get_store(absolute_expiration=True)
        session = store.new()
        session["debug"] = ""
        store.save(session)
        self.assertEqual(self._ttl(store, session), 3 * HOUR)
        self.redis.advance(2 * HOUR)
        session = self._use(store, session)
        self.assertEqual(self._ttl(store, session), 3 * HOUR)

    def test_absolute_expiration_key_without_ttl(self):
        """A key without TTL (left by the former SET then EXPIRE) gets one"""
        store = self._get_store(absolute_expiration=True)
        session = self._login(store)
        self.redis.expire_at.pop(store.build_key(session.sid))
        self.assertEqual(self._ttl(store, session), -1)
        session = self._use(store, session)
        self.assertEqual(self._ttl(store, session), 7 * DAY)

    def _login_from_anonymous(self, store):
        """Simulate odoo.http: the login rotates the anonymous session"""
        session = store.new()
        session["debug"] = ""
        store.save(session)
        session = store.get(session.sid)
        session.update({"uid": 1, "login": "admin"})
        store.rotate(session, self.env)
        return session

    def test_login_rotation(self):
        """The login saves the new key, then the TTL counts from it"""
        store = self._get_store(absolute_expiration=True)
        self.redis.advance(HOUR)
        session = self._login_from_anonymous(store)
        self.assertEqual(self._ttl(store, session), 7 * DAY)
        self.redis.advance(DAY)
        session = self._use(store, session)
        self.assertEqual(self._ttl(store, session), 6 * DAY)

    def test_absolute_expiration_soft_rotation(self):
        """A soft rotation keeps the expiration since the login"""
        store = self._get_store(absolute_expiration=True)
        session = self._login_from_anonymous(store)
        old_sid = session.sid
        self.redis.advance(4 * HOUR)
        session = store.get(session.sid)
        store.rotate(session, self.env, soft=True)
        self.assertNotEqual(session.sid, old_sid)
        self.assertEqual(self._ttl(store, session), 7 * DAY - 4 * HOUR)
        self.assertEqual(store.get(old_sid)["next_sid"], session.sid)
        # the old key is kept for the deletion delay only
        self.assertEqual(self.redis.ttl(store.build_key(old_sid)), 120)
        # later requests keep counting from the login
        self.redis.advance(DAY)
        session = self._use(store, session)
        self.assertEqual(self._ttl(store, session), 6 * DAY - 4 * HOUR)

    def test_absolute_expiration_concurrent_soft_rotation(self):
        """A request following a concurrent soft rotation keeps its TTL"""
        store = self._get_store(absolute_expiration=True)
        session = self._login_from_anonymous(store)
        old_sid = session.sid
        self.redis.advance(4 * HOUR)
        first = store.get(old_sid)
        second = store.get(old_sid)
        store.rotate(first, self.env, soft=True)
        store.rotate(second, self.env, soft=True)
        self.assertEqual(second.sid, first.sid)
        self.assertEqual(self._ttl(store, second), 7 * DAY - 4 * HOUR)

    def test_sliding_expiration_soft_rotation(self):
        """By default, a soft rotation gives a full expiration"""
        store = self._get_store()
        session = self._login_from_anonymous(store)
        self.redis.advance(4 * HOUR)
        session = store.get(session.sid)
        store.rotate(session, self.env, soft=True)
        self.assertEqual(self._ttl(store, session), 7 * DAY)

    def test_soft_rotation_old_key_deletion(self):
        """The old key of a soft rotation expires after its deletion delay"""
        store = self._get_store()
        session = self._login_from_anonymous(store)
        old_sid = session.sid
        self.redis.advance(4 * HOUR)
        session = store.get(session.sid)
        store.rotate(session, self.env, soft=True)
        self.assertEqual(
            self.redis.ttl(store.build_key(old_sid)), http.SESSION_DELETION_TIMER
        )
        self.redis.advance(http.SESSION_DELETION_TIMER)
        self.assertIsNone(self.redis.get(store.build_key(old_sid)))
        self.assertEqual(store.get(session.sid).uid, 1)
