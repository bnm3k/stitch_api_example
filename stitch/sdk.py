import logging


class Authorization:
    def __init__(self, client_id, client_secret, logger=None):
        self.client_id = client_id
        self.client_secret = client_secret

        if logger is None:
            logger = logging.getLogger(__name__)
            logger.addHandler(logging.NullHandler())
            logger.disabled = True

        self.logger = logger

    def get_bank_accounts(self):
        return "To be Implemented"
