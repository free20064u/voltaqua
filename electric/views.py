from django.shortcuts import render


def electric(request):
    context = {
        'title': 'Electric — Voltaqua'
    }
    return render(request, 'electric.html', context)
