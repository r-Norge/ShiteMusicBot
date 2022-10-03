import logging
import logging.handlers
import os


class ConsoleFormatter(logging.Formatter):

    def format(self, record):
        gray = "\x1b[38;20m"
        green = "\x1b[32;20m"
        yellow = "\x1b[33;20m"
        blue = "\x1b[34;20m"
        red = "\x1b[31;20m"
        reset = "\x1b[0m"
        match record.levelno:
            case logging.DEBUG:
                color = yellow
            case logging.INFO:
                color = green
            case logging.ERROR:
                color = red
            case _:
                color = gray
        format = blue + "[%(asctime)s]  " + reset + "%(name)-20s" + \
            "[" + color + "%(levelname)-8s" + reset + "]  " + "%(message)s"
        formatter = logging.Formatter(format)
        return formatter.format(record)


class BotLogger(object):
    def __init__(self, debug=None, data_location=None):

        self.log_location = data_location
        self.log_level = debug

        if self.log_level:
            self.log_level = logging.DEBUG

        else:
            self.log_level = logging.INFO

        self.bot_logger = logging.getLogger("musicbot")
        self.bot_logger.setLevel(logging.DEBUG)

        console_formatter = ConsoleFormatter()
        file_format = logging.Formatter("[%(asctime)s]  %(name)-20s[%(levelname)-8s]%(message)s")

        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(console_formatter)

        self.bot_logger.addHandler(console_handler)

        if self.log_location is not None:
            if not os.path.isdir(self.log_location):
                os.makedirs(self.log_location)
                self.bot_logger.info(f"Creating logging directory: {self.log_location}")
            if self.log_level:
                self.bot_logger.info(f"Logging directory: {self.log_location}")
            file_logger = logging.handlers.RotatingFileHandler(f'{self.log_location}/bot.log', mode='a',
                                                               maxBytes=5000, encoding="UTF-8", delay=0, backupCount=5)
            file_logger.setLevel(self.log_level)
            file_logger.setFormatter(file_format)
            self.bot_logger.addHandler(file_logger)
