from django.urls import path
from . import views

app_name = 'water'

urlpatterns = [
    path('', views.home_dashboard, name='home'),
    path('dashboard/', views.home_dashboard, name='dashboard'),
    path('block/<int:site_id>/', views.block_dashboard, name='block-dashboard'),
    path('apartment/<int:apartment_id>/', views.apartment_dashboard, name='apartment-dashboard'),
    path('apartment/<int:apartment_id>/edit/', views.edit_apartment, name='edit-apartment'),
    path('apartment/<int:apartment_id>/bills/', views.apartment_bill_list, name='apartment-bill-list'),
    path('apartment/<int:apartment_id>/payments/', views.apartment_payment_history, name='apartment-payment-history'),
    path('block/<int:site_id>/enter-bill/', views.enter_bill, name='enter-bill'),
    path('bill/<int:bill_id>/pay/', views.record_payment, name='record-payment'),
    path('sites/', views.sites_list, name='sites-list'),
    path('apartments/', views.apartments_list, name='apartments-list'),
    path('meters/', views.meters_list, name='meters-list'),
    path('admins/', views.admins_list, name='admins-list'),
    path('setup/block/', views.create_site, name='create-site'),
    path('setup/meter/', views.create_meter, name='create-meter'),
    path('setup/join/', views.join_site, name='join-site'),
]
