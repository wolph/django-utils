"""Tests for ChunkedCommand.

Commands are exercised through ``call_command`` with a real command
instance — the same code path ``manage.py`` uses — not by calling
private helpers.  ``verbosity=2`` is required for INFO-level progress
logs (call_command defaults to 1 = WARN).
"""

import logging

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import models as dj_models
from django_utils import query_debug
from django_utils.management.commands import base_command

from tests.test_app import models

pytestmark = pytest.mark.django_db

LOGGER = 'management.commands.test_chunked_command'


class CollectSpam(base_command.ChunkedCommand):
    """Records every pk it sees; optionally raises partway."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[int] = []
        self.interrupt_on: int | None = None

    def get_queryset(self) -> dj_models.QuerySet[models.Spam]:
        return models.Spam.objects.all()

    def handle_instance(self, instance: models.Spam) -> None:
        if (
            self.interrupt_on is not None
            and len(self.seen) + 1 >= self.interrupt_on
        ):
            raise KeyboardInterrupt
        self.seen.append(instance.pk)


class MutateSpam(base_command.ChunkedCommand):
    def __init__(self) -> None:
        super().__init__()
        self.count: int = 0
        self.interrupt_on: int | None = None

    def get_queryset(self) -> dj_models.QuerySet[models.Spam]:
        return models.Spam.objects.all()

    def handle_instance(self, instance: models.Spam) -> None:
        if (
            self.interrupt_on is not None
            and self.count + 1 >= self.interrupt_on
        ):
            raise KeyboardInterrupt
        self.count += 1
        instance.a = 'changed'
        instance.save()


class MutateOtherAliasSpam(base_command.ChunkedCommand):
    """Like MutateSpam, but its queryset targets the 'other' alias --
    exercises dry-run rollback scoped to the queryset's own database."""

    def get_queryset(self) -> dj_models.QuerySet[models.Spam]:
        return models.Spam.objects.using('other')

    def handle_instance(self, instance: models.Spam) -> None:
        instance.a = 'changed'
        instance.save()


@pytest.fixture
def spam_rows():
    return [models.Spam.objects.create(a=f's{n}') for n in range(5)]


def test_processes_all_rows_in_pk_order(spam_rows):
    command = CollectSpam()
    call_command(command, verbosity=2)
    assert command.seen == sorted(spam.pk for spam in spam_rows)


def test_chunksize_bounds_queries(spam_rows):
    command = CollectSpam()
    with query_debug.query_budget(warn_at=100) as budget:
        call_command(command, verbosity=2, chunksize=2)
    # queryset_iterator fetches ceil(5/2)=3 data chunks, then one more empty
    # query to discover end of iteration (never short-circuits on partial
    # final chunk). Total: 3 data + 1 probe = 4 queries.
    assert budget.count == 4
    assert len(command.seen) == 5


def test_resume_from_skips_processed_rows(spam_rows):
    pks = sorted(spam.pk for spam in spam_rows)
    command = CollectSpam()
    call_command(command, verbosity=2, resume_from=str(pks[1]))
    assert command.seen == pks[2:]


def test_limit_stops_early_and_logs_resume_hint(spam_rows, caplog):
    pks = sorted(spam.pk for spam in spam_rows)
    command = CollectSpam()
    with caplog.at_level(logging.INFO, logger=LOGGER):
        call_command(command, verbosity=2, limit=2)
    assert command.seen == pks[:2]
    assert any(
        '--resume-from' in record.getMessage() for record in caplog.records
    )


def test_dry_run_rolls_back(spam_rows):
    call_command(MutateSpam(), verbosity=2, dry_run=True)
    assert not models.Spam.objects.filter(a='changed').exists()


def test_without_dry_run_commits(spam_rows):
    call_command(MutateSpam(), verbosity=2)
    assert models.Spam.objects.filter(a='changed').count() == 5


def test_keyboard_interrupt_logs_resume_hint(spam_rows, caplog):
    pks = sorted(spam.pk for spam in spam_rows)
    command = CollectSpam()
    command.interrupt_on = 2
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        with pytest.raises(KeyboardInterrupt):
            call_command(command, verbosity=2)
    # interrupt_on=2 raises when len(seen)+1 >= 2, i.e., before 2nd
    # append. So only the 1st pk is in seen; the resume hint names the
    # last completed pk.
    assert command.seen == pks[:1]
    message = ' '.join(record.getMessage() for record in caplog.records)
    assert '--resume-from' in message
    assert str(pks[0]) in message
    assert 'after 1 rows' in message


def test_keyboard_interrupt_on_first_row_suggests_plain_rerun(
    spam_rows, caplog
):
    """No row completed: a `--resume-from None` hint would be pasted
    verbatim by an operator and break; the message must say to re-run
    without --resume-from instead."""
    command = CollectSpam()
    command.interrupt_on = 1
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        with pytest.raises(KeyboardInterrupt):
            call_command(command, verbosity=2)
    assert command.seen == []
    message = ' '.join(record.getMessage() for record in caplog.records)
    assert 'interrupted before completing any rows' in message
    assert 'None' not in message


def test_progress_logged_every_log_every_rows(spam_rows, caplog):
    command = CollectSpam()
    with caplog.at_level(logging.INFO, logger=LOGGER):
        call_command(command, verbosity=2, log_every=1)
    progress = [
        record
        for record in caplog.records
        if 'rows processed' in record.getMessage()
    ]
    assert len(progress) >= 5


def test_chunksize_zero_raises_command_error(spam_rows):
    with pytest.raises(CommandError, match='--chunksize must be >= 1'):
        call_command(CollectSpam(), verbosity=2, chunksize=0)


def test_log_every_zero_raises_command_error(spam_rows):
    with pytest.raises(CommandError, match='--log-every must be >= 1'):
        call_command(CollectSpam(), verbosity=2, log_every=0)


def test_dry_run_with_keyboard_interrupt_rolls_back(spam_rows):
    command = MutateSpam()
    command.interrupt_on = 2
    with pytest.raises(KeyboardInterrupt):
        call_command(command, verbosity=2, dry_run=True)
    # Even though interrupted during processing, dry-run transaction
    # rolled back.
    assert not models.Spam.objects.filter(a='changed').exists()


def test_limit_zero_raises_command_error(spam_rows):
    command = CollectSpam()
    with pytest.raises(CommandError, match='--limit must be >= 1'):
        call_command(command, verbosity=2, limit=0)
    assert command.seen == []


def test_limit_negative_raises_command_error(spam_rows):
    command = CollectSpam()
    with pytest.raises(CommandError, match='--limit must be >= 1'):
        call_command(command, verbosity=2, limit=-1)
    assert command.seen == []


def test_bad_resume_from_raises_command_error(spam_rows):
    with pytest.raises(CommandError, match='not a valid primary key'):
        call_command(CollectSpam(), verbosity=2, resume_from='not-a-pk')


@pytest.mark.django_db(databases=['default', 'other'])
def test_dry_run_rolls_back_on_queryset_own_alias():
    """dry-run must roll back on the alias get_queryset() itself uses,
    not always 'default' -- a command whose queryset targets 'other'
    must not leave committed writes there."""
    for n in range(3):
        models.Spam.objects.using('other').create(a=f's{n}')
    call_command(MutateOtherAliasSpam(), verbosity=2, dry_run=True)
    assert not models.Spam.objects.using('other').filter(a='changed').exists()
