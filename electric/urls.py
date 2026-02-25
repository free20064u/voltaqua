from django.urls import path
from . import views

app_name = 'electric'

urlpatterns = [
    path('', views.electric, name='electric'),
]
