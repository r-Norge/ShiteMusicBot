import logging.handlers
import logging

class BotLogger(object):
    def __init__(self, debug=None, data_location=None):
        self.log_location = data_location
        self.log_level = debug

        if self.log_level:
            self.log_level = logging.DEBUG

        else:
            self.log_level = logging.INFO

        self.bot_logger = logging.getLogger("logger")
        self.bot_logger.setLevel(logging.DEBUG)

        log_formatter = logging.Formatter("%(asctime)s:%(name)s:%(levelname)s:%(message)s")

        if self.log_location is not None:
            file_logger = logging.handlers.RotatingFileHandler(f'{self.log_location}/logs.log',
                                          mode='a', maxBytes=50000, encoding=None, delay=0, backupCount=5)
            file_logger.setLevel(self.log_level)
            file_logger.setFormatter(log_formatter)
            self.bot_logger.addHandler(file_logger)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(log_formatter)

        self.bot_logger.addHandler(console_handler)

