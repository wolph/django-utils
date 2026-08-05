# Management commands

Base classes for Django management commands that process large
querysets safely: `CustomBaseCommand` adds structured logging on top
of `BaseCommand`, and `ChunkedCommand` builds on it with fixed-size
chunked iteration, progress logging, resumable checkpointing, and a
transactional dry-run.

## CustomBaseCommand

## ChunkedCommand
