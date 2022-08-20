import os
from flask import Flask, Blueprint

import click
import pathlib
import stitch.sdk

user_bp = Blueprint("user", __name__)


@user_bp.route("/login", methods=("GET",))
def hello():
    return "Hello there"


def load_config(app, test_config=None):
    # set up logging
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s]: %(message)s",
        datefmt="%H:%M:%S",
    )

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


def load_handlers(app):

    # add handlers
    @app.route("/")
    def index():
        return "index\n"

    app.register_blueprint(user_bp)


def create_app(test_config=None):
    app = Flask(__name__)

    # configure app
    load_config(app, test_config)

    # load handlers
    load_handlers(app)

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
def run_app(stitch_client_id, stitch_cert_path):

    app = create_app()
    app.logger.info(f"stitch client id: {stitch_client_id}")
    app.logger.info(f"stitch cert path: {stitch_cert_path}")
    app.run(
        host="127.0.0.1",
        port=3000,
        load_dotenv=False,
    )


if __name__ == "__main__":
    # load env from .env file
    from dotenv import load_dotenv

    load_dotenv()
    run_app()
