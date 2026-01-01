from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.auth.models import User
import qrcode
from io import BytesIO
import base64
import pdfkit
from django.utils import timezone
from django.db.models import Count, Q
from django.db import models
from django.contrib.auth.decorators import user_passes_test
import json
import os
from django.http import JsonResponse
from .models import Clinic, PatientRecord
from .forms import ClinicRegistrationForm, PatientRecordForm


def is_superuser(user):
    return user.is_superuser

superuser_required = user_passes_test(is_superuser, login_url='login')


# Public Home (if you have one — optional)
def home_view(request):
    if request.user.is_authenticated:
        return redirect('records:clinic_dashboard')
    return render(request, 'home.html', {
        'title': 'LifeQR - Emergency Medical Records for Nigeria'
    })



@superuser_required
def clinic_suggestions(request):
    query = request.GET.get('q', '')
    clinics = Clinic.objects.filter(
        models.Q(name__icontains=query) | models.Q(phone__icontains=query) | models.Q(state__icontains=query)
    ).values('id', 'name', 'phone', 'state')[:10]

    return JsonResponse(list(clinics), safe=False)


# Superuser Dashboard
@superuser_required
@login_required
def superuser_dashboard(request):
    total_clinics = Clinic.objects.count()
    approved_clinics = Clinic.objects.filter(is_approved=True).count()
    pending_clinics = Clinic.objects.filter(is_approved=False).count()
    locked_clinics = Clinic.objects.filter(is_locked=True).count()
    total_records = PatientRecord.objects.filter(is_active=True).count()

    state_data = Clinic.objects.values('state').annotate(
        clinic_count=Count('id'),
        record_count=Count('patientrecord__id', filter=Q(patientrecord__is_active=True))
    ).order_by('state')

    states = [item['state'] for item in state_data]
    clinic_counts = [item['clinic_count'] for item in state_data]
    record_counts = [item['record_count'] for item in state_data]

    recent_pending = Clinic.objects.filter(is_approved=False).order_by('-date_joined')[:10]

    last_week_records = PatientRecord.objects.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=7),
        is_active=True
    ).count()

    context = {
        'total_clinics': total_clinics,
        'approved_clinics': approved_clinics,
        'pending_clinics': pending_clinics,
        'locked_clinics': locked_clinics,
        'total_records': total_records,
        'last_week_records': last_week_records,
        'recent_pending': recent_pending,
        'states_json': json.dumps(states),
        'clinic_counts_json': json.dumps(clinic_counts),
        'record_counts_json': json.dumps(record_counts),
    }
    return render(request, 'superuser/dashboard.html', context)


# Clinic Registration
def clinic_register(request):
    if request.method == 'POST':
        form = ClinicRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Clinic.objects.create(
                user=user,
                name=form.cleaned_data['clinic_name'],
                address=form.cleaned_data['address'],
                state=form.cleaned_data['state'],
                phone=form.cleaned_data['phone']
            )
            messages.success(request, 'Registration successful! Waiting for superuser approval.')
            return redirect('login')
    else:
        form = ClinicRegistrationForm()
    return render(request, 'registration/clinic_register.html', {'form': form})


@login_required
def patient_detail(request, pk):
    clinic = get_object_or_404(Clinic, user=request.user)
    record = get_object_or_404(PatientRecord, pk=pk, clinic=clinic, is_active=True)

    context = {
        'record': record,
        'title': f"Patient Details: {record.full_name}"
    }
    return render(request, 'patient/detail.html', context)


# Clinic Dashboard
@login_required
def clinic_dashboard(request):
    if request.user.is_superuser:
        return redirect('records:superuser_dashboard')

    clinic = get_object_or_404(Clinic, user=request.user)

    if not clinic.is_approved:
        return render(request, 'clinic/waiting_approval.html')

    if clinic.is_locked:
        return render(request, 'clinic/locked.html')

    recent_records = PatientRecord.objects.filter(clinic=clinic, is_active=True).order_by('-updated_at')[:10]

    context = {
        'clinic': clinic,
        'recent_records': recent_records,
        'total_records': PatientRecord.objects.filter(clinic=clinic, is_active=True).count()
    }
    return render(request, 'clinic/dashboard.html', context)


