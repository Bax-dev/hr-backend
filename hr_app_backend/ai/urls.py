from django.urls import path

from .views import assistant_view
app_name = 'ai'

urlpatterns = [
    path('assistant/', assistant_view, name='assistant'),
]
