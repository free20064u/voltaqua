from django.shortcuts import render


def water(request):
    context = {
        'title': 'Water — Voltaqua'
    }
    return render(request, 'water.html', context)