# Create Patient Record
@login_required
def patient_create(request):
    clinic = get_object_or_404(Clinic, user=request.user)
    if not clinic.is_approved or clinic.is_locked:
        return redirect('records:clinic_dashboard')

    if request.method == 'POST':
        form = PatientRecordForm(request.POST, request.FILES)
        if form.is_valid():
            record = form.save(commit=False)
            record.clinic = clinic
            record.save()
            messages.success(request, f'Record created for {record.full_name}. Print the new QR card.')
            return redirect('records:printable_card', unique_id=record.unique_id)
    else:
        form = PatientRecordForm()

    return render(request, 'patient/form.html', {'form': form, 'title': 'Create New Record'})


# Update Patient Record
@login_required
def patient_update(request, pk):
    clinic = get_object_or_404(Clinic, user=request.user)
    if not clinic.is_approved or clinic.is_locked:
        return redirect('records:clinic_dashboard')

    old_record = get_object_or_404(PatientRecord, pk=pk, clinic=clinic)

    if request.method == 'POST':
        form = PatientRecordForm(request.POST, request.FILES, instance=old_record)
        if form.is_valid():
            new_record = form.save(commit=False)
            new_record.pk = None
            new_record.unique_id = None
            new_record.clinic = clinic
            new_record.save()
            new_record.deactivate_old_versions()
            messages.success(request, f'Updated record for {new_record.full_name}. Old card is now invalid.')
            return redirect('records:printable_card', unique_id=new_record.unique_id)
    else:
        form = PatientRecordForm(instance=old_record)

    return render(request, 'patient/form.html', {
        'form': form,
        'title': 'Update Record (New QR will be issued)',
        'old_record': old_record
    })


# Search Patient
@login_required
def patient_search(request):
    clinic = get_object_or_404(Clinic, user=request.user)
    if not clinic.is_approved or clinic.is_locked:
        return redirect('records:clinic_dashboard')

    results = []
    if 'q' in request.GET:
        query = request.GET['q']
        results = PatientRecord.objects.filter(
            clinic=clinic,
            is_active=True,
            full_name__icontains=query
        ) | PatientRecord.objects.filter(
            clinic=clinic,
            is_active=True,
            phone__icontains=query
        )

    return render(request, 'patient/search.html', {'results': results})


# Public Emergency View
def emergency_view(request, unique_id):
    record = get_object_or_404(PatientRecord, unique_id=unique_id, is_active=True)
    context = {
        'record': record,
        'current_date': timezone.now().strftime("%B %d, %Y")
    }
    return render(request, 'emergency/view.html', context)


# Printable Card (PDF)
@login_required
def printable_card(request, unique_id):
    record = get_object_or_404(PatientRecord, unique_id=unique_id, is_active=True)
    clinic = record.clinic

    if clinic.user != request.user:
        messages.error(request, "Access denied. You can only print records from your clinic.")
        return redirect('records:clinic_dashboard')

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr_url = request.build_absolute_uri(f'/qr/{unique_id}/')
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_data_uri = "data:image/png;base64," + base64.b64encode(qr_buffer.getvalue()).decode()

    html_string = render_to_string('printable/card.html', {
        'record': record,
        'qr_data_uri': qr_data_uri,
    })

    # Try common wkhtmltopdf paths on Windows, then fall back to auto-detect
    possible_paths = [
        r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe',
        r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe',
        r'C:\wkhtmltopdf\bin\wkhtmltopdf.exe',
    ]

    config = None
    for path in possible_paths:
        if os.path.exists(path):
            config = pdfkit.configuration(wkhtmltopdf=path)
            break

    # If not found in common paths, let pdfkit try to find it (if in PATH)
    pdf = pdfkit.from_string(
        html_string,
        False,
        configuration=config,  # Will be None if not found — pdfkit will try auto-detect
        options={
            'page-size': 'A4',
            'margin-top': '0.5in',
            'margin-right': '0.5in',
            'margin-bottom': '0.5in',
            'margin-left': '0.5in',
            'encoding': "UTF-8",
            'no-outline': None,
            'quiet': ''
        }
    )

    response = HttpResponse(pdf, content_type='application/pdf')
    filename = f"{record.full_name.replace(' ', '_')}_LifeQR_Card.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response

@login_required
def patient_suggestions(request):
    clinic = get_object_or_404(Clinic, user=request.user)
    query = request.GET.get('q', '')
    patients = PatientRecord.objects.filter(
        clinic=clinic,
        is_active=True
    ).filter(
        models.Q(full_name__icontains=query) | models.Q(phone__icontains=query)
    ).values('id', 'full_name', 'phone')[:10]  # Limit to 10 suggestions

    return JsonResponse(list(patients), safe=False)