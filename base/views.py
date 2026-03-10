from django.shortcuts import render


def home(request):
    context = {
        'title': 'Utility Bill Distribution Management System'
    }
    return render(request, 'base/home.html', context)


def about(request):
    context = {
        'title': 'About — Voltaqua'
    }
    return render(request, 'base/about.html', context)
