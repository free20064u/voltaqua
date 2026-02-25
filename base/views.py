from django.shortcuts import render


def home(request):
    context = {
        'title': 'Water Distribution Management System'
    }
    return render(request, 'home.html', context)
