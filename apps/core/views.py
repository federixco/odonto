"""Páginas informativas públicas: no consultan estudios ni requieren una cuenta."""

from django.shortcuts import render

from .privacy import PRIVACY_LAST_UPDATED


def landing(request):
    """Presenta D.O.C.; el acceso clínico sigue en las vistas protegidas existentes."""
    return render(request, "core/landing.html")


def privacy_policy(request):
    """Documento institucional público; no consulta datos de personas ni estudios."""
    return render(request, "core/privacy.html", {
        "policy_updated": PRIVACY_LAST_UPDATED,
    })
