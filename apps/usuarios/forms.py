"""Formularios para gestión de cuentas de odontólogos derivantes."""

from django import forms
from django.contrib.auth.password_validation import password_validators_help_text_html, validate_password
from django.db import transaction

from apps.core.enums import EstadoCuenta, RolUsuario
from apps.usuarios.models import Odontologo, Usuario


class OdontologoCreacionAdminForm(forms.Form):
    """Alta de odontólogo por el Administrador (estado HABILITADA)."""

    username = forms.CharField(label="Nombre de usuario", max_length=50)
    email = forms.EmailField(label="Correo electrónico")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password_confirm = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput)
    nombre = forms.CharField(label="Nombre", max_length=100)
    apellido = forms.CharField(label="Apellido", max_length=100)
    matricula = forms.CharField(label="Matrícula", max_length=50)
    telefono = forms.CharField(label="Teléfono", max_length=30, required=False)

    def __init__(self, *args, **kwargs):
        """Ayudas visuales compartidas por el alta administrativa y el autorregistro."""
        super().__init__(*args, **kwargs)
        autocomplete = {
            "nombre": "given-name", "apellido": "family-name",
            "email": "email", "telefono": "tel", "username": "username",
            "password": "new-password", "password_confirm": "new-password",
        }
        for name, value in autocomplete.items():
            self.fields[name].widget.attrs["autocomplete"] = value
        self.fields["telefono"].widget.attrs["inputmode"] = "tel"
        self.fields["password"].help_text = password_validators_help_text_html()

    def clean_username(self):
        username = self.cleaned_data["username"]
        if Usuario.objects.filter(username=username).exists():
            raise forms.ValidationError("Ya existe un usuario con ese nombre.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Ya existe un usuario con ese correo.")
        return email

    def clean_matricula(self):
        matricula = self.cleaned_data["matricula"].strip()
        if Odontologo.objects.filter(matricula=matricula).exists():
            raise forms.ValidationError("Ya existe un odontólogo con esa matrícula.")
        return matricula

    def clean_telefono(self):
        """Evita que dos cuentas compartan un teléfono definido como único."""
        telefono = self.cleaned_data.get("telefono", "").strip()
        if telefono and Usuario.objects.filter(telefono=telefono).exists():
            raise forms.ValidationError("Ya existe un usuario con ese teléfono.")
        return telefono

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Las contraseñas no coinciden.")

        if password:
            # Crear usuario temporal para validar similitud
            temp_user = Usuario(
                username=cleaned_data.get("username", ""),
                email=cleaned_data.get("email", ""),
            )
            try:
                validate_password(password, user=temp_user)
            except forms.ValidationError as e:
                self.add_error("password", e)

        return cleaned_data

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        usuario = Usuario.objects.create_user(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.HABILITADA,
            telefono=data.get("telefono") or None,
        )
        odontologo = Odontologo.objects.create(
            usuario=usuario,
            nombre=data["nombre"],
            apellido=data["apellido"],
            matricula=data["matricula"],
        )
        return odontologo


class OdontologoAutoregistroForm(OdontologoCreacionAdminForm):
    """Autorregistro público de odontólogo (estado PENDIENTE)."""

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        usuario = Usuario.objects.create_user(
            username=data["username"],
            email=data["email"],
            password=data["password"],
            rol=RolUsuario.ODONTOLOGO,
            estado=EstadoCuenta.PENDIENTE,
            telefono=data.get("telefono") or None,
        )
        odontologo = Odontologo.objects.create(
            usuario=usuario,
            nombre=data["nombre"],
            apellido=data["apellido"],
            matricula=data["matricula"],
        )
        return odontologo


class OdontologoEdicionForm(forms.Form):
    """Edición de perfil de odontólogo por el Administrador."""

    nombre = forms.CharField(label="Nombre", max_length=100)
    apellido = forms.CharField(label="Apellido", max_length=100)
    matricula = forms.CharField(label="Matrícula", max_length=50)
    email = forms.EmailField(label="Correo electrónico")
    telefono = forms.CharField(label="Teléfono", max_length=30, required=False)

    def __init__(self, *args, odontologo=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo presentación: ayuda al navegador sin cambiar las validaciones del perfil.
        autocomplete = {
            "nombre": "given-name", "apellido": "family-name",
            "email": "email", "telefono": "tel",
        }
        for name, value in autocomplete.items():
            self.fields[name].widget.attrs["autocomplete"] = value
        self.fields["telefono"].widget.attrs["inputmode"] = "tel"
        self.odontologo = odontologo
        if odontologo:
            self.fields["nombre"].initial = odontologo.nombre
            self.fields["apellido"].initial = odontologo.apellido
            self.fields["matricula"].initial = odontologo.matricula
            self.fields["email"].initial = odontologo.usuario.email
            self.fields["telefono"].initial = odontologo.usuario.telefono

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = Usuario.objects.filter(email=email)
        if self.odontologo:
            qs = qs.exclude(pk=self.odontologo.usuario_id)
        if qs.exists():
            raise forms.ValidationError("Ya existe un usuario con ese correo.")
        return email

    def clean_matricula(self):
        matricula = self.cleaned_data["matricula"].strip()
        qs = Odontologo.objects.filter(matricula=matricula)
        if self.odontologo:
            qs = qs.exclude(pk=self.odontologo.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un odontólogo con esa matrícula.")
        return matricula

    def clean_telefono(self):
        """Valida la unicidad sin considerar la cuenta que se está editando."""
        telefono = self.cleaned_data.get("telefono", "").strip()
        qs = Usuario.objects.filter(telefono=telefono)
        if self.odontologo:
            qs = qs.exclude(pk=self.odontologo.usuario_id)
        if telefono and qs.exists():
            raise forms.ValidationError("Ya existe un usuario con ese teléfono.")
        return telefono

    @transaction.atomic
    def save(self):
        data = self.cleaned_data
        odontologo = self.odontologo
        odontologo.nombre = data["nombre"]
        odontologo.apellido = data["apellido"]
        odontologo.matricula = data["matricula"]
        odontologo.save(update_fields=["nombre", "apellido", "matricula"])

        usuario = odontologo.usuario
        usuario.email = data["email"]
        usuario.telefono = data.get("telefono") or None
        usuario.save(update_fields=["email", "telefono", "updated_at"])

        return odontologo
