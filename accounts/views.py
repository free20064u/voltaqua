from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserCreationForm, ProfileForm


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful! Please log in.')
            return redirect('accounts:login')
    else:
        form = UserCreationForm()
    
    context = {
        'form': form,
        'title': 'Register — Voltaqua'
    }
    return render(request, 'register.html', context)

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
    return render(request, 'profile.html', {'form': form, 'title': 'My Profile'})