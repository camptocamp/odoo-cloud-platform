# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from datetime import timedelta

from redis.exceptions import ConnectionError as RedisConnectionError

import odoo.http
from odoo import fields
from odoo.http import Session
from odoo.tests import BaseCase, TransactionCase

from odoo.addons.session_redis.session import RedisSessionStore

# res.device.log identifier of a session from odoo.http.FilesystemSessionStore,
# e.g. written before switching to this store
FILESYSTEM_IDENTIFIER = "Ab-_" * 10 + "Zz"


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.round_trips = 0
        self.down = False

    def _round_trip(self):
        if self.down:
            raise RedisConnectionError("Connection refused")
        self.round_trips += 1

    def set(self, key, value):
        self._round_trip()
        self.data[key] = value
        return True

    def expire(self, key, seconds):
        self._round_trip()
        return key in self.data

    def get(self, key):
        self._round_trip()
        return self.data.get(key)

    def delete(self, *keys):
        self._round_trip()
        return sum(self.data.pop(key, None) is not None for key in keys)

    def pipeline(self, transaction=True):
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.keys = []

    def exists(self, key):
        self.keys.append(key)

    def execute(self):
        self.redis._round_trip()
        return [int(key in self.redis.data) for key in self.keys]


class TestRedisSessionStore(BaseCase):
    def setUp(self):
        super().setUp()
        self.redis = FakeRedis()
        self.store = RedisSessionStore(
            redis=self.redis, prefix="test", session_class=Session
        )

    def _saved_session(self, store=None):
        store = store or self.store
        session = store.new()
        session.uid = 2
        store.save(session)
        return session

    def test_identifier_is_the_whole_sid(self):
        session = self._saved_session()
        self.assertLessEqual(
            len(session.sid),
            42,
            "longer sids need prefix matching in the identifier methods",
        )
        self.assertIn(self.store.build_key(session.sid[:42]), self.redis.data)

    def test_get_missing_session_identifiers(self):
        alive = self._saved_session()
        gone = self.store.generate_key()
        missing = self.store.get_missing_session_identifiers(
            [alive.sid[:42], gone[:42], FILESYSTEM_IDENTIFIER]
        )
        self.assertEqual(missing, {gone, FILESYSTEM_IDENTIFIER})

    def test_get_missing_session_identifiers_is_pipelined(self):
        alive = [self._saved_session().sid for _ in range(5)]
        gone = [self.store.generate_key() for _ in range(2495)]
        self.redis.round_trips = 0
        missing = self.store.get_missing_session_identifiers(alive + gone)
        self.assertEqual(missing, set(gone))
        self.assertEqual(self.redis.round_trips, 3)

    def test_get_missing_session_identifiers_when_redis_is_down(self):
        self._saved_session()
        self.redis.down = True
        with self.assertLogs("odoo.addons.session_redis.session", "WARNING"):
            missing = self.store.get_missing_session_identifiers(
                [self.store.generate_key()]
            )
        self.assertEqual(missing, set())

    def test_delete_from_identifiers_matches_whole_sids_only(self):
        victim = self._saved_session()
        bystander = self._saved_session()
        other_store = RedisSessionStore(
            redis=self.redis, prefix="other", session_class=Session
        )
        other = other_store.new()
        other.sid = victim.sid
        other_store.save(other)

        self.store.delete_from_identifiers(
            [victim.sid[:42], bystander.sid[:39], "*", FILESYSTEM_IDENTIFIER]
        )

        self.assertEqual(
            set(self.redis.data),
            {
                self.store.build_key(bystander.sid),
                other_store.build_key(victim.sid),
            },
        )

    def test_rotate_clears_should_rotate(self):
        session = self._saved_session()
        old_sid = session.sid
        session.should_rotate = True
        self.store.rotate(session, None)
        self.assertFalse(session.should_rotate)
        self.assertNotIn(self.store.build_key(old_sid), self.redis.data)
        self.assertIn(self.store.build_key(session.sid), self.redis.data)


class TestDeviceRevocation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.redis = FakeRedis()
        self.store = RedisSessionStore(redis=self.redis, session_class=Session)
        self.patch(odoo.http.root, "session_store", self.store)

    def _logs(self, identifiers, last_activity):
        return self.env["res.device.log"].create(
            [
                {
                    "session_identifier": identifier,
                    "user_id": self.env.uid,
                    "platform": "linux",
                    "browser": "firefox",
                    "ip_address": "127.0.0.1",
                    "first_activity": last_activity,
                    "last_activity": last_activity,
                    "revoked": False,
                }
                for identifier in identifiers
            ]
        )

    def _saved_session(self):
        session = self.store.new()
        session.uid = self.env.uid
        self.store.save(session)
        return session

    def test_autovacuum_revokes_logs_of_gone_sessions(self):
        alive = self._saved_session()
        logs = self._logs(
            [alive.sid[:42], self.store.generate_key()[:42], FILESYSTEM_IDENTIFIER],
            fields.Datetime.now() - timedelta(days=30),
        )
        # the autovacuum commits after each batch
        self.patch(self.env.cr, "commit", lambda: None)
        self.env["res.device.log"]._ResDeviceLog__update_revoked()
        self.assertEqual(logs.mapped("revoked"), [False, True, True])

    def test_revoke_device_deletes_its_session_only(self):
        victim = self._saved_session()
        bystander = self._saved_session()
        logs = self._logs([victim.sid[:42], bystander.sid[:42]], fields.Datetime.now())
        self.env.flush_all()
        device = self.env["res.device"].search(
            [("session_identifier", "=", victim.sid[:42])]
        )
        device._revoke()
        self.assertEqual(set(self.redis.data), {self.store.build_key(bystander.sid)})
        self.assertEqual(logs.mapped("revoked"), [True, False])
