from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from . import views
from .forms import CustomAuthenticationForm

app_name = 'accounts'

urlpatterns = [
    # NOTE: You should move your existing login, logout, and register
    # URL patterns into this file to keep your accounts app self-contained.
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),

    # Password reset flow
    path('password_reset/',
         auth_views.PasswordResetView.as_view(
             template_name="accounts/password_reset_form.html",
             email_template_name="accounts/password_reset_email.html",
             subject_template_name="accounts/password_reset_subject.txt",
             success_url=reverse_lazy('accounts:password_reset_done')
         ),
         name='password_reset'),
    path('password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name="accounts/password_reset_done.html"
         ),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name="accounts/password_reset_confirm.html",
             success_url=reverse_lazy('accounts:password_reset_complete')
         ),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name="accounts/password_reset_complete.html"
         ),
         name='password_reset_complete'),
]