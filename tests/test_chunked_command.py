"""Tests for ChunkedCommand.

Commands are exercised through ``call_command`` with a real command
instance — the same code path ``manage.py`` uses — not by calling
private helpers.  ``verbosity=2`` is required for INFO-level progress
logs (call_command defaults to 1 = WARN).
"""

import logging

import pytest
from django.core.management import call_command
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
        self.interrupt_after: int | None = None

    def get_queryset(self) -> dj_models.QuerySet[models.Spam]:
        return models.Spam.objects.all()

    def handle_instance(self, instance: models.Spam) -> None:
        self.seen.append(instance.pk)
        if self.interrupt_after and len(self.seen) >= self.interrupt_after:
            raise KeyboardInterrupt


class MutateSpam(base_command.ChunkedCommand):
    def get_queryset(self) -> dj_models.QuerySet[models.Spam]:
        return models.Spam.objects.all()

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
    # ceil(5/2) = 3 data chunks + 1 final empty probe.
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
    command = CollectSpam()
    command.interrupt_after = 2
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        with pytest.raises(KeyboardInterrupt):
            call_command(command, verbosity=2)
    message = ' '.join(record.getMessage() for record in caplog.records)
    assert '--resume-from' in message
    assert str(command.seen[-1]) in message


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
