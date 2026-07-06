import logging
from typing import Any, ClassVar

from django.core.management import base
from python_utils import logger

DEFAULT_VERBOSITY = 2
VERBOSITY_LOG_MAP = {
    0: logging.ERROR,
    1: logging.WARN,
    2: logging.INFO,
    3: logging.DEBUG,
}


class CustomBaseCommand(base.BaseCommand, logger.Logged):
    loggers: ClassVar[tuple[str, ...]] = ()

    def __init__(self) -> None:
        self.verbosity = DEFAULT_VERBOSITY
        base.BaseCommand.__init__(self)

    def handle(self, *args: Any, **kwargs: Any) -> str | None:
        self.verbosity = int(kwargs.get('verbosity', DEFAULT_VERBOSITY))
        self.logger = self.create_logger()
        # `log` is a classmethod on `logger.Logged`; shadowing it with the
        # instance's `logging.Logger` is intentional.
        self.log = self.logger  # type: ignore[method-assign,assignment]
        return None

    def create_logger(self) -> logging.Logger:
        module = self.__class__.__module__

        module_name = module.split('.')[-1]
        loggers = (
            f'management.commands.{module_name}',
            module,
            *self.loggers,
        )
        logger_ = logging.getLogger(loggers[0])
        for logger_name in loggers:
            logger_ = logging.getLogger(logger_name)
            logger_.setLevel(VERBOSITY_LOG_MAP[self.verbosity])

        return logger_


class CustomAppCommand(CustomBaseCommand, base.AppCommand):
    pass
