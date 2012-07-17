import re
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

LIST_FILTER_TRESHOLD = 25
RAW_ID_THRESHOLD = 100

class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        self.model_res = []

        installed_apps = dict((a.__name__.rsplit('.', 1)[0], a)
            for a in models.get_apps())

        if not args:
            print >>sys.stderr, 'This command requires a (list of) app(s)'
            for app in sorted(installed_apps):
                print >>sys.stderr, '\t%r' % app
            return

        args = list(args)
        app = installed_apps.get(args.pop(0))
        for arg in args:
            self.model_res.append(re.compile(arg, re.IGNORECASE))

        self.handle_app(app, **kwargs)

    def handle_app(self, app, **options):
        models_dict = {}

        for model in get_models(app):
            name = model.__name__
            field_names = []

            if self.model_res:
                for model_re in self.model_res:
                    if model_re.search(name):
                        break
                else:
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
                        related_count = (field.related.parent_model.objects
                            .all()
                            [:max(LIST_FILTER_TRESHOLD, RAW_ID_THRESHOLD)]
                            .count()
                        )

                        if related_count >= RAW_ID_THRESHOLD:
                            model_dict['raw_id_fields'].append(field.name)

                        if related_count <= LIST_FILTER_TRESHOLD:
                            model_dict['list_filter'].append(field.name)
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

