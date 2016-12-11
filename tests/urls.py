from django.conf.urls import include, url
from django.contrib import admin
from django_utils import views

from tests import views as test_views

admin.autodiscover()

urlpatterns = [
    url(r'^admin/', include(admin.site.urls)),
    url(r'^error_403', test_views.error_403),
    url(r'^error_500', test_views.error_500),
]

handler403 = views.error_403
handler404 = views.error_404
handler500 = views.error_500
