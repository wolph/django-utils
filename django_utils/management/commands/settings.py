import argparse
import json
import pprint
from typing import Any, ClassVar

from django.conf import settings

from . import base_command


def json_default(obj: Any) -> str:
    return str(obj)


EXCLUDED_KEYS = {'FILE_CHARSET', 'DEFAULT_CONTENT_TYPE', 'USE_L10N'}


class Command(base_command.CustomBaseCommand):
    help = """Get a list of the current settings, any arguments given will be
    used to match the settings name (case insensitive).
    """
    can_import_settings = True
    requires_model_validation = False
    output_types: ClassVar[tuple[str, ...]] = (
        'pprint',
        'print',
        'json',
        'csv',
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument('keys', nargs='+')
        parser.add_argument(
            '-o', '--output-type', default='pprint', choices=self.output_types
        )
        parser.add_argument('-k', '--show-keys', action='store_true')

    def render_output(
        self,
        data: dict[str, Any] | None,
        output_type: str | None = 'pprint',
        show_keys: bool = False,
        **options: Any,
    ) -> None:
        if data is None:
            return

        if output_type == 'pprint':
            self._render_pprint(data, show_keys)
        elif output_type == 'print':
            self._render_print(data, show_keys)
        elif output_type == 'csv':
            self._render_csv(data, show_keys)
        elif output_type == 'json':
            self._render_json(data)

    @staticmethod
    def _render_pprint(data: dict[str, Any], show_keys: bool) -> None:
        if show_keys:
            print(pprint.pformat(data))
        else:
            for values in data.values():
                print(pprint.pformat(values))

    @staticmethod
    def _render_print(data: dict[str, Any], show_keys: bool) -> None:
        for key, values in data.items():
            if show_keys:
                print(key, end='')
            print(values)

    @staticmethod
    def _to_csv_values(values: Any) -> list[str]:
        if isinstance(values, str):
            return [values]
        elif isinstance(values, dict):
            return [f'{k}={v}' for k, v in values.items()]
        else:
            try:
                return [str(value) for value in values]
            except TypeError:
                return [str(values)]

    def _render_csv(self, data: dict[str, Any], show_keys: bool) -> None:
        for key, values in data.items():
            out: list[str] = []
            if show_keys:
                out.append(key)

            str_values = self._to_csv_values(values)

            for i, value in enumerate(str_values):
                if '"' in value:
                    value = value.replace('"', '""')

                if ' ' in value or ',' in value:
                    value = f'"{value}"'

                str_values[i] = value

            out += str_values
            print(','.join(out))

    @staticmethod
    def _render_json(data: dict[str, Any]) -> None:
        print(json.dumps(data, indent=4, sort_keys=True, default=json_default))

    def handle(self, *args: Any, **options: Any) -> None:
        super().handle(*args, **options)
        keys = [key.upper() for key in options.get('keys', args)]
        data: dict[str, Any] = {}
        for key in dir(settings):
            if key.isupper() and key not in EXCLUDED_KEYS:
                value = getattr(settings, key)
                found = False
                for arg in keys:
                    if arg in key:
                        found = True
                        break

                if found:
                    data[key] = value

        self.render_output(data, **options)
