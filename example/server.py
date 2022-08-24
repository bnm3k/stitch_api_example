import os
from flask import Flask, Blueprint, current_app, redirect, request, url_for
import sqlite3
import time
from typing import Optional
import json

import click
import pathlib
from stitch import UserTokenStoreInterface, TokenDetails, Stitch

# ============================ HANDLERS =======================================
# =============================================================================

user_bp = Blueprint("user", __name__)


@user_bp.route("/bank_accounts", methods=("GET",))
def retrieve_bank_accounts():
    user_id = 1  # for demo, TODO, use sessions to retrieve user id
    stitch = current_app.config["stitch"]

    if stitch.should_authorize(user_id):
        stitch_authorization_url = stitch.initiate_authorization(user_id)
        return redirect(stitch_authorization_url)

    bank_accounts = stitch.get_bank_accounts(user_id)
    return bank_accounts


@user_bp.route("/")
def index():
    html = """
    <form>
      <button formaction="/bank_accounts">List bank accounts</button>
    </form>
    """
    return html


@user_bp.route("/return", methods=("GET",))
def handle_return_from_stitch_sso():
    user_id = 1  # for demo, TODO, use sessions to retrieve user id
    stitch = current_app.config["stitch"]

    code = request.args.get("code")
    state = request.args.get("state")
    # scope = request.args.get("scope")

    stitch.complete_authorization(user_id, code, state)
    return redirect(url_for("user.retrieve_bank_accounts"))


# =============================================================================
# ============================ DATABASE ACCESS ================================


def init_db(db_file):
    # schema = []
    # schema.append(
    schema_sql = """
    create table if not exists users(
        id integer primary key,
        username text unique not null
    );

    create table if not exists user_stitch_tokens(
        user_id integer primary key,

        id_token blob not null,
        access_token blob not null,
        expires_at int not null,
        token_type str not null,
        refresh_token blob not null,
        scope text not null,

        foreign key(user_id) references users(id)
    );
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.executescript(schema_sql)
        conn.commit()
    finally:
        if conn:
            conn.close()


def seed_db(db_file):
    test_user = "test-user"

    conn = None
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("insert into users(username) values (?)", (test_user,))
        conn.commit()
    except sqlite3.IntegrityError as e:
        pass
    finally:
        if conn:
            conn.close()


class SqliteUserTokenStore(UserTokenStoreInterface):
    def __init__(self, db_file):
        self._db_file = db_file

    def get_token_details(self, user_id: int) -> Optional[TokenDetails]:
        conn = None
        token_details = None
        try:
            conn = sqlite3.connect(self._db_file)
            c = conn.cursor()
            res = c.execute(
                """
            select id_token, access_token, expires_at, token_type, refresh_token, scope
            from user_stitch_tokens where user_id = ?
            """,
                (user_id,),
            ).fetchone()
            if res is not None:
                token_details = TokenDetails(*res)
        finally:
            if conn:
                conn.close()
        return token_details

    def set_token_details(self, user_id: int, td: TokenDetails):
        conn = None
        td_as_tuple = (
            td.id_token,
            td.access_token,
            td.expires_at_seconds_from_epoch,
            td.token_type,
            td.refresh_token,
            td.scope,
        )
        try:
            conn = sqlite3.connect(self._db_file)
            c = conn.cursor()
            c.execute("pragma foreign_keys=1")
            c.execute(
                """
            insert into
            user_stitch_tokens(user_id, id_token, access_token, expires_at, token_type, refresh_token, scope)
            values (?,?,?,?,?,?,?)
            on conflict(user_id)
            do update set
                id_token=excluded.id_token,
                access_token=excluded.access_token,
                expires_at=excluded.expires_at,
                token_type=excluded.token_type,
                refresh_token=excluded.refresh_token,
                scope=excluded.scope
            """,
                (user_id, *td_as_tuple),
            )
            conn.commit()
        finally:
            if conn:
                conn.close()
        return

    def delete_expired_tokens(self):
        conn = None
        try:
            conn = sqlite3.connect(self._db_file)
            c = conn.cursor()
            now = time.time()
            c.execute(
                "delete from user_stitch_tokens where expires_at <= ?",
                (now,),
            )
            conn.commit()
        finally:
            if conn:
                conn.close()


# =============================================================================
# ============================INITIALIZATION===================================


def init_app(stitch_config, db_config):
    # create app
    app = Flask(__name__)

    # set up logging
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        datefmt="%H:%M:%S",
    )

    # set up database

    db_file = db_config["db_file"]
    init_db(db_file)
    seed_db(db_file)
    app.config["db_file"] = db_file

    # set up authz for stitch api
    user_token_store = SqliteUserTokenStore(db_file)
    stitch_access = Stitch(
        client_id=stitch_config["client_id"],
        client_secret=stitch_config["client_secret"],
        redirect_uri="http://localhost:3000/return",
        user_token_store=user_token_store,
    )
    app.config["stitch"] = stitch_access

    # since this is for a demo, override debug config and
    # set to True
    app.config["DEBUG"] = True

    # add CORS headers for dev
    if app.config["DEBUG"] == True:
        from flask_cors import CORS

        CORS(app)
        app.logger.info("add CORS headers. For development env only")
    else:
        app.logger.info("CORS disabled")

    # load handlers
    app.register_blueprint(user_bp)

    return app


# =============================================================================
# ========================== CLI ==============================================


def _validate_is_nonempty(ctx, param, val):
    if val is None:
        raise click.BadParameter(f"is empty")
    return val


def _validate_file_path(ctx, param, val):
    _validate_is_nonempty(ctx, param, val)
    if not os.path.exists(val):
        raise click.BadParameter(f"{val} does not exist")
    if not os.path.isfile(val):
        raise click.BadParameter(f"{val} is not a file")
    return val


@click.command()
@click.option(
    "--stitch-client-id",
    help="client_id provided by stitch when you register for test dev",
    envvar="STITCH_CLIENT_ID",
    callback=_validate_is_nonempty,
)
@click.option(
    "--stitch-cert-path",
    help="file path to certificate that is provided by stitch when you register for test dev",
    envvar="STITCH_CERTIFICATE",
    type=pathlib.Path,
    callback=_validate_file_path,
)
def run_server(stitch_client_id, stitch_cert_path):
    # stitch config
    stitch_client_secret = None
    with open(stitch_cert_path, "r") as f:
        stitch_client_secret = f.read()
    stitch_config = {
        "client_id": stitch_client_id,
        "client_secret": stitch_client_secret,
    }

    # db config for sqlite
    db_filename = "db.sqlite"
    db_filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_filename)
    # db_file = ":memory:"
    db_config = {
        "db_file": db_filepath,
    }

    # configure app
    app = init_app(stitch_config, db_config)

    app.logger.info(f"stitch client id: {stitch_client_id}")
    app.logger.info(f"stitch cert path: {stitch_cert_path}")

    # run server
    app.run(
        host="127.0.0.1",
        port=3000,
        load_dotenv=False,
    )


if __name__ == "__main__":
    # load env from .env file
    from dotenv import load_dotenv

    load_dotenv()
    run_server()
# =============================================================================
