import logging
import time
from typing import Any, ClassVar, cast

from django.core.management import base
from django.db import models, transaction
from python_utils import logger

from django_utils import queryset as queryset_utils

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
        self.log = self.logger  # type: ignore[method-assign,assignment]  # ty: ignore[invalid-assignment]
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


class _DryRunRollback(Exception):  # noqa: N818
    """Raised to unwind a ``--dry-run`` transaction; never escapes."""


class ChunkedCommand(CustomBaseCommand):
    """Batch-process a queryset in bounded, resumable chunks.

    Subclasses implement ``get_queryset()`` and ``handle_instance()``;
    the base iterates via ``queryset_iterator`` (memory bounded on both
    the client and the database), logs progress with a rate every
    ``--log-every`` rows, stops after ``--limit`` rows, resumes after a
    known pk with ``--resume-from``, and rolls everything back under
    ``--dry-run``.  On interrupt or early stop it logs the exact
    ``--resume-from`` value to continue with.

    Deliberately out of scope: retries and parallelism — this is
    iterate + log + checkpoint, nothing more.
    """

    chunksize: ClassVar[int] = 1000
    log_every: ClassVar[int] = 1000

    def add_arguments(self, parser: base.CommandParser) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            '--chunksize',
            type=int,
            default=self.chunksize,
            help='Rows fetched per query (default %(default)s).',
        )
        parser.add_argument(
            '--resume-from',
            default=None,
            help='Process only rows with pk greater than this value.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Stop after this many rows.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run inside a transaction and roll everything back.',
        )
        parser.add_argument(
            '--log-every',
            type=int,
            default=self.log_every,
            help='Log progress every N rows (default %(default)s).',
        )

    def get_queryset(self) -> models.QuerySet[Any]:
        """Return the queryset to process. Subclasses must implement."""
        raise NotImplementedError

    def handle_instance(self, instance: Any) -> None:
        """Process one row. Subclasses must implement."""
        raise NotImplementedError

    def handle(self, *args: Any, **options: Any) -> str | None:
        super().handle(*args, **options)
        if options.get('dry_run'):
            # Exception-unwind instead of transaction.set_rollback(True):
            # set_rollback marks the whole connection, which would poison
            # an enclosing atomic block (e.g. a caller's transaction, or
            # pytest-django's per-test transaction). Unwinding a nested
            # atomic via an exception rolls back only its own savepoint.
            try:
                with transaction.atomic():
                    self._process(**options)
                    raise _DryRunRollback  # noqa: TRY301
            except _DryRunRollback:
                cast(logging.Logger, self.log).info(
                    'dry run: all changes rolled back'
                )
            return None
        self._process(**options)
        return None

    def _process(self, **options: Any) -> None:
        log = cast(logging.Logger, self.log)
        queryset = self.get_queryset()
        chunksize: int = options.get('chunksize') or self.chunksize
        log_every: int = options.get('log_every') or self.log_every
        limit: int | None = options.get('limit')
        resume_from: str | None = options.get('resume_from')
        start_after: Any = None
        if resume_from is not None:
            # Command-line values are strings; convert through the pk
            # field so integer/UUID/etc. pks compare correctly.
            start_after = queryset.model._meta.pk.to_python(resume_from)

        processed = 0
        last_pk: Any = None
        started = time.monotonic()
        rows = queryset_utils.queryset_iterator(
            queryset, chunksize=chunksize, start_after=start_after
        )
        try:
            for instance in rows:
                last_pk = instance.pk
                self.handle_instance(instance)
                processed += 1
                if processed % log_every == 0:
                    elapsed = max(time.monotonic() - started, 1e-9)
                    log.info(
                        '%d rows processed (%.1f rows/s), last pk %r',
                        processed,
                        processed / elapsed,
                        last_pk,
                    )
                if limit is not None and processed >= limit:
                    log.info(
                        'limit %d reached; continue with --resume-from %s',
                        limit,
                        last_pk,
                    )
                    return
        except KeyboardInterrupt:
            log.warning(
                'interrupted after %d rows; continue with --resume-from %s',
                processed,
                last_pk,
            )
            raise
        log.info('done: %d rows processed, last pk %r', processed, last_pk)
