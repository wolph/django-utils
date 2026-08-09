import logging
import time
from typing import Any, ClassVar, cast

from django.core.exceptions import ValidationError
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


def _resolve_start_after(
    queryset: models.QuerySet[Any], resume_from: str | None
) -> Any:
    """Convert ``--resume-from`` to a pk value via the queryset's model.

    Command-line values are strings; converting through the pk field
    lets integer/UUID/etc. pks compare correctly. Raises ``CommandError``
    (not a raw ``ValidationError``) for a value the pk field rejects.
    """
    if resume_from is None:
        return None
    try:
        return queryset.model._meta.pk.to_python(resume_from)
    except ValidationError as exc:
        raise base.CommandError(
            f'--resume-from {resume_from!r} is not a valid primary key '
            f'for {queryset.model.__name__}: {exc}'
        ) from exc


class ChunkedCommand(CustomBaseCommand):
    """Batch-process a queryset in bounded, resumable chunks.

    Subclasses implement ``get_queryset()`` and ``handle_instance()``;
    the base iterates via ``queryset_iterator`` (memory bounded on both
    the client and the database), logs progress with a rate every
    ``--log-every`` rows, stops after ``--limit`` rows, resumes after a
    known pk with ``--resume-from``, and rolls everything back under
    ``--dry-run``.  On interrupt or early stop it logs the exact
    ``--resume-from`` value to continue with.

    ``--dry-run`` wraps only the queryset's own database alias
    (``self.get_queryset().db``); writes ``handle_instance`` makes to
    OTHER databases are not covered and will still be committed. Also
    note: under ``--dry-run``, the resume hints logged refer to work
    that was rolled back -- do not feed them to a real run.

    Deliberately out of scope: retries and parallelism. This is
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
                # Double get_queryset() call is harmless: querysets are
                # lazy, and this scopes the rollback to the queryset's
                # own alias rather than always 'default'.
                with transaction.atomic(using=self.get_queryset().db):
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
        raw_chunksize = options.get('chunksize')
        chunksize: int = (
            self.chunksize if raw_chunksize is None else raw_chunksize
        )
        raw_log_every = options.get('log_every')
        log_every: int = (
            self.log_every if raw_log_every is None else raw_log_every
        )
        if chunksize < 1:
            raise base.CommandError(
                f'--chunksize must be >= 1, got {chunksize}'
            )
        if log_every < 1:
            raise base.CommandError(
                f'--log-every must be >= 1, got {log_every}'
            )
        limit: int | None = options.get('limit')
        if limit is not None and limit < 1:
            raise base.CommandError(f'--limit must be >= 1, got {limit}')
        resume_from: str | None = options.get('resume_from')
        start_after: Any = _resolve_start_after(queryset, resume_from)

        processed: int = 0
        last_pk: Any = None
        started: float = time.monotonic()
        rows = queryset_utils.queryset_iterator(
            queryset, chunksize=chunksize, start_after=start_after
        )
        try:
            for instance in rows:
                self.handle_instance(instance)
                last_pk = instance.pk
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
            if last_pk is None:
                # No row completed; a --resume-from hint would be
                # 'None' verbatim, so tell the operator to just re-run.
                log.warning(
                    'interrupted before completing any rows; re-run '
                    'without --resume-from'
                )
            else:
                log.warning(
                    'interrupted after %d rows; continue with '
                    '--resume-from %s',
                    processed,
                    last_pk,
                )
            raise
        log.info('done: %d rows processed, last pk %r', processed, last_pk)
