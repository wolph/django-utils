import sys
from . import base_command

try:
    from django_admin_generator.management.commands.django_admin_generator \
        import Command
except ImportError:
    class Command(base_command.CustomBaseCommand):
        def handle(self, *args, **kwargs):
            print >>sys.stderr, (
                'This command has been moved to the `django_admin_generator` '
                'package. Please use `pip install django_admin_generator` to '
                'install')

