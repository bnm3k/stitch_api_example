import logging
import datetime as dt
import time
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any
import re
import base64
import secrets
import urllib.parse
from hashlib import sha256
import uuid

# external dependencies
import jwt
import requests


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


class UserTokenStoreInterface(ABC):
    @abstractmethod
    def get_token_details(self, user: Any) -> Optional[TokenDetails]:
        pass

    def set_token_details(self, user: Any, token_details: TokenDetails):
        pass


@dataclass
class BankAccount:
    name: str
    currency: str
    branch_code: int
    bank_id: str
    account_type: str
    account_number: str
    supports_payment_initiation: bool

    @staticmethod
    def _from_api_res(**r):
        return BankAccount(
            r["name"],
            r["currency"],
            int(r["branchCode"]),
            r["bankId"],
            r["accountType"],
            r["accountNumber"],
            r["supportsPaymentInitiation"],
        )


class Stitch:
    def __init__(
        self,
        client_id,
        client_secret,
        redirect_uri,
        token_store: UserTokenStoreInterface,
        logger=None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_store = token_store
        self._pending_authorization_requests = dict()

        if logger is None:
            logger = logging.getLogger(__name__)
            logger.addHandler(logging.NullHandler())
            logger.disabled = True

        self.logger = logger

    def should_authorize(self, user) -> bool:
        td = self.token_store.get_token_details(user)
        if td is None:
            return True
        return False

    def initiate_authorization(self, user) -> str:
        state = _gen_random_base64_str()
        nonce = _gen_random_base64_str()
        code_challenge, code_verifier = _gen_code_challenge_and_verifier()
        self._pending_authorization_requests[user] = {
            "code_verifier": code_verifier,
            "state": state,
        }
        scope = ["openid", "accounts", "offline_access"]
        params = {
            # unique ID of client generated
            "client_id": self.client_id,
            #
            # non-empty space sperated list of requested scopes
            # openid scope is required,
            # offline_access scope is necessary to use refresh token
            "scope": " ".join(scope),
            #
            # instructs stitch SSO to return an authorization code,
            # should always have a value of "code"
            "response_type": "code",
            #
            # after login, user is directed back to this URL, should always be
            # protected by SSL and HSTS
            "redirect_uri": self.redirect_uri,
            #
            # for mitigating replay attacks
            # value should be cryptographically secure, random string between 32
            # and 300 characters in length. It's later included in the id_token
            # found in the token endpoint response
            "nonce": nonce,
            #
            # for preventing CSRF. Like the Nonce, sould be cryptographically
            # secure. When the authorization request returns, the state is included
            # and should be validated against the stored value
            "state": state,
            #
            # A base64URL encoding of the sha256 hashed code verifier created below
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        encoded_params = "&".join(
            f"{k}={urllib.parse.quote(v)}" for k, v in params.items()
        )
        authz_code_endpoint = (
            f"https://secure.stitch.money/connect/authorize?{encoded_params}"
        )
        return authz_code_endpoint

    def complete_authorization(self, user, authorization_code, state=None, scope=None):
        # TODO, relying on Key lookup error to signify to library users that
        # they are trying to call this method without having first called
        # initiate_authorization. Consider throwing a specific exception
        # instead
        req = self._pending_authorization_requests[user]
        code_verifier = req["code_verifier"]

        params = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": self._encode_client_jwt(),
        }
        retrieve_user_token_endpoint = "https://secure.stitch.money/connect/token"
        req = requests.post(retrieve_user_token_endpoint, params)
        td = TokenDetails.from_json(req.content)
        self.token_store.set_token_details(user, td)

    def _encode_client_jwt(self) -> str:
        now = int(time.time())
        one_hour_from_now = now + 3600
        payload = {
            "aud": "https://secure.stitch.money/connect/token",
            "iss": self.client_id,
            "sub": self.client_id,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "nbf": now,
            "exp": one_hour_from_now,
        }
        encoded_jwt = jwt.encode(payload, self.client_secret, algorithm="RS256")
        return encoded_jwt

    def _get_token(self, user):
        td = self.token_store.get_token_details(user)
        if td is None:
            # TODO maybe throw exception
            return

        if td.is_expired():
            params = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": td.refresh_token,
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": self._encode_client_jwt(),
            }
            refresh_user_tokens_url = "https://secure.stitch.money/connect/token"
            req = requests.post(refresh_user_tokens_url, params)
            td = TokenDetails.from_json(req.content)
            self.token_store.set_token_details(user, td)

        return td

    def get_bank_accounts(self, user):
        td = self._get_token(user)
        if td is None:
            raise Exception("User not authorized or error retrieving token")

        stitch_url = "https://api.stitch.money/graphql"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {td.access_token}",
        }
        query = """query ListBankAccounts
        {
          user {
            bankAccounts {
              name
              currency
              branchCode
              bankId
              accountType
              accountNumber
              supportsPaymentInitiation
            }
          }
        }
        """
        graphql_query = json.dumps(
            {
                "query": query,
                "variables": None,
            }
        )
        req = requests.post(stitch_url, data=graphql_query, headers=headers)
        res = req.json()
        errors = res.get("errors")
        if req.status_code == 200 and errors is None:
            bank_accounts_raw = res["data"]["user"]["bankAccounts"]
            bank_accounts = []
            for entry in bank_accounts_raw:
                ba = BankAccount._from_api_res(**entry)
                bank_accounts.append(ba)
            return bank_accounts

        else:
            err_message = "Error retrieving user's stitch data"
            if req.status_code != 200:
                err_message = f"{err_message}. Status {req.status_code}"
            if errors is not None:
                err_message = f"{err_message}. {errors[0]['message']}"
            raise Exception(err_message)


def _encode_bytes_to_base64_str(bs) -> str:
    res = base64.b64encode(bs)
    res = re.sub(b"=", b"", res)
    res = re.sub(b"\\+", b"-", res)
    res = re.sub(b"\\/", b"_", res)
    as_str = res.decode("ascii")
    return as_str


def _gen_code_challenge_and_verifier() -> tuple[str, str]:
    """
    generates a random code

    the hashed value of this code (challenge) is sent with the authorization
    request

    the unhashed value (verifier) is sent with the user access token request
    """
    random_bytes = secrets.token_bytes(32)

    verifier = _encode_bytes_to_base64_str(random_bytes)

    challenge_bs = sha256(verifier.encode("utf-8")).digest()
    challenge = _encode_bytes_to_base64_str(challenge_bs)
    return challenge, verifier


def _gen_random_base64_str() -> str:
    return _encode_bytes_to_base64_str(secrets.token_bytes(32))
