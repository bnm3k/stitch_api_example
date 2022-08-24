# Using Python for Stitch SSO

## Overview

This post goes through user Stitch SSO for python-based backends. It covers
pretty much the same ground as the
[Stitch docs](https://stitch.money/docs/stitch-sso/user-tokens) but uses Python
instead of browser-based Javascript. It should be of help for anyone trying to
integrate Stitch in their backend server. Before proceeding, make sure you have
both a `client_id` and `client_secret`- they are provided by Stitch

## Obtaining an Authorization Code

First, set the `client_id`, `client_secret` and redirect URL:

```python
client_id = "test-xyx"
client_secret = ""
redirect_uri = "http://localhost:3000/return"
```

We'll need the following helper function to encode bytes values to base64
strings as per Stitch's requirements:

```python
import base64
import re

def encode_bytes_to_base64_str(bs) -> str:
    res = base64.b64encode(bs)
    res = re.sub(b"=", b"", res)
    res = re.sub(b"\\+", b"-", res)
    res = re.sub(b"\\/", b"_", res)
    as_str = res.decode("ascii")
    return as_str
```

Generate the `code_challenge` and `code_verifier` values. The hashed value
(challenge) is sent with the authorization request. Once the user authorizes
successfully, the unhashed value (verifier) is then sent with the access token
request. These values are used by Stitch's server to correlate the authorization
and user access code requests so as to prevent certain vulnerabilities.

```python
import secrets
from hashlib import sha256

def gen_code_challenge_and_verifier() -> tuple[str, str]:
    random_bytes = secrets.token_bytes(32)

    verifier = encode_bytes_to_base64_str(random_bytes)
    challenge_bs = sha256(verifier.encode("utf-8")).digest()
    challenge = encode_bytes_to_base64_str(challenge_bs)

    return challenge, verifier

code_challenge, code_verifier = gen_code_challenge_and_verifier()
```

Generate the `state` and the `nonce` values. The `state` is required to prevent
cross-site request forgery while the `nonce` is required to prevent replay
attacks.

```python
import secrets

def gen_random_base64_str() -> str:
    return encode_bytes_to_base64_str(secrets.token_bytes(32))

state = gen_random_base64_str()
nonce = gen_random_base64_str()
```

Build up the URL that the user will be redirected to in order to sign in and
authorize your client:

```python
import urllib.parse

params = {
  "client_id": client_id,
  "scope": "openid accounts offline_access",
  "response_type": "code",
  "redirect_uri": redirect_uri,
  "nonce": nonce,
  "state": state,
  "code_challenge": code_challenge,
  "code_challenge_method": "S256",
}


encoded_params = urllib.parse.urlencode(params)
authorization_endpoint = (
  f"https://secure.stitch.money/connect/authorize?{encoded_params}"
)
```

Next redirect the user to this URL. Flask provides functions for doing so but
for now, we'll do this "manually":

```python
import webbrowser

webbrowser.open(authorization_endpoint)
```

Check the Stitch docs for the test-user authentication details in order to
sign-in and authorize your client as the "end-user".

Stitch will redirect back to your client once the user has completed
authorization. If you've set up the requisite handlers for the `/return`
endpoint you are good to go; otherwise, you will have to find some other way of
getting Stitch's response into your application. For example:

```python
authorization_res_urlstring = input("redirect_uri: ")
authorization_res = {
  k: v[0]
  for k, v in urllib.parse.parse_qs(
    urllib.parse.urlparse(authorization_res_urlstring).query
  ).items()
}
code = authorization_res["code"]
state = authorization_res["state"]
```

If you are using a web framework like Flask, it should automatically parse the
query arguments for you. You need the `code` to proceed. You should also check
the `state` value returned in the query parameters with the state value you
generated to prevent CSRF.\
If the user does not sign in, you will only receive the `state` value back.

Generate the `client_assertion`. Note that
[PyJWT](https://pyjwt.readthedocs.io/en/stable/) is used, instead of
[python-jwt](https://github.com/GehirnInc/python-jwt).

```python
import time
import uuid
import jwt

def encode_jwt(client_id, client_secret) -> str:
    now = int(time.time())
    one_hour_from_now = now + 3600
    payload = {
        "aud": "https://secure.stitch.money/connect/token",
        "iss": client_id,
        "sub": client_id,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "nbf": now,
        "exp": one_hour_from_now,
    }
    encoded_jwt = jwt.encode(payload, client_secret, algorithm="RS256")
    return encoded_jwt
```

Finally, get the access token from Stitch:

```python
import requests

params = {
  "grant_type": "authorization_code",
  "client_id": client_id,
  "code": code,
  "redirect_uri": redirect_uri,
  "code_verifier": code_verifier,
  "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
  "client_assertion": encode_jwt(client_id, client_secret),
}

retrieve_user_token_endpoint = "https://secure.stitch.money/connect/token"
req = requests.post(retrieve_user_token_endpoint, params)
res = req.json()
access_token = res["access_token"]
refresh_token = res["refresh_token"]
```

If you intend to store the user's access and refresh tokens on disk, it is
recommended that you encrypt them. If the tokens are leaked, contact Stitch
immediately.

## Querying the Stitch API

Now that you have the `access_token`, you can query Stitch's GraphQL API:

```python
stitch_url = "https://api.stitch.money/graphql"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {access_token}",
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
print(res)
```

## Refreshing User Tokens

Refreshing user tokens is a bit simpler:

```python
params = {
    "grant_type": "refresh_token",
    "client_id": client_id,
    "refresh_token": refresh_token,
    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
    "client_assertion": encode_jwt(client_id, client_secret),
}

refresh_user_tokens_url = "https://secure.stitch.money/connect/token"
req = requests.post(refresh_user_tokens_url, params)

res = req.json()
access_token = res["access_token"]
refresh_token = res["refresh_token"]
```
