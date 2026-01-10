from django.contrib import admin
from django.db.models import Count, Q  # <-- This was missing!
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django_countries import countries
from .models import Clinic, PatientRecord
from .models import AdCampaign
from django_countries.fields import CountryField
from django import forms



class AdCampaignAdminForm(forms.ModelForm):
    class Meta:
        model = AdCampaign
        fields = '__all__'

    target_countries = forms.MultipleChoiceField(
        choices=[(code, name) for code, name in countries],
        required=False,
        widget=forms.SelectMultiple(attrs={'size': 10}),
        help_text="Select countries (hold Ctrl/Cmd for multiple)"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Pre-fill with existing codes
            self.fields['target_countries'].initial = self.instance.target_countries.split(',') if self.instance.target_countries else []

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Save selected codes as comma-separated string
        instance.target_countries = ','.join(self.cleaned_data['target_countries'])
        if commit:
            instance.save()
        return instance


@admin.register(AdCampaign)
class AdCampaignAdmin(admin.ModelAdmin):
    form = AdCampaignAdminForm  # Use our custom form
    list_display = ('title', 'ad_type', 'start_date', 'end_date', 'is_active', 'target_countries_short', 'target_states_short')
    list_filter = ('ad_type', 'is_active', 'start_date', 'end_date')
    search_fields = ('title',)
    list_per_page = 20
    date_hierarchy = 'start_date'

    def target_countries_short(self, obj):
        if obj.target_countries:
            codes = obj.target_countries.split(',')
            return ', '.join(code.strip() for code in codes[:3]) + ('...' if len(codes) > 3 else '')
        return "All countries"
    target_countries_short.short_description = "Countries"

    def target_states_short(self, obj):
        if obj.target_states:
            states = obj.target_states.split(',')
            return ', '.join(s.strip() for s in states[:3]) + ('...' if len(states) > 3 else '')
        return "All states"
    target_states_short.short_description = "States"

    fieldsets = (
        ('Basic Info', {'fields': ('title', 'ad_type', 'is_active')}),
        ('Schedule', {'fields': ('start_date', 'end_date')}),
        ('Targeting', {'fields': ('target_countries', 'target_states')}),
        ('Content', {'fields': ('video_file', 'background_image')}),
    )


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ['name', 'state', 'phone', 'is_approved', 'is_locked', 'date_joined', 'record_count']
    list_filter = ['state', 'is_approved', 'is_locked', 'date_joined']
    search_fields = ['name', 'address', 'phone']
    readonly_fields = ['date_joined']
    actions = ['approve_clinics', 'lock_clinics', 'unlock_clinics']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_record_count=Count('patientrecord'))

    def record_count(self, obj):
        count = obj._record_count
        url = reverse('admin:records_patientrecord_changelist') + f'?clinic__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    record_count.short_description = 'Active Records'
    record_count.admin_order_field = '_record_count'  # Allows sorting

    def approve_clinics(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"{updated} clinics approved.")
    approve_clinics.short_description = "Approve selected clinics"

    def lock_clinics(self, request, queryset):
        updated = queryset.update(is_locked=True)
        self.message_user(request, f"{updated} clinics locked.")
    lock_clinics.short_description = "Lock selected clinics"

    def unlock_clinics(self, request, queryset):
        updated = queryset.update(is_locked=False)
        self.message_user(request, f"{updated} clinics unlocked.")
    unlock_clinics.short_description = "Unlock selected clinics"

@admin.register(PatientRecord)
class PatientRecordAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'clinic_link', 'blood_group', 'phone', 'is_active', 'updated_at']
    list_filter = ['clinic__state', 'blood_group', 'is_active', 'clinic']
    search_fields = ['full_name', 'phone', 'emergency_contact_phone']
    readonly_fields = ['unique_id', 'created_at', 'updated_at']

    def clinic_link(self, obj):
        url = reverse('admin:records_clinic_change', args=[obj.clinic.id])
        return format_html(f'<a href="{url}">{obj.clinic.name} ({obj.clinic.state})</a>')
    clinic_link.short_description = 'Clinic'


# Custom Superuser Dashboard Stats
admin.site.site_header = "LifeQR - Emergency Medical Records"
admin.site.site_title = "LifeQR Admin"
admin.site.index_title = "Superuser Dashboard"

# Optional: Add a custom view for state-by-state summary
def get_state_stats():
    return Clinic.objects.values('state').annotate(
        clinic_count=Count('id'),
        active_records=Count('patientrecord', filter=Q(patientrecord__is_active=True))
    ).order_by('state')

# Override the admin index template to show stats (optional, but cool)
# For now, just know the built-in admin + filters above already gives great insights!