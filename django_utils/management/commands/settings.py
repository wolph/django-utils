from . import base_command
import pprint


class Command(base_command.CustomBaseCommand):
    help = '''Get a list of the current settings, any arguments given will be
    used to match the settings name (case insensitive).
    '''
    can_import_settings = True
    requires_model_validation = False

    def handle(self, *args, **options):
        from django.conf import settings
        args = map(str.upper, args)
        for k in dir(settings):
            if k.upper() == k:
                v = getattr(settings, k)
                found = not bool(args)
                for arg in args:
                    if arg in k:
                        found = True
                        break

                if found:
                    print '%s: ' % k,
                    pprint.pprint(v)

        super(Command, self).handle(*args, **options)
