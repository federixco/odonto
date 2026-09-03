"""Páginas informativas públicas: no consultan estudios ni requieren una cuenta."""

from django.shortcuts import render


def landing(request):
    """Presenta D.O.C.; el acceso clínico sigue en las vistas protegidas existentes."""
    return render(request, "core/landing.html")
