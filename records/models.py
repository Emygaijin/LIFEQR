import uuid
from django.db import models
from django.contrib.auth.models import User

# Nigeria States + FCT
NIGERIA_STATES = [
    ('Abuja', 'Abuja (FCT)'),
    ('Abia', 'Abia'), ('Adamawa', 'Adamawa'), ('Akwa Ibom', 'Akwa Ibom'),
    ('Anambra', 'Anambra'), ('Bauchi', 'Bauchi'), ('Bayelsa', 'Bayelsa'),
    ('Benue', 'Benue'), ('Borno', 'Borno'), ('Cross River', 'Cross River'),
    ('Delta', 'Delta'), ('Ebonyi', 'Ebonyi'), ('Edo', 'Edo'),
    ('Ekiti', 'Ekiti'), ('Enugu', 'Enugu'), ('Gombe', 'Gombe'),
    ('Imo', 'Imo'), ('Jigawa', 'Jigawa'), ('Kaduna', 'Kaduna'),
    ('Kano', 'Kano'), ('Katsina', 'Katsina'), ('Kebbi', 'Kebbi'),
    ('Kogi', 'Kogi'), ('Kwara', 'Kwara'), ('Lagos', 'Lagos'),
    ('Nasarawa', 'Nasarawa'), ('Niger', 'Niger'), ('Ogun', 'Ogun'),
    ('Ondo', 'Ondo'), ('Osun', 'Osun'), ('Oyo', 'Oyo'),
    ('Plateau', 'Plateau'), ('Rivers', 'Rivers'), ('Sokoto', 'Sokoto'),
    ('Taraba', 'Taraba'), ('Yobe', 'Yobe'), ('Zamfara', 'Zamfara'),
]


class Clinic(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    address = models.TextField()
    state = models.CharField(max_length=50, choices=NIGERIA_STATES)
    phone = models.CharField(max_length=15, blank=True)
    is_approved = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)  # For subscription failure
    date_joined = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.state})"


class PatientRecord(models.Model):
    BLOOD_GROUPS = [
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-'),
        ('Unknown', 'Unknown'),
    ]

    clinic = models.ForeignKey(Clinic, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    photo = models.ImageField(upload_to='patients/', blank=True, null=True)

    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    insurance_name = models.CharField(max_length=200, blank=True, verbose_name="Insurance Company Name")
    insurance_phone = models.CharField(max_length=15, blank=True, verbose_name="Insurance Company Phone")
    blood_group = models.CharField(max_length=10, choices=BLOOD_GROUPS, default='Unknown')
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    other_notes = models.TextField(blank=True)

    unique_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.full_name} ({self.clinic.name})"

    def deactivate_old_versions(self):
        PatientRecord.objects.filter(
            full_name__iexact=self.full_name,
            phone=self.phone,
            clinic=self.clinic
        ).exclude(pk=self.pk).update(is_active=False)

    class Meta:
        # Prevent multiple active records for the same patient in the same clinic
        constraints = [
            models.UniqueConstraint(
                fields=['full_name', 'phone', 'clinic'],
                condition=models.Q(is_active=True),
                name='unique_active_patient_per_clinic'
            )
        ]