import argparse
import datetime

import pytest
from django_utils.management.commands import admin_autogen, settings


@pytest.fixture
def settings_command():
    return settings.Command()


def test_settings_command_empty(settings_command):
    settings_command.add_arguments(argparse.ArgumentParser())
    settings_command.handle()


def test_settings_command_no_type(settings_command):
    settings_command.render_output(None, output_type=None)


def test_settings_command_unknown_type(settings_command):
    # An output_type that matches none of the known renderers should be a
    # silent no-op (argparse `choices` prevents this via the CLI, but
    # render_output() is public API and can be called directly).
    settings_command.render_output({'a': 1}, output_type='unknown')


@pytest.mark.parametrize('output_type', settings.Command.output_types)
@pytest.mark.parametrize('show_keys', [True, False])
def test_settings_command_arg(settings_command, output_type, show_keys):
    settings_command.handle('a', show_keys=show_keys, output_type=output_type)


@pytest.mark.parametrize('output_type', settings.Command.output_types)
@pytest.mark.parametrize('show_keys', [True, False])
def test_settings_command_data(settings_command, output_type, show_keys):
    # Test difficult data types
    data = dict(
        a=['spam"eggs"test,something'],
        b=['spam"eggs"'],
        c=['spam,eggs'],
        d='spam"eggs"test,something',
        e='spam"eggs"',
        f='spam,eggs',
        g=datetime.datetime.now(),
        h=datetime.timedelta(),
        i=datetime.date.today(),
    )
    settings_command.render_output(data, output_type, show_keys)


def test_admin_autogen_command():
    command = admin_autogen.Command()
    command.handle()
