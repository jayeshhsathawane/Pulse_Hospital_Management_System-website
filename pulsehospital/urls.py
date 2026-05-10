from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'pulsehospital'

urlpatterns = [
    path('stafflogin/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    # --- Website Main Pages ---
    path('', views.home, name='home'),
    path('services/', views.services, name='services'),
    path('doctors/', views.doctors, name='doctors'),
    path('pharmacy/', views.pharmacy, name='pharmacy'),
    path('gallery/', views.gallery, name='gallery'),
    path('contact/', views.contact, name='contact'),
    
    # --- LOGIN REDIRECT LOGIC ---
    # After login, the system will use this path to decide which dashboard to show
    path('dashboard-redirect/', views.dashboard_redirect, name='dashboard_redirect'),
    # path('start-consultation/<int:pk>/', views.start_consultation, name='start_consultation'),
  
    
    # --- Receptionist Dashboard ---
    # Corrected 'reception_dashboardF' to 'reception_dashboard'
    path('reception/', views.reception_dashboard, name='reception_dashboard'),
    path('reception/confirm/<int:pk>/', views.confirm_appointment, name='confirm_appointment'),
    path('reception/new-appointment/', views.walkin_appointment, name='walkin_appointment'),
    path('reception/daily-report/', views.daily_report, name='daily_report'),
    path('reception/delete/<int:pk>/', views.delete_appointment, name='delete_appointment'),
    path('reception/history/', views.ipd_discharge_history, name='ipd_discharge_history'),
    path('reception/print-discharge/<str:reg_id>/', views.direct_print_discharge, name='direct_print_discharge'),
    path('reception/ot-scheduled/', views.reception_ot_scheduled, name='reception_ot_scheduled'),
    path('reception/ot-completed/', views.reception_ot_completed, name='reception_ot_completed'),

    # --- Doctor Dashboard ---
    path('dashboard/', views.doctor_dashboard, name='dashboard'),
    path('dashboard/today/', views.dashboard_today, name='dashboard_today'),
    path('dashboard/patient/<int:pk>/', views.patient_detail, name='patient_detail'),
    path('dashboard/history/', views.patient_history, name='patient_history'),
    path('dashboard/delete-appointment/<int:pk>/', views.doctor_delete_appointment, name='doctor_delete_appointment'),
    path('doctor/admitted-patients/', views.doctor_admitted_patients, name='doctor_admitted_patients'),
    path('doctor/ipd-history/<int:adm_id>/', views.doctor_view_ipd_history, name='doctor_view_ipd_history'),
    path('doctor/discharged-case/<int:discharge_id>/', views.view_discharged_case, name='view_discharged_case'),
    
    #Pharmacy  Management URLs
    path('pharmacy/dashboard/', views.pharmacy_dashboard, name='pharmacy_dashboard'),
    path('pharmacy/edit/<int:pk>/', views.edit_medicine, name='edit_medicine'),
    path('pharmacy/delete/<int:pk>/', views.delete_medicine, name='delete_medicine'),
    path('pharmacy/bulk-delete/', views.bulk_delete_medicine, name='bulk_delete_medicine'),

    # 🟢 New Discharge Card URL 
    path('discharge/generate/', views.generate_discharge_card, name='generate_discharge_card'),
    path('discharge/history/', views.discharge_history, name='discharge_history'),

    # --- Autocomplete APIs ---
    path('api/medicines/', views.medicine_lookup, name='medicine_lookup'),
    path('api/medicine-lookup/', views.medicine_lookup, name='medicine_lookup'),
    path('api/symptoms/', views.symptom_lookup, name='symptom_lookup'),
    path('api/search-patient/', views.search_patient, name='search_patient'),
    path('api/get-patient-details/', views.get_patient_details, name='get_patient_details'),
    
    # --- Inventory (CSV Upload) ---
    path('reception/upload-medicines/', views.upload_medicine_csv, name='upload_medicine_csv'),

# --- NEW IPD & BED MANAGEMENT URLS ---
    
    # 1. IPD Admission Form (Search aur Admit ke liye)
    path('ipd/admission/', views.ipd_admission_form, name='ipd_admission_form'),

    # 2. Admitted Patients ki List (Current status dekhne ke liye)
    path('ipd/admitted-list/', views.admitted_patients_list, name='admitted_patients_list'),

    # 3. Patient ki Personal IPD Profile (Daily Treatment Records ke liye)
    # Isme <int:adm_id> zaroori hai taaki sahi patient ka data khule
    path('ipd/patient-profile/<int:adm_id>/', views.ipd_patient_profile, name='ipd_patient_profile'),

    # 4. Bed Dashboard (Visual Red/Green Grid ke liye)
    path('ipd/beds/', views.ipd_bed_dashboard, name='ipd_bed_dashboard'),

#  Operation Theatre (OT) Management 
# Doctor's OT Dashboard (Surgery list)
    path('ot/ot-management/', views.ot_management, name='ot_management'),
    
    # Action to schedule surgery from Prescription page
    path('ot/schedule-ot/<int:appt_id>/', views.schedule_ot_action, name='schedule_ot_action'),
    path('ot/new-ot-booking/', views.ot_scheduling_form, name='ot_scheduling_form'),
    # Professional Operation Note Print View
    path('ot/print-op-note/<int:ot_id>/', views.print_operation_note, name='print_operation_note'),

 # 🟢 Billing 
    path('billing/create/', views.create_bill, name='create_bill'), 
    path('billing/print/<int:bill_id>/', views.print_bill, name='print_bill'),
    path('billing/history/', views.bill_history, name='bill_history'),



# #api testing
#    path('api/mobile/medicines/', views.medicine_api_list, name='medicine_api_list'),
#    path('api/mobile/login/', views.login_api, name='login_api'),

#    # 🟢 Doctor Dashboard API
#     path('api/mobile/doctor/dashboard/', views.doctor_dashboard_api, name='doctor_dashboard_api'),
#     # 🟢 Checkup Screen API (GET = Details, POST = Save)
#     path('api/mobile/doctor/checkup/<int:pk>/', views.patient_checkup_api, name='patient_checkup_api'),
    
#     # 🟢 Reception APIs
#     path('api/mobile/reception/dashboard/', views.reception_dashboard_api, name='reception_dashboard_api'),
#     path('api/mobile/reception/book/', views.book_appointment_api, name='book_appointment_api'),

#     # 🟢 Billing APIs
#     path('api/mobile/billing/search-patient/', views.search_admitted_patient_api, name='search_admitted_patient_api'),
#     path('api/mobile/billing/create/', views.create_bill_api, name='create_bill_api'),

#     # 🟢 1. IPD & Bed Management
#     path('api/mobile/reception/beds/', views.bed_dashboard_api, name='bed_dashboard_api'),
#     path('api/mobile/reception/admit/', views.admit_patient_api, name='admit_patient_api'),

#     # 🟢 2. Pending Requests
#     path('api/mobile/reception/pending/', views.pending_requests_api, name='pending_requests_api'),
#     path('api/mobile/reception/confirm/<int:pk>/', views.confirm_request_api, name='confirm_request_api'),
#     path('api/mobile/reception/search-master/', views.search_patient_profile_api, name='search_patient_profile_api'),
#     path('api/mobile/reception/ipd-rounds/<int:admission_id>/', views.ipd_daily_round_api, name='ipd_daily_round_api'),
#     path('api/mobile/reception/discharge/<int:admission_id>/', views.discharge_patient_api, name='discharge_patient_api'),

#     # 🟢 3. OT Schedule
#     path('api/mobile/reception/ot-schedule/', views.ot_schedule_api, name='ot_schedule_api'),

#     # 🟢 Doctor Discharge & OT
#     path('api/mobile/doctor/discharge-summary/', views.save_discharge_summary_api, name='save_discharge_summary_api'),
#     path('api/mobile/doctor/book-ot/', views.book_surgery_api, name='book_surgery_api'),
#     path('api/mobile/doctor/ot-notes/<int:ot_id>/', views.save_ot_notes_api, name='save_ot_notes_api'),
]