from django.urls import path
from . import views

urlpatterns = [
    path('crawl/', views.crawl_links, name='crawl_links'),
]