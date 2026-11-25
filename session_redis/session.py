# Copyright 2016-2024 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json
import logging

from odoo.service import security
from odoo.tools import split_every
from odoo.tools._vendor.sessions import SessionStore

from . import json_encoding

try:
    from redis.exceptions import RedisError
except ImportError:
    # without redis, the store is never instantiated (see http.py)
    RedisError = Exception

# this is equal to the duration of the session garbage collector in
# odoo.http.session_gc()
DEFAULT_SESSION_TIMEOUT = 60 * 60 * 24 * 7  # 7 days in seconds
DEFAULT_SESSION_TIMEOUT_ANONYMOUS = 60 * 60 * 3  # 3 hours in seconds
# number of EXISTS commands sent per round trip by
# get_missing_session_identifiers()
EXISTS_BATCH_SIZE = 1000

_logger = logging.getLogger(__name__)


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

    def list(self):
        keys = self.redis.keys("%s*" % self.prefix)
        _logger.debug("a listing redis keys has been called")
        return [key[len(self.prefix) :] for key in keys]

    def rotate(self, session, env):
        self.delete(session)
        session.sid = self.generate_key()
        if session.uid and env:
            session.session_token = security.compute_session_token(session, env)
        session.should_rotate = False
        self.save(session)

    def vacuum(self, *args, **kwargs):
        """Do not garbage collect the sessions

        Redis keys are automatically cleaned at the end of their
        expiration.
        """
        return None

    # The two methods below are called by res.device / res.device.log, which
    # identify a session by ``sid[:42]``. The sids of this store are 40
    # characters long, so an identifier is a whole sid and maps to exactly one
    # key: lookups use the key itself, never a pattern.

    def get_missing_session_identifiers(self, identifiers):
        """Return the identifiers whose session no longer exists

        Used by the autovacuum of ``res.device.log`` to flag revoked devices,
        with up to 100 000 identifiers per call, hence the pipelined EXISTS.
        """
        identifiers = set(identifiers)
        found = set()
        try:
            for batch in split_every(
                EXISTS_BATCH_SIZE, filter(self.is_valid_key, identifiers), list
            ):
                pipeline = self.redis.pipeline(transaction=False)
                for identifier in batch:
                    pipeline.exists(self.build_key(identifier))
                results = pipeline.execute()
                found.update(
                    identifier
                    for identifier, exists in zip(batch, results, strict=True)
                    if exists
                )
        except RedisError as error:
            # flagging every device as revoked would be wrong, flag none
            _logger.warning(
                "could not check the sessions in Redis, no device is flagged "
                "as revoked: %s",
                error,
            )
            return set()
        return identifiers - found

    def delete_from_identifiers(self, identifiers):
        """Delete the sessions of the given identifiers

        Used when revoking devices. Errors are raised on purpose: the caller
        flags the devices as revoked afterwards.
        """
        keys = [
            self.build_key(identifier)
            for identifier in set(identifiers)
            if self.is_valid_key(identifier)
        ]
        if keys:
            self.redis.delete(*keys)
