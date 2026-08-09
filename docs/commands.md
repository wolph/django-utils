# Management commands

Base classes for Django management commands that process large
querysets safely: `CustomBaseCommand` adds structured logging on top
of `BaseCommand`, and `ChunkedCommand` builds on it with fixed-size
chunked iteration, progress logging, resumable checkpointing, and a
transactional dry-run.

## CustomBaseCommand

`CustomBaseCommand` wraps Django's `BaseCommand` with a
verbosity-aware logger, so a command gets structured logging for free
instead of hand-rolling `self.stdout.write()` calls. `create_logger()`
configures a logger named `management.commands.<module>` (plus the
full module path, and any names listed in `loggers`) at a level driven
by `--verbosity` (`0`=`ERROR`, `1`=`WARN`, `2`=`INFO` (the default),
`3`=`DEBUG`), and exposes it as `self.log`.

```python
from django_utils.management.commands.base_command import CustomBaseCommand


class Command(CustomBaseCommand):
    def handle(self, *args, **options):
        super().handle(*args, **options)
        self.log.info('starting up')
```

API reference: {py:class}`~django_utils.management.commands.base_command.CustomBaseCommand`.

(chunkedcommand)=
## ChunkedCommand

`ChunkedCommand` is a base class for Django management commands that
process large querysets in memory-bounded chunks. It composes with
[`queryset_iterator`](qs-iterator) to iterate
through data in fixed-size batches, logging progress and supporting
resumable checkpointing via `--resume-from` and early stopping via
`--limit`. Dry-run mode rolls back all changes via an
exception-unwound nested transaction, safe for pytest-django's
per-test transactions.

Subclass `ChunkedCommand` and implement `get_queryset()` and
`handle_instance(instance)`:

```python
from django_utils.management.commands.base_command import ChunkedCommand
from myapp.models import MyModel


class Command(ChunkedCommand):
    chunksize = 1000  # Optional: customize batch size (default 1000)
    log_every = 1000  # Optional: log progress every N rows (default 1000)

    def get_queryset(self):
        return MyModel.objects.all()

    def handle_instance(self, instance):
        instance.some_field = 'updated'
        instance.save()
```

Command-line options:

| Option | Effect |
| --- | --- |
| `--chunksize N` | Override the class `chunksize` (default 1000). |
| `--resume-from PK` | Skip rows with pk <= this value (useful for resuming interrupted runs). |
| `--limit N` | Stop after processing N rows and log the resume-from hint. |
| `--dry-run` | Run inside a transaction and roll everything back. |
| `--log-every N` | Log progress every N rows (default 1000). |

Below is a realistic transcript of a run that gets interrupted and
resumed. The exact `--resume-from` value comes from the last
successfully processed row, logged both on interrupt and on hitting
`--limit`:

<pre data-terminal>
$ python manage.py backfill_totals
2026-08-05 10:02:11 INFO 1000 rows processed (842.3 rows/s), last pk 1000
2026-08-05 10:02:12 INFO 2000 rows processed (918.7 rows/s), last pk 2000
2026-08-05 10:02:13 INFO 3000 rows processed (935.1 rows/s), last pk 3000
2026-08-05 10:02:14 INFO 4000 rows processed (940.4 rows/s), last pk 4000
^C
2026-08-05 10:02:14 WARNING interrupted after 4000 rows; continue with --resume-from 4000
Traceback (most recent call last):
  ...
KeyboardInterrupt

$ python manage.py backfill_totals --resume-from 4000
2026-08-05 10:05:02 INFO 1000 rows processed (901.2 rows/s), last pk 5000
2026-08-05 10:05:03 INFO 2000 rows processed (927.6 rows/s), last pk 6000
2026-08-05 10:05:04 INFO done: 2143 rows processed, last pk 6143
</pre>

If no row completed before the interrupt, the resume hint is skipped
in favor of a plain instruction: `interrupted before completing any
rows; re-run without --resume-from`. A `--resume-from None` would be
meaningless.

:::{dropdown} Caveat: dry-run transaction scope
`--dry-run` wraps only the queryset's own database alias
(`self.get_queryset().db`); writes `handle_instance` makes to OTHER
databases are not covered and will still be committed. Under
`--dry-run`, the resume hints logged refer to work that was rolled
back. Do not feed them to a real run.

The rollback itself is implemented as an exception unwound out of a
nested `transaction.atomic()`, not `transaction.set_rollback(True)`:
`set_rollback` marks the whole connection, which would poison an
enclosing atomic block (a caller's transaction, or pytest-django's
per-test transaction). Unwinding a nested atomic via an exception
rolls back only its own savepoint.
:::

Deliberately out of scope: retries and parallelism. This is iterate,
log and checkpoint, nothing more.

API reference: {py:class}`~django_utils.management.commands.base_command.ChunkedCommand`,
full module at {doc}`django_utils`.
