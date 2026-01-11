from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth import authenticate
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.auth.models import User
import qrcode
from io import BytesIO
from datetime import datetime
from django.db import transaction
import uuid
from django_countries import countries
import base64
import pdfkit
from django.utils import timezone
from django.db.models import Count, Q
from django.db import models
from django.contrib.auth.decorators import user_passes_test
import json
import os
from django.http import JsonResponse
from .models import Clinic, PatientRecord, AdCampaign
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
    # Overall stats
    total_clinics = Clinic.objects.count()
    approved_clinics = Clinic.objects.filter(is_approved=True).count()
    pending_clinics = Clinic.objects.filter(is_approved=False).count()
    locked_clinics = Clinic.objects.filter(is_locked=True).count()
    total_records = PatientRecord.objects.filter(is_active=True).count()

    # Ad campaigns for revenue management
    ad_campaigns = AdCampaign.objects.order_by('-start_date')

    # === Clinics per Country (using django-countries) ===
    country_stats_raw = Clinic.objects.exclude(country__isnull=True)\
        .values('country')\
        .annotate(count=Count('id'))\
        .order_by('-count')

    # Convert country code to name
    country_stats = []
    for stat in country_stats_raw:
        country_code = stat['country']
        country_name = dict(countries).get(country_code, 'Unknown')
        country_stats.append({
            'country_code': country_code,
            'country_name': country_name,
            'count': stat['count']
        })

    total_countries = len(country_stats)

    # === Clinics per State/Region (text field) ===
    state_stats = Clinic.objects.exclude(state__exact='')\
        .values('state')\
        .annotate(count=Count('id'))\
        .order_by('-count')[:20]

    # Chart data - Top 10 countries
    top_countries = country_stats[:10]
    country_names = [c['country_name'] for c in top_countries]
    country_counts = [c['count'] for c in top_countries]

    # Recent pending clinics
    recent_pending = Clinic.objects.filter(is_approved=False).order_by('-date_joined')[:10]

    # Recent activity (last 7 days)
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

        # Global stats
        'country_stats': country_stats,
        'total_countries': total_countries,
        'state_stats': state_stats,

        # Chart data
        'country_names_json': json.dumps(country_names),
        'country_counts_json': json.dumps(country_counts),

        # Ad campaigns for revenue
        'ad_campaigns': ad_campaigns,
    }
    return render(request, 'superuser/dashboard.html', context)


# Clinic Registration
def clinic_register(request):
    if request.method == 'POST':
        form = ClinicRegistrationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            if User.objects.filter(username=username).exists():
                messages.error(request, f"The username '{username}' is already taken. Please choose a different one.")
                return render(request, 'registration/clinic_register.html', {'form': form})

            # Save the user and create clinic
            user = form.save()
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

