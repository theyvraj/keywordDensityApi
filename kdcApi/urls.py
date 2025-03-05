from django.urls import path
from .views import URLProcessingView

urlpatterns = [
    path('process-url/', URLProcessingView.as_view(), name='process-url'),
]