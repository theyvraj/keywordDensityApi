from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('kdcApi.urls')),  # Include the kdcApi URLs with the 'api/' prefix
]