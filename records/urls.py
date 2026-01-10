from django.urls import path
from . import views

app_name = 'records'

urlpatterns = [
    # Home / Clinic Dashboard
    path('', views.clinic_dashboard, name='clinic_dashboard'),

    # Clinic Registration
    path('register/', views.clinic_register, name='clinic_register'),

    # Patient Records
    path('patient/new/', views.patient_create, name='patient_create'),
    path('patient/<int:pk>/delete/', views.patient_delete, name='patient_delete'),
    path('patient/search/', views.patient_search, name='patient_search'),

    # Printable Card
    path('patient/<uuid:unique_id>/print/', views.printable_card, name='printable_card'),

    # Emergency QR View (public)
    path('qr/<uuid:unique_id>/', views.emergency_view, name='emergency_view'),

    # Superuser Dashboard
    path('superuser/', views.superuser_dashboard, name='superuser_dashboard'),

    path('patient/suggestions/', views.patient_suggestions, name='patient_suggestions'),

    path('patient/<int:pk>/detail/', views.patient_detail, name='patient_detail'),
]