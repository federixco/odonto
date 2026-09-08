"""Formularios para la ficha clínica y el acceso opcional de pacientes."""

from django import forms
from django.contrib.auth.password_validation import (
    password_validators_help_text_html,
    validate_password,
)
from django.db import transaction
from django.db.models import Q

from apps.core.enums import EstadoCuenta, RolUsuario
from apps.usuarios.models import Usuario

from .models import Paciente


class PacienteForm(forms.ModelForm):
    """Alta y edición de la ficha clínica desde el centro."""

    class Meta:
        model = Paciente
        fields = ("nombre", "apellido", "dni", "fecha_nacimiento", "obra_social", "usuario")
        widgets = {"fecha_nacimiento": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, paciente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.paciente = paciente or self.instance
        self.fields["usuario"].empty_label = "Sin cuenta de acceso por ahora"
        self.fields["usuario"].help_text = (
            "Solo se pueden vincular cuentas de paciente que todavía no estén asociadas a otra ficha."
        )
        self.fields["fecha_nacimiento"].widget.attrs["autocomplete"] = "bday"
        for field_name, autocomplete in {
            "nombre": "given-name",
            "apellido": "family-name",
            "dni": "off",
            "obra_social": "off",
        }.items():
            self.fields[field_name].widget.attrs["autocomplete"] = autocomplete

        disponibles = Usuario.objects.filter(rol=RolUsuario.PACIENTE)
        if self.paciente and self.paciente.pk:
            disponibles = disponibles.filter(
                Q(paciente__isnull=True) | Q(pk=self.paciente.usuario_id)
            )
        else:
            disponibles = disponibles.filter(paciente__isnull=True)
        self.fields["usuario"].queryset = disponibles.order_by("username")

    def clean_dni(self):
        dni = self.cleaned_data["dni"].strip()
        if not dni:
            raise forms.ValidationError("Ingresá el DNI del paciente.")
        return dni

    def clean_usuario(self):
        usuario = self.cleaned_data.get("usuario")
        if usuario is None:
            return None
        if usuario.rol != RolUsuario.PACIENTE:
            raise forms.ValidationError("Solo puede vincularse una cuenta con rol Paciente.")
        perfil_existente = getattr(usuario, "paciente", None)
        if perfil_existente and perfil_existente.pk != self.paciente.pk:
            raise forms.ValidationError("Esta cuenta ya está vinculada a otra ficha clínica.")
        return usuario


class CrearAccesoPacienteForm(forms.Form):
    """Crea una cuenta habilitada y la vincula a una ficha ya existente."""

    username = forms.CharField(label="Nombre de usuario", max_length=50)
    email = forms.EmailField(label="Correo electrónico", required=False)
    telefono = forms.CharField(label="Teléfono", max_length=30, required=False)
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password_confirm = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput)

    def __init__(self, *args, paciente, **kwargs):
        super().__init__(*args, **kwargs)
        self.paciente = paciente
        for field_name, autocomplete in {
            "username": "username",
            "email": "email",
            "telefono": "tel",
            "password": "new-password",
            "password_confirm": "new-password",
        }.items():
            self.fields[field_name].widget.attrs["autocomplete"] = autocomplete
        self.fields["telefono"].widget.attrs["inputmode"] = "tel"
        self.fields["password"].help_text = password_validators_help_text_html()

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if Usuario.objects.filter(username=username).exists():
            raise forms.ValidationError("Ya existe un usuario con ese nombre.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if email and Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario con ese correo.")
        return email

    def clean_telefono(self):
        telefono = self.cleaned_data.get("telefono", "").strip()
        if telefono and Usuario.objects.filter(telefono=telefono).exists():
            raise forms.ValidationError("Ya existe un usuario con ese teléfono.")
        return telefono

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        telefono = cleaned_data.get("telefono")
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if not email and not telefono:
            self.add_error("email", "Ingresá un correo electrónico o un teléfono.")
        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Las contraseñas no coinciden.")
        if password:
            usuario_temporal = Usuario(
                username=cleaned_data.get("username", ""), email=email or None, telefono=telefono or None,
            )
            try:
                validate_password(password, user=usuario_temporal)
            except forms.ValidationError as error:
                self.add_error("password", error)
        return cleaned_data

    @transaction.atomic
    def save(self):
        if self.paciente.usuario_id:
            raise ValueError("La ficha ya posee una cuenta vinculada.")
        data = self.cleaned_data
        usuario = Usuario.objects.create_user(
            username=data["username"],
            email=data["email"] or None,
            telefono=data["telefono"] or None,
            password=data["password"],
            rol=RolUsuario.PACIENTE,
            estado=EstadoCuenta.HABILITADA,
        )
        self.paciente.usuario = usuario
        self.paciente.save(update_fields=["usuario"])
        return usuario
