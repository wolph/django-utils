from django.conf.urls import patterns, include, url
from django.contrib import admin
from django_utils import views

admin.autodiscover()

urlpatterns = patterns(
    '',
    url(r'^admin/', include(admin.site.urls)),
    url(r'^error_403', 'tests.views.error_403'),
    url(r'^error_500', 'tests.views.error_500'),
)

handler400 = views.error_400
handler403 = views.error_403
handler404 = views.error_404
handler500 = views.error_500

