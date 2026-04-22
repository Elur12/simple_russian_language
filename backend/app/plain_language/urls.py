from django.urls import path

from .views import AnalyzeView, FetchUrlView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("analyze/", AnalyzeView.as_view(), name="analyze"),
    path("fetch-url/", FetchUrlView.as_view(), name="fetch-url"),
]
