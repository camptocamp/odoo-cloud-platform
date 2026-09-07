# Copyright 2016-2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import builtins
import json
import logging
from typing import TypeAlias

import odoo.http
from odoo.tools._vendor.sessions import SessionStore, _sha1_re

from . import json_encoding

# this is equal to the duration of the session garbage collector in
# odoo.http.session_gc()
DEFAULT_SESSION_TIMEOUT = 60 * 60 * 24 * 7  # 7 days in seconds
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
    ):
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
        self.prefix = "session:"
        if prefix:
            self.prefix = f"{self.prefix}:{prefix}:"

    def build_key(self, sid):
        return f"{self.prefix}{sid}"

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
        if self.redis.set(key, data):
            return self.redis.expire(key, expiration)

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

    # The FilesystemSessionStore's rotate does not do anything file-system
    # specific so it can just be reused here
    rotate = odoo.http.FilesystemSessionStore.rotate

    def vacuum(self, *args, **kwargs):
        """Do not garbage collect the sessions

        Redis keys are automatically cleaned at the end of their
        expiration.
        """
        return None

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
            key = f"{self.prefix}{partial_sid}*"
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
            # Avoid removing a session if it does not match an identifier.
            # See this same comment in
            # odoo.http.FileSessionStore.delete_from_identifiers.
            if not _sha1_re.match(identifier):
                # skip as done in odoo.http.FileSessionStore
                continue
            patterns_to_unlink.append(f"{self.prefix}{identifier}*")
        keys_to_unlink = []
        for pattern in patterns_to_unlink:
            keys_to_unlink.extend(self.redis.scan_iter(match=pattern))
        if keys_to_unlink:
            self.redis.delete(*keys_to_unlink)
