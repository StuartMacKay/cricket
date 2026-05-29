from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from core.views import IndexView, RobotsView
from api.api import api

urlpatterns = [
    path("", IndexView.as_view(), name="index"),
]


urlpatterns += [
    # Change the path to the Django Admin to something non-standard.
    path(settings.ADMIN_PATH, admin.site.urls),  # type: ignore
]

urlpatterns += [
    path("robots.txt", RobotsView.as_view()),
    path("watchman/", include("watchman.urls")),
    path("audits/", include("lighthouse.urls")),
    path("api/", api.urls),
]

if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DJANGO_ENV == "development" and settings.DEBUG:
    from django.views import defaults

    urlpatterns += [
        path(
            "403/",
            defaults.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            defaults.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path(
            "500/",
            defaults.server_error,
        ),
    ]

    # Add a view that raises and error to test sentry in development
    def trigger_error(request):
        raise Exception("Verify Sentry is configured and working")

    urlpatterns += [
        path("__debug__/sentry/", trigger_error),
    ]

    import debug_toolbar  # type: ignore

    urlpatterns += [
        path("__debug__/toolbar/", include(debug_toolbar.urls)),  # type: ignore
    ]
