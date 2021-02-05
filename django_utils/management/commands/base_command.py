import logging
from python_utils import logger
from django.core.management import base


DEFAULT_VERBOSITY = 2
VERBOSITY_LOG_MAP = {
    0: logging.ERROR,
    1: logging.WARN,
    2: logging.INFO,
    3: logging.DEBUG,
}


class CustomBaseCommand(base.BaseCommand, logger.Logged):
    loggers = ()

    def __init__(self):
        self.verbosity = DEFAULT_VERBOSITY
        base.BaseCommand.__init__(self)

    def handle(self, *args, **kwargs):
        self.verbosity = int(kwargs.get('verbosity', DEFAULT_VERBOSITY))
        self.log = self.logger = self.create_logger()

    def create_logger(self):
        module = self.__class__.__module__

        loggers = (
            'management.commands.%s' % module.split('.')[-1],
            module,
        ) + self.loggers
        for logger_name in loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(VERBOSITY_LOG_MAP[self.verbosity])

        return logger


class CustomAppCommand(CustomBaseCommand, base.AppCommand):
    pass
