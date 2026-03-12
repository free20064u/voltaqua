from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login, views as auth_views
from channels.layers import get_channel_layer
from .forms import UserCreationForm, ProfileForm, CustomAuthenticationForm
from .models import User, Notification


class CustomLoginView(auth_views.LoginView):
    authentication_form = CustomAuthenticationForm
    template_name = 'accounts/login.html'

    def form_valid(self, form):
        remember_me = form.cleaned_data.get('remember_me')
        if not remember_me:
            # Set session expiry to 0 seconds. So it will automatically expire when the browser is closed.
            self.request.session.set_expiry(0)
        return super().form_valid(form)


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)

            # --- Create and Send Notifications ---

            # 1. Create notifications in the database
            admin_roles = ['block_admin', 'superuser']
            admins = User.objects.filter(role__in=admin_roles)
            admin_message = f'A new user has just registered: {user.first_name or user.email}'
            for admin in admins:
                Notification.objects.create(recipient=admin, message=admin_message)

            welcome_message = f'Welcome to Voltaqua, {user.first_name}!'
            welcome_notification = Notification.objects.create(recipient=user, message=welcome_message)

            # 2. Send real-time notifications via Channels
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()

            # Notify admins
            async_to_sync(channel_layer.group_send)(
                'block_admins',
                {
                    'type': 'broadcast_message',
                    'message': {
                        'text': admin_message
                    }
                }
            )

            # Send a private welcome message to the new user
            async_to_sync(channel_layer.group_send)(
                f'user_{user.id}',
                {
                    'type': 'broadcast_message',
                    'message': {
                        'id': welcome_notification.id,
                        'text': welcome_notification.message
                    }
                }
            )

            messages.success(request, 'Registration successful! Welcome.')
            return redirect('water:home')
    else:
        form = UserCreationForm()
    
    context = {
        'form': form,
        'title': 'Create an Account'
    }
    return render(request, 'accounts/register.html', context)


@login_required
def notification_list(request):
    notifications = request.user.notifications.all()
    context = {'notifications': notifications, 'title': 'My Notifications'}
    return render(request, 'accounts/notification_list.html', context)

@login_required
def mark_notifications_read(request):
    if request.method == 'POST':
        request.user.notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
    return redirect('accounts:notification_list')

@login_required
def profile(request):
    user = request.user
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=user)
    return render(request, 'accounts/profile.html', {'form': form, 'title': 'My Profile'})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect('base:home')