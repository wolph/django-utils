from django import urls
from django.contrib import admin

from django_utils import views
from tests import views as test_views

admin.autodiscover()

urlpatterns = [
    urls.re_path(r'^admin/', admin.site.urls),
    urls.re_path(r'^error_403', test_views.error_403),
    urls.re_path(r'^error_500', test_views.error_500),
]

handler403 = views.error_403
handler404 = views.error_404
handler500 = views.error_500
