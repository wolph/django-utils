import json
import pprint

from django.conf import settings

from . import base_command


def json_default(obj):
    return str(obj)


EXCLUDED_KEYS = {'FILE_CHARSET', 'DEFAULT_CONTENT_TYPE', 'USE_L10N'}


class Command(base_command.CustomBaseCommand):
    help = """Get a list of the current settings, any arguments given will be
    used to match the settings name (case insensitive).
    """
    can_import_settings = True
    requires_model_validation = False
    output_types = ('pprint', 'print', 'json', 'csv')

    def add_arguments(self, parser):
        parser.add_argument('keys', nargs='+')
        parser.add_argument(
            '-o', '--output-type', default='pprint', choices=self.output_types
        )
        parser.add_argument('-k', '--show-keys', action='store_true')

    def render_output(
        self, data, output_type='pprint', show_keys=False, **options
    ):
        if output_type == 'pprint':
            self._render_pprint(data, show_keys)
        elif output_type == 'print':
            self._render_print(data, show_keys)
        elif output_type == 'csv':
            self._render_csv(data, show_keys)
        elif output_type == 'json':
            self._render_json(data)

    @staticmethod
    def _render_pprint(data, show_keys):
        if show_keys:
            print(pprint.pformat(data))
        else:
            for values in data.values():
                print(pprint.pformat(values))

    @staticmethod
    def _render_print(data, show_keys):
        for key, values in data.items():
            if show_keys:
                print(key, end='')
            print(values)

    @staticmethod
    def _to_csv_values(values):
        if isinstance(values, str):
            return [values]
        elif isinstance(values, dict):
            return [f'{k}={v}' for k, v in values.items()]
        else:
            try:
                return [str(value) for value in values]
            except TypeError:
                return [str(values)]

    def _render_csv(self, data, show_keys):
        for key, values in data.items():
            out = []
            if show_keys:
                out.append(key)

            values = self._to_csv_values(values)

            for i, value in enumerate(values):
                if '"' in value:
                    value = value.replace('"', '""')

                if ' ' in value or ',' in value:
                    value = f'"{value}"'

                values[i] = value

            out += values
            print(','.join(out))

    @staticmethod
    def _render_json(data):
        print(json.dumps(data, indent=4, sort_keys=True, default=json_default))

    def handle(self, *args, **options):
        super().handle(*args, **options)
        args = list(map(str.upper, options.get('keys', args)))
        data = dict()
        for key in dir(settings):
            if key.isupper() and key not in EXCLUDED_KEYS:
                value = getattr(settings, key)
                found = False
                for arg in args:
                    if arg in key:
                        found = True
                        break

                if found:
                    data[key] = value

        self.render_output(data, **options)
