from django.urls import path
from . import views

app_name = 'water'

urlpatterns = [
    path('', views.water, name='water'),
]
