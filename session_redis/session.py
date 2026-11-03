# Copyright 2016-2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import builtins
import json
import logging
from typing import TypeAlias

import odoo.http
from odoo.http import SESSION_LIFETIME
from odoo.tools._vendor.sessions import SessionStore

from . import json_encoding

# this was equal to the duration of the session garbage collector in
# odoo.http.session_gc()
DEFAULT_SESSION_TIMEOUT_ANONYMOUS = 60 * 60 * 3  # 3 hours in seconds

_logger = logging.getLogger(__name__)


# Many parts of the session store API operate not on full session keys, but only
# the first n characters of them (see odoo.http.STORED_SESSION_BYTES). In
# particular used by Devices, but Odoo in general seems to promise that this
# partial sid will be safe to store in the database, and can be used to later
# find sessions, even if those sessions are actually longer.
PartialSid: TypeAlias = str


class RedisSessionStore(SessionStore):
    """SessionStore that saves session to redis"""

    def __init__(
        self,
        redis,
        session_class=None,
        prefix="",
        expiration=None,
        anon_expiration=None,
        absolute_expiration=False,
    ):
        super().__init__(session_class=session_class)
        self.redis = redis
        if expiration is None:
            self.expiration = SESSION_LIFETIME
        else:
            self.expiration = expiration
        if anon_expiration is None:
            self.anon_expiration = DEFAULT_SESSION_TIMEOUT_ANONYMOUS
        else:
            self.anon_expiration = anon_expiration
        # authenticated sessions expire after `expiration` since their login
        self.absolute_expiration = absolute_expiration
        self.prefix = "session:"
        if prefix:
            self.prefix = f"{self.prefix}:{prefix}:"

    # Use the key generation method of the FileSystemSessionStore: it seems that
    # the one on the general SessionStore does not generate long enough keys to
    # support the device session rotation logic (SessionStore produces 40
    # character long keys, while the new rotation logic appears to assume a
    # length of at least 84).
    generate_key = odoo.http.FilesystemSessionStore.generate_key
    is_valid_key = odoo.http.FilesystemSessionStore.is_valid_key

    def build_key(self, sid):
        return f"{self.prefix}{sid}"

    def save(self, session):
        key = self.build_key(session.sid)

        # If the session has a deletion_time, it is slated for rotation, and
        # should be removed once the rotation window is over. See
        # odoo.http.SESSION_DELETION_TIMER.
        # Otherwise, allow to set a custom expiration for a session
        # such as a very short one for monitoring requests
        if session.uid:
            expiration = (
                session.get("deletion_time")
                or session.get("expiration")
                or self.expiration
            )
        else:
            expiration = (
                session.get("deletion_time")
                or session.get("expiration")
                or self.anon_expiration
            )
        if _logger.isEnabledFor(logging.DEBUG):
            if session.uid:
                user_msg = f"user '{session.login}' (id: {session.uid})"
            else:
                user_msg = "anonymous user"
            _logger.debug(
                f"saving session with key '{key}' and "
                f"expiration of {expiration} seconds for {user_msg}"
            )

        data = json.dumps(dict(session), cls=json_encoding.SessionEncoder).encode(
            "utf-8"
        )
        if not (expiration and isinstance(expiration, int)):
            expiration = DEFAULT_SESSION_TIMEOUT_ANONYMOUS
            expiration = DEFAULT_SESSION_TIMEOUT_ANONYMOUS
        if (
            self.absolute_expiration
            and session.uid
            and not session.is_new
            and not session.get("deletion_time")
        ):
            # absolute mode: keep the TTL set at login (keepttl) and never
            # recreate an expired session (xx); anonymous and new sessions
            # get a full TTL below, and the old key of a soft rotation its
            # deletion delay
            if not self.redis.set(key, data, xx=True, keepttl=True):
                return False
            # keepttl keeps "no TTL": give one to a key left without
            if self.redis.ttl(key) == -1:
                self.redis.expire(key, expiration)
            return True
        # write the data and the TTL in one command: with SET then EXPIRE, a
        # failed EXPIRE left a key without TTL, never expiring
        return self.redis.set(key, data, ex=expiration)

    def delete(self, session):
        key = self.build_key(session.sid)
        _logger.debug(f"deleting session with key {key}")
        return self.redis.delete(key)

    def get(self, sid):
        if not self.is_valid_key(sid):
            _logger.debug(
                f"session with invalid sid '{sid}' has been asked, returning a new one"
            )
            return self.new()

        key = self.build_key(sid)
        saved = self.redis.get(key)
        if not saved:
            _logger.debug(
                f"session with non-existent key '{key}' has been asked, "
                "returning a new one"
            )
            return self.new()
        try:
            data = json.loads(saved.decode("utf-8"), cls=json_encoding.SessionDecoder)
        except ValueError:
            _logger.debug(
                f"session for key '{key}' has been asked but its json "
                "content could not be read, it has been reset"
            )
            data = {}
        return self.session_class(data, sid, False)

    def list(self):
        keys = self.redis.keys(f"{self.prefix}*")
        _logger.debug("a listing redis keys has been called")
        return [key[len(self.prefix) :] for key in keys]

    def rotate(self, session, env, soft=False):
        """Rotate the session id, see odoo.http.FilesystemSessionStore.rotate

        Its logic does not do anything file-system specific, so it is reused,
        but the new session id is a new Redis key:

        * it is saved as a new session (full TTL): on login, logout or MFA
          (hard rotation), the expiration restarts, in absolute mode too
        * in absolute mode, a soft rotation (every
          odoo.http.SESSION_ROTATION_INTERVAL) keeps the remaining TTL of the
          old key, so the expiration still counts from the login
        """
        ttl = None
        if soft and self.absolute_expiration and session.uid:
            # read it before the old key gets the TTL of its deletion_time
            ttl = self.redis.ttl(self.build_key(session.sid))
        create_time = session.get("create_time")
        session.is_new = True
        try:
            odoo.http.FilesystemSessionStore.rotate(self, session, env, soft=soft)
        finally:
            session.is_new = False
        # a soft rotation already done by a concurrent request only switches
        # to its new session id, without saving: its TTL is already right
        rotated = session.get("create_time") != create_time
        if ttl is None or not rotated:
            return
        key = self.build_key(session.sid)
        if ttl > 0:
            self.redis.expire(key, ttl)
        elif ttl == -2:
            # the old session expired meanwhile: do not revive it
            self.redis.delete(key)
        # ttl == -1 (old key without TTL): keep the full TTL of the new key

    def vacuum(self, *args, **kwargs):
        """Do not garbage collect the sessions

        Redis keys are automatically cleaned at the end of their
        expiration.
        """
        return None

    def delete_old_sessions(self, session):
        """
        # Deletion of rotated sessions is handled by updating the sessions'
        # expiry based on deletion_time in save(), so this method is redundant
        # when using a redis store.

        # While this method is not part of the generic SessionStore API, it is
        # defined on the file session store, and is used by the Session itself
        # as part of the session rotation (see odoo.http.Session._delete_old_sessions).
        """
        return

    def get_missing_session_identifiers(
        self, identifiers: builtins.list[PartialSid]
    ) -> set[PartialSid]:
        """
        Given a list of partial session ids, return a set of those session ids
        which no longer exist in the keystore.

        While this method is not part of the generic SessionStore API, it is
        defined on the file session store, and is used by Odoo's devices to
        figure out what needs to be revoked
        (see odoo.addons.base.models.res_device.ResDeviceLog.__update_revoked).
        """
        identifiers = set(identifiers)
        not_found = set()
        for partial_sid in identifiers:
            key = f"session::{self.prefix}:{partial_sid}*"
            match = self.redis.keys(pattern=key)
            if not match:
                not_found.add(partial_sid)
        return not_found

    def delete_from_identifiers(self, identifiers: builtins.list[PartialSid]):
        """
        Given a list of partial session ids, remove any that are in the session store.

        While this method is not part of the generic SessionStore API, it is
        defined on the file session store, and is used by devices when revoking
        device sessions (see odoo.addons.base.models.res_device.ResDevice._revoke).
        """
        patterns_to_unlink = []
        for identifier in identifiers:
            # Avoid removing a session if it does not match an identifier. See this same
            # comment in odoo.http.FileSessionStore.delete_from_identifiers.
            if not odoo.http._session_identifier_re.match(identifier):
                raise ValueError(
                    "Identifier format incorrect, did you pass in a string instead ",
                    "of a list?",
                )
            patterns_to_unlink.append(f"{self.prefix}{identifier}*")
        keys_to_unlink = []
        for pattern in patterns_to_unlink:
            keys_to_unlink.extend(self.redis.scan_iter(match=pattern))
        if keys_to_unlink:
            self.redis.delete(*keys_to_unlink)
