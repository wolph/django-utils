from __future__ import print_function

import six
import json
import pprint

from django.conf import settings

from . import base_command


def json_default(obj):
    return str(obj)


class Command(base_command.CustomBaseCommand):
    help = '''Get a list of the current settings, any arguments given will be
    used to match the settings name (case insensitive).
    '''
    can_import_settings = True
    requires_model_validation = False
    output_types = ['pprint', 'print', 'json', 'csv']

    def add_arguments(self, parser):
        parser.add_argument('keys', nargs='+')
        parser.add_argument(
            '-o', '--output-type', default='pprint', choices=self.output_types)
        parser.add_argument('-k', '--show-keys', action='store_true')

    def render_output(self, data, output_type='pprint', show_keys=False,
                      **options):
        if output_type == 'pprint':
            if show_keys:
                pprint.pprint(data)
            else:
                for key, values in data.items():
                    pprint.pprint(values)

        elif output_type == 'print':
            for key, values in data.items():
                if show_keys:
                    print(key, end='')
                print(values)

        elif output_type == 'csv':
            for key, values in data.items():
                out = []
                if show_keys:
                    out.append(key)

                if isinstance(values, six.string_types):
                    values = [values]
                elif isinstance(values, dict):
                    values = ['%s=%s' % item for item in values.items()]
                else:
                    try:
                        values = [str(value) for value in values]
                    except TypeError:
                        values = [str(values)]

                for i, value in enumerate(values):
                    if '"' in value:
                        value = value.replace('"', '""')

                    if ' ' in value or ',' in value:
                        value = '"%s"' % value

                    values[i] = value

                out += values
                print(','.join(out))

        elif output_type == 'json':
            print(json.dumps(data, indent=4, sort_keys=True,
                             default=json_default))

    def handle(self, *args, **options):
        super(Command, self).handle(*args, **options)
        args = list(map(str.upper, options.get('keys', args)))
        data = dict()
        for key in dir(settings):
            if key.isupper():
                value = getattr(settings, key)
                found = False
                for arg in args:
                    if arg in key:
                        found = True
                        break

                if found:
                    data[key] = value

        self.render_output(data, **options)
