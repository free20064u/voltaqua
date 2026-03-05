from django.urls import path
from . import views

app_name = 'water'

urlpatterns = [
    path('', views.home_dashboard, name='home'),
    path('block/<int:site_id>/', views.block_dashboard, name='block-dashboard'),
    path('apartment/<int:apartment_id>/', views.apartment_dashboard, name='apartment-dashboard'),
    path('apartment/<int:apartment_id>/edit/', views.edit_apartment, name='edit-apartment'),
    path('block/<int:site_id>/enter-bill/', views.enter_bill, name='enter-bill'),
    path('sites/', views.sites_list, name='sites-list'),
    path('apartments/', views.apartments_list, name='apartments-list'),
    path('meters/', views.meters_list, name='meters-list'),
    path('admins/', views.admins_list, name='admins-list'),
]
