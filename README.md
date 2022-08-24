# STITCH SDK

## Overview

The Stitch SDK provides access to the Stitch API.

## Design Principles

The following are the key design principles for this library:

- Use as few third party dependencies as possible, for example, even though we
  could use the `gql` library to make graphql queries, we instead opt for doing
  it manually. The only third-party dependencies are
  [requests](https://requests.readthedocs.io/en/latest/) and
  [PyJWT](https://pyjwt.readthedocs.io/en/stable/)
- keep as little state as possible within the library. For example, it is up to
  the caller to implement and provide a `User Token Store` in which the tokens
  are stored, and a `User Auth Requests Store`. This allows the caller to use
  their preferred solution, be it in-memory, redis or some other solution.
  In-memory defaults that use dicts are provided so that one can tinker around
  with the SDK. However, for production, it is recommended that the caller
  implements and provides their desired store (I personally prefer sqlite)
- If an action requires end-user interaction, it should be up to the caller to
  initiate that action. For example, redirects to stitch for authorization
- If an action does not require end-user interaction, handle it within the
  library, for example, refreshing tokens.

## Usage

To initialize the library:

```
pip install dist/stitch-0.1.0-py3-none-any.whl
```

Initialize the sdk:

```python
stitch = Stitch(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri="http://localhost:3000/return",
)
```

To retrieve a user's bank info, first check if they should authorize your
client, then redirect them to Stitch to do so:

```python
if stitch.should_authorize(user_id):
    stitch_authorization_url = stitch.initiate_authorization(user_id)
    return redirect(stitch_authorization_url)
```

Once they have authorized Stitch redirects back to your app and provides a
`code` value, use it to complete authorization in order to retrieve and store
their token:

```python
code = request.args.get("code").
stitch.complete_authorization(user_id, code)
```

Finally, retrieve the user's bank accounts:

```python
bank_accounts = stitch.get_bank_accounts(user_id)
for bank_account in bank_accounts:
    print(bank_account)
```

## Installation

First, ensure you have Python 3 installed. Python versions 3.8 and above should
suffice though testing has only been done with 3.10.4 so far.

Assuming you are using bash, `cd` into the Project's root then create and
activate a virtual environment as so:

```
python -m venv .venv
source .venv/bin/activate
```

Next, install the dependencies to run the demo.
[Poetry](https://python-poetry.org/) is used as the main dependency and
packaging tool for this codebase. If you already have Poetry installed, use it
to install the dependencies, if not, skip this step as installing Poetry for
first-time users can be a bit arduous, an alternative is provided just after
this:

To install the dependencies using Poetry, run this command:

```
poetry install --only=default,example
```

`default` are the dependencies exclusive to the Stitch SDK. `example` are the
dependencies necessary for running the demo. If you wish to contribute to the
SDK, also include the `dev` dependencies for testing, linting, formatting etc.

Alternatively, to install the Stitch SDK, install the wheel file that is in the
`dist/` folder:

```
pip install dist/stitch-0.1.0-py3-none-any.whl
```

To install the dependencies required for the demo, use the requirements.txt file
that is in the `example/` folder:

```
pip install -r example/requirements.txt
```

## Running the demo

Make sure you have a valid client-id and client-secret from Stitch. To run the
demo:

```
python example/server.py \
  --stitch-client-id TEXT \
  --stitch-cert-path PATH
```

Alternatively, you can set the following environment variables if you prefer:

```
STITCH_CLIENT_ID=TEXT
STITCH_CERTIFICATE=PATH
python example/server.py
```

The server will launch on localhost, port 3000, make sure that port is
available. Go to "localhost:3000/" on your browser. Click the _List bank
accounts_ button and you'll be redirected to Stitch from where you can authorize
the demo to retrieve your bank accounts as a test user. If successful, you will
be redirected back to the demo and a payload containing all the test-user's bank
accounts shall be returned.
