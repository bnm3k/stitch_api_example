import os
from flask import Flask, Blueprint, current_app, redirect

import click
import pathlib
import stitch.sdk

user_bp = Blueprint("user", __name__)


@user_bp.route("/bank_accounts", methods=("GET",))
def retrieve_user_bank_accounts():
    #  first check if we have user's token and refresh token
    # if so, make an API call to stitch

    # if not, have user authorize via stitch
    # store token + refresh token
    # then retrieve bank accounts
    # return redirect("https://www.google.com", 307)
    stitch_authz = current_app.config["stitch_authorization"]
    res = stitch_authz.get_bank_accounts()
    return res


@user_bp.route("/")
def index():
    html = """
    <form>
      <button formaction="/bank_accounts">List bank accounts</button>
    </form>
    """
    return html


def init_app(stitch_config, db_config=None):
    # create app
    app = Flask(__name__)

    # set up logging
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        datefmt="%H:%M:%S",
    )

    # set up authz for stitch api
    stitch_authorization = stitch.sdk.Authorization(
        client_id=stitch_config["client_id"],
        client_secret=stitch_config["client_secret"],
    )
    app.config["stitch_authorization"] = stitch_authorization

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

    # configure app
    app = init_app(stitch_config)

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
