from __future__ import print_function

import sys
from . import base_command

try:
    from django_admin_generator.management.commands.admin_generator \
        import Command
except ImportError:
    class Command(base_command.CustomBaseCommand):

        def handle(self, *args, **kwargs):
            print('This command has been moved to the `django_admin_generator`'
                  ' package. Please use `pip install django_admin_generator` '
                  'to install', file=sys.stderr)
