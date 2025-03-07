from django.urls import path
from . import views

urlpatterns = [
    path('crawl/', views.crawl_website_view, name='crawl_website'),
]