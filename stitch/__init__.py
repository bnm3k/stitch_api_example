import logging
import datetime as dt
import time
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any


@dataclass(repr=False, frozen=True)
class TokenDetails:
    id_token: str
    access_token: str
    expires_at_seconds_from_epoch: float | int
    token_type: str
    refresh_token: str
    scope: str

    @staticmethod
    def from_json(s: str | bytes | bytearray):
        as_dict = json.loads(s)
        t = TokenDetails(
            id_token=as_dict["id_token"],
            access_token=as_dict["access_token"],
            expires_at_seconds_from_epoch=time.time() + as_dict["expires_in"],
            token_type=as_dict["token_type"],
            refresh_token=as_dict["refresh_token"],
            scope=as_dict["scope"],
        )
        return t

    def to_tuple(self) -> tuple:
        return (
            self.id_token,
            self.access_token,
            self.expires_at_seconds_from_epoch,
            self.token_type,
            self.refresh_token,
            self.scope,
        )

    def to_json(self) -> str:
        expires_in = int(self.expires_at_seconds_from_epoch - time.time())
        if expires_in < 0:  # already expired
            expires_in = 0
        return json.dumps(
            {
                "id_token": self.id_token,
                "access_token": self.access_token,
                "expires_in": expires_in,
                "token_type": self.token_type,
                "refresh_token": self.refresh_token,
                "scope": self.scope,
            }
        )

    def is_expired(self) -> bool:
        now = time.time()
        return self.expires_at_seconds_from_epoch > now

    def __str__(self) -> str:
        return "TokenDetails(id_token={}..., access_token={}..., expires_at={}, token_type={}, refresh_token={}..., scope={})".format(
            self.id_token[:5],
            self.access_token[:5],
            dt.datetime.fromtimestamp(self.expires_at_seconds_from_epoch),
            self.token_type,
            self.refresh_token[:5],
            self.scope,
        )


class UserTokenStore(ABC):
    @abstractmethod
    def get_token_details(self, user: Any) -> Optional[TokenDetails]:
        pass

    def set_token_details(self, user: Any, token_details: TokenDetails):
        pass


class Stitch:
    def __init__(
        self, client_id, client_secret, token_store: UserTokenStore, logger=None
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_store = token_store

        if logger is None:
            logger = logging.getLogger(__name__)
            logger.addHandler(logging.NullHandler())
            logger.disabled = True

        self.logger = logger

    def get_bank_accounts(self):
        return "To be Implemented"
