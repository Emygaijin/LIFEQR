from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Clinic, PatientRecord, NIGERIA_STATES
from django_countries.fields import CountryField
from django_countries.widgets import CountrySelectWidget


class ClinicRegistrationForm(UserCreationForm):
    clinic_name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter clinic name'})
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Full clinic address'}),
        required=True
    )
    country = CountryField(blank_label="Select country").formfield(
        widget=CountrySelectWidget(attrs={'class': 'form-control'})
    )
    state = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State / Province / Region'}),
        help_text="e.g., Lagos, California, Greater London"
    )
    phone = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+234... or country code'})
    )

    class Meta:
        model = User
        fields = ('username', 'password1', 'password2', 'clinic_name', 'address', 'country', 'state', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Bootstrap classes to password fields
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Choose username'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Create password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm password'})

        # Remove default help text
        self.fields['username'].help_text = None
        self.fields['password2'].help_text = None

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            Clinic.objects.create(
                user=user,
                name=self.cleaned_data['clinic_name'],
                address=self.cleaned_data['address'],
                country=self.cleaned_data['country'],
                state=self.cleaned_data['state'],
                phone=self.cleaned_data['phone']
            )
        return user
class PatientRecordForm(forms.ModelForm):
    class Meta:
        model = PatientRecord
        fields = [
            'full_name', 'phone', 'address', 'photo',
            'emergency_contact_name', 'emergency_contact_phone',
            'blood_group', 'allergies', 'current_medications','insurance_name', 'insurance_phone', 'chronic_conditions', 'other_notes'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'chronic_conditions': forms.Textarea(attrs={'rows': 2}),
            'other_notes': forms.Textarea(attrs={'rows': 3}),
            'current_medications': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})