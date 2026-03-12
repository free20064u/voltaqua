from django.urls import path
from . import views

app_name = 'base'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('contact/', views.contact_view, name='contact'),
    path('contact/success/', views.contact_success_view, name='contact_success'),
    path('terms/', views.TermsView.as_view(), name='terms'),
    path('privacy/', views.PrivacyView.as_view(), name='privacy'),
]