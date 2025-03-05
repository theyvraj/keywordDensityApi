from django.urls import path
from . import views

urlpatterns = [
    path('process-url/', views.process_url, name='process_url'),
    path('process-multiple-urls/', views.process_multiple_urls, name='process_multiple_urls'),
]