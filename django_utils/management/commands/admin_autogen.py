import sys
from django.core.management.base import BaseCommand
from django.db.models.loading import get_models
from django.db import models

LIST_FILTER = (
    models.DateField,
    models.DateTimeField,
    models.ForeignKey,
    models.BooleanField,
)

SEARCH_FIELD = (
    'name',
    'slug',
)

DATE_HIERARCHY = (
    'created_at',
    'updated_at',
    'joined_at',
)

PREPOPULATED_FIELDS = {
    'slug': ('name',)
}


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        apps = []
        self.models = []

        installed_apps = dict((a.__name__.rsplit('.', 1)[0], a)
            for a in models.get_apps())

        for arg in args:
            app = installed_apps.get(arg)
            if app:
                apps.append(app)
            else:
                self.models.append(arg.lower())

        for app in apps:
            self.handle_app(app, **kwargs)

        if not args:
            print >>sys.stderr, 'This command requires a (list of) app(s)'
            for app in sorted(installed_apps):
                print >>sys.stderr, '\t%r' % app

    def handle_app(self, app, **options):
        models_dict = {}

        for model in get_models(app):
            name = model.__name__
            field_names = []

            if self.models and name.lower() not in self.models:
                continue

            models_dict[name] = model_dict = {
                'list_display': [],
                'list_filter': [],
                'raw_id_fields': [],
                'search_fields': [],
                'prepopulated_fields': {},
                'date_hierarchy': None,
            }

            parent_fields = model._meta.parents.values()

            for field in model._meta.local_many_to_many:
                if(field.related.parent_model.objects.all()[:100].count()
                        <= 100):
                    model_dict['raw_id_fields'].append(field.name)

            for field in model._meta.fields:
                if field in parent_fields:
                    continue

                field_names.append(field.name)
                model_dict['list_display'].append(field.name)

                if isinstance(field, LIST_FILTER):
                    if isinstance(field, models.ForeignKey):
                        if(field.related.parent_model.objects.all()[:100]
                                .count() <= 100):
                            model_dict['list_filter'].append(field.name)
                        else:
                            model_dict['raw_id_fields'].append(field.name)
                    else:
                        model_dict['list_filter'].append(field.name)

                if field.name in SEARCH_FIELD:
                    model_dict['search_fields'].append(field.name)

            for field_name in DATE_HIERARCHY:
                if field_name in field_names \
                        and not model_dict['date_hierarchy']:
                    model_dict['date_hierarchy'] = field_name

            for k, vs in sorted(PREPOPULATED_FIELDS.iteritems()):
                if field_name in field_names \
                        and not model_dict['date_hierarchy']:
                    model_dict['date_hierarchy'] = field_name

                if k in field_names:
                    incomplete = False
                    for v in vs:
                        if v not in field_names:
                            incomplete = True
                            break

                    if not incomplete:
                        model_dict['prepopulated_fields'][k] = vs

        print 'import models'
        print 'from django.contrib import admin'
        print

        for name, model in sorted(models_dict.iteritems()):
            print '\n\nclass %sAdmin(admin.ModelAdmin):' % name
            for k, v in sorted(model.iteritems()):
                if v:
                    if isinstance(v, (list, set)):
                        v = tuple(v)

                    row = '    %s = %r' % (k, v)
                    row_parts = []
                    while len(row) > 78:
                        pos = row.rfind(' ', 0, 78)
                        row_parts.append(row[:pos])
                        row = '        ' + row[pos:]

                    row_parts.append(row)

                    print '\n'.join(row_parts)

        print '\n\n'
        for name in sorted(models_dict):
            print 'admin.site.register(models.%s, %sAdmin)' % (name, name)

