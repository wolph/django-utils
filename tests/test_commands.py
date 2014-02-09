from django_utils.management import commands


def test_settings_command():
    command = commands.settings.Command()
    command.handle()
    command.handle('debug')


def test_admin_autogen_command():
    import sys
    stderr = sys.stderr
    stdout = sys.stdout
    sys.stderr = stdout

    commands.admin_autogen.DATE_HIERARCHY += ('date_joined',)
    commands.admin_autogen.PREPOPULATED_FIELDS['username'] = 'first_name',
    commands.admin_autogen.PREPOPULATED_FIELDS['last_name'] = 'full_name',
    commands.admin_autogen.LIST_FILTER_THRESHOLD = 0
    commands.admin_autogen.RAW_ID_THRESHOLD = 0

    command = commands.admin_autogen.Command()
    command.handle()
    command.handle('tests.test_app')
    command.handle('django.contrib.auth')
    command.handle('django.contrib.auth', 'user')

    commands.admin_autogen.LIST_FILTER_THRESHOLD = 250
    commands.admin_autogen.RAW_ID_THRESHOLD = 250
    command.handle('tests.test_app')
    command.handle('django.contrib.auth')
    command.handle('django.contrib.auth', 'user')

    sys.stderr = stderr


