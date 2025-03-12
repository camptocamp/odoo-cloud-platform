# Copyright 2016-2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json
import logging
from typing import Optional

from odoo.service import security
from odoo.tools._vendor.sessions import SessionStore

from . import json_encoding

# this is equal to the duration of the session garbage collector in
# odoo.http.session_gc()
DEFAULT_SESSION_TIMEOUT = 60 * 60 * 24 * 7  # 7 days in seconds
DEFAULT_SESSION_TIMEOUT_ANONYMOUS = 60 * 60 * 3  # 3 hours in seconds

_logger = logging.getLogger(__name__)


class RedisSessionStore(SessionStore):
    """SessionStore that saves session to redis"""

    def __init__(
        self,
        redis,
        session_class=None,
        prefix: str = "",
        expiration: Optional[int] = None,
        anon_expiration: Optional[int] = None,
    ) -> None:
        super().__init__(session_class=session_class)
        self.redis = redis
        self.expiration = (
            expiration if expiration is not None else DEFAULT_SESSION_TIMEOUT
        )
        self.anon_expiration = (
            anon_expiration
            if anon_expiration is not None
            else DEFAULT_SESSION_TIMEOUT_ANONYMOUS
        )
        self.prefix = f"session:{prefix}:" if prefix else "session:"

    def build_key(self, sid: str) -> str:
        """Build the Redis key for a session ID."""
        return f"{self.prefix}{sid}"

    def save(self, session) -> Optional[bool]:
        """Save session data in Redis with an expiration time."""
        key = self.build_key(session.sid)

        # allow to set a custom expiration for a session
        # such as a very short one for monitoring requests
        expiration = session.expiration or (
            self.expiration if session.uid else self.anon_expiration
        )

        if _logger.isEnabledFor(logging.DEBUG):
            user_msg = (
                f"user '{session.login}' (id: {session.uid})"
                if session.uid
                else "anonymous user"
            )
            _logger.debug(
                f"saving session with key '{key}' and "
                f"expiration of {expiration} seconds for {user_msg}"
            )

        data = json.dumps(dict(session), cls=json_encoding.SessionEncoder).encode(
            "utf-8"
        )
        if self.redis.set(key, data):
            return self.redis.expire(key, expiration)
        return None

    def delete(self, session) -> int:
        """Delete a session from Redis."""
        key = self.build_key(session.sid)
        _logger.debug(f"deleting session with key {key}")
        return self.redis.delete(key)

    def get(self, sid: str):
        """Retrieve a session from Redis, or return a new one if not found."""
        if not self.is_valid_key(sid):
            _logger.debug(
                f"session with invalid sid '{sid}' has been asked, "
                "returning a new one"
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

    def list(self) -> list[str]:
        """List all session keys in Redis."""
        # More efficient scanning
        keys = [key for key in self.redis.scan_iter(f"{self.prefix}*")]
        _logger.debug("a listing redis keys has been called")
        return [key.decode("utf-8")[len(self.prefix) :] for key in keys]

    def rotate(self, session, env) -> None:
        """Rotate session ID and regenerate session token if user is logged in."""
        self.delete(session)
        session.sid = self.generate_key()
        if session.uid and env:
            session.session_token = security.compute_session_token(session, env)
        self.save(session)

    def vacuum(self, *args, **kwargs):
        """Do not garbage collect the sessions

        Redis keys are automatically cleaned at the end of their
        expiration.
        """
        return None