@login_required
def clinic_dashboard(request):
    if request.user.is_superuser:
        return redirect('records:superuser_dashboard')

    clinic = get_object_or_404(Clinic, user=request.user)

    if not clinic.is_approved:
        return render(request, 'clinic/waiting_approval.html')

    if clinic.is_locked:
        return render(request, 'clinic/locked.html')

    # Recent records
    recent_records = PatientRecord.objects.filter(
        clinic=clinic, is_active=True
    ).order_by('-updated_at')[:10]

    # Timezone-aware now
    now = timezone.now()

    # === DEBUG: Clinic info ===
    print("\n=== DEBUG: Clinic Dashboard Load ===")
    print(f"Clinic: {clinic.name}")
    print(f"Country code: {clinic.country.code if clinic.country else 'None'}")
    print(f"State: {clinic.state or 'None'}")
    print(f"Current time (aware): {now}")

    # === Fetch ALL matching active video ads ===
    video_ads = []
    video_candidates = AdCampaign.objects.filter(
        ad_type='video',
        is_active=True,
        start_date__lte=now,
        end_date__gte=now
    )

    print(f"DEBUG: Found {video_candidates.count()} active video candidates")
    for ad in video_candidates:
        print(f"  - Ad: '{ad.title}' | Active: {ad.is_active} | Dates: {ad.start_date} to {ad.end_date}")
        print(f"    Targets: Countries='{ad.target_countries}', States='{ad.target_states}'")

        match = True
        if ad.target_countries:
            country_codes = [code.strip().upper() for code in ad.target_countries.split(',')]
            if clinic.country.code not in country_codes:
                match = False
                print(f"    → Country mismatch: {clinic.country.code} not in {country_codes}")
        if match and ad.target_states:
            states = [s.strip().lower() for s in ad.target_states.split(',')]
            if clinic.state and clinic.state.lower() not in states:
                match = False
                print(f"    → State mismatch: {clinic.state.lower()} not in {states}")
        if match:
            video_ads.append(ad)
            print(f"    → MATCH! Added video_ad: {ad.title}")

    # === Fetch ALL matching active background ads ===
    background_ads = []
    background_candidates = AdCampaign.objects.filter(
        ad_type='background',
        is_active=True,
        start_date__lte=now,
        end_date__gte=now
    )

    print(f"DEBUG: Found {background_candidates.count()} active background candidates")
    for ad in background_candidates:
        print(f"  - Ad: '{ad.title}' | Active: {ad.is_active} | Dates: {ad.start_date} to {ad.end_date}")
        print(f"    Targets: Countries='{ad.target_countries}', States='{ad.target_states}'")

        match = True
        if ad.target_countries:
            country_codes = [code.strip().upper() for code in ad.target_countries.split(',')]
            if clinic.country.code not in country_codes:
                match = False
        if match and ad.target_states:
            states = [s.strip().lower() for s in ad.target_states.split(',')]
            if clinic.state and clinic.state.lower() not in states:
                match = False
        if match:
            background_ads.append(ad)
            print(f"    → MATCH! Added background_ad: {ad.title}")

    # === Final debug ===
    print("DEBUG: Final video_ads list:", [ad.title for ad in video_ads] or "None")
    print("DEBUG: Final background_ads list:", [ad.title for ad in background_ads] or "None")
    print("=== DEBUG END ===\n")

    context = {
        'clinic': clinic,
        'recent_records': recent_records,
        'total_records': PatientRecord.objects.filter(clinic=clinic, is_active=True).count(),
        'video_ads': video_ads,          # list (can be used later)
        'background_ads': background_ads,  # list for rotation
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
# @login_required
# @transaction.atomic
# def patient_update(request, pk):
#     clinic = get_object_or_404(Clinic, user=request.user)
#
#     if not clinic.is_approved or clinic.is_locked:
#         return redirect('records:clinic_dashboard')
#
#     old_record = get_object_or_404(PatientRecord, pk=pk, clinic=clinic)
#
#     if request.method == 'POST':
#         form = PatientRecordForm(request.POST, request.FILES)
#         if form.is_valid():
#             with transaction.atomic():
#                 # Step 1: Create a completely NEW record with form data
#                 new_record = PatientRecord()
#                 new_record.clinic = clinic
#                 new_record.full_name = form.cleaned_data['full_name']
#                 new_record.phone = form.cleaned_data['phone']
#                 new_record.address = form.cleaned_data['address']
#                 new_record.photo = form.cleaned_data['photo'] or old_record.photo  # Keep photo if not changed
#                 new_record.emergency_contact_name = form.cleaned_data['emergency_contact_name']
#                 new_record.emergency_contact_phone = form.cleaned_data['emergency_contact_phone']
#                 new_record.blood_group = form.cleaned_data['blood_group']
#                 new_record.allergies = form.cleaned_data['allergies']
#                 new_record.chronic_conditions = form.cleaned_data['chronic_conditions']
#                 new_record.other_notes = form.cleaned_data['other_notes']
#                 new_record.insurance_name = form.cleaned_data['insurance_name']
#                 new_record.insurance_phone = form.cleaned_data['insurance_phone']
#                 new_record.unique_id = uuid.uuid4()  # New UUID
#                 new_record.is_active = True
#                 new_record.save()
#
#                 # Step 2: Deactivate the old record
#                 old_record.is_active = False
#                 old_record.save(update_fields=['is_active'])
#
#             messages.success(
#                 request,
#                 f'Successfully updated record for {new_record.full_name}. '
#                 f'Old QR card is now invalid. Print the new one.'
#             )
#             return redirect('records:printable_card', unique_id=new_record.unique_id)
#     else:
#         # Pre-fill form with old record data
#         form = PatientRecordForm(instance=old_record)
#
#     return render(request, 'patient/form.html', {
#         'form': form,
#         'title': 'Update Record (New QR will be issued)',
#         'old_record': old_record
#     })


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


@login_required
def printable_card(request, unique_id):
    record = get_object_or_404(
        PatientRecord,
        unique_id=unique_id,
        is_active=True,
        clinic__user=request.user
    )

    # ---------------- QR CODE ----------------
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr_url = request.build_absolute_uri(f'/qr/{unique_id}/')
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_data_uri = "data:image/png;base64," + base64.b64encode(
        qr_buffer.getvalue()
    ).decode()

    # ---------------- PHOTO (FIX) ----------------
    photo_data_uri = None
    if record.photo and record.photo.path:
        with open(record.photo.path, 'rb') as f:
            photo_data_uri = (
                "data:image/jpeg;base64," +
                base64.b64encode(f.read()).decode()
            )

    # ---------------- RENDER ----------------
    html_string = render_to_string(
        'printable/card.html',
        {
            'record': record,
            'qr_data_uri': qr_data_uri,
            'photo_data_uri': photo_data_uri,
        }
    )

    # wkhtmltopdf config
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

    pdf = pdfkit.from_string(
        html_string,
        False,
        configuration=config,
        options={
            'page-width': '3.37in',
            'page-height': '2.12in',
            'margin-top': '0',
            'margin-right': '0',
            'margin-bottom': '0',
            'margin-left': '0',

        }
    )

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="{record.full_name.replace(" ", "_")}_LifeQR_Card.pdf"'
    )
    return response




@login_required
@login_required
def patient_suggestions(request):
    # Get the current user's clinic
    clinic = get_object_or_404(Clinic, user=request.user)

    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse([], safe=False)

    # Search only active patients in the user's clinic
    patients = PatientRecord.objects.filter(
        clinic=clinic,
        is_active=True
    ).filter(
        Q(full_name__icontains=query) | Q(phone__icontains=query)
    ).values('id', 'full_name', 'phone')[:10]  # Limit to 10 suggestions

    return JsonResponse(list(patients), safe=False)


@login_required
def patient_delete(request, pk):
    clinic = get_object_or_404(Clinic, user=request.user)

    if not clinic.is_approved or clinic.is_locked:
        return redirect('records:clinic_dashboard')

    try:
        record = PatientRecord.objects.get(pk=pk, clinic=clinic)
    except PatientRecord.DoesNotExist:
        messages.info(request,
                      "The patient record you tried to delete no longer exists. It may have already been deleted.")
        return redirect('records:clinic_dashboard')

    if request.method == 'POST':
        password = request.POST.get('password')
        user = authenticate(username=request.user.username, password=password)

        if user is not None:
            full_name = record.full_name  # Save name before deletion
            record.delete()
            messages.success(request, f'Record for {full_name} has been permanently deleted.')
            return redirect('records:patient_search')
        else:
            messages.error(request, "Incorrect password. Record not deleted.")

    return render(request, 'patient/delete_confirm.html', {'record': record})