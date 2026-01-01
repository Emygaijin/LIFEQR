from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Clinic, PatientRecord, NIGERIA_STATES

class ClinicRegistrationForm(UserCreationForm):
    clinic_name = forms.CharField(max_length=200, required=True)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=True)
    state = forms.ChoiceField(choices=NIGERIA_STATES, required=True)
    phone = forms.CharField(max_length=15, required=True)

    class Meta:
        model = User
        fields = ('username', 'password1', 'password2', 'clinic_name', 'address', 'state', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].help_text = None
        self.fields['password2'].help_text = None
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class PatientRecordForm(forms.ModelForm):
    class Meta:
        model = PatientRecord
        fields = [
            'full_name', 'phone', 'address', 'photo',
            'emergency_contact_name', 'emergency_contact_phone',
            'blood_group', 'allergies', 'insurance_name', 'insurance_phone', 'chronic_conditions', 'other_notes'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'chronic_conditions': forms.Textarea(attrs={'rows': 2}),
            'other_notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})