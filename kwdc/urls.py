from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
     path('inlinkapi/', include('inLinkApi.urls')),  # Include the inLinkApi URLs with the 'inlinkapi/' prefix
    path('kwdcapi/', include('kdcApi.urls')),  # Include the kdcApi URLs with the 'api/' prefix
]