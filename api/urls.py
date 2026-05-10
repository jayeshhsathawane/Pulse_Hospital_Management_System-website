from django.urls import path
from . import views  

urlpatterns = [
    # 🟢 General APIs
    path('mobile/medicines/', views.medicine_api_list, name='medicine_api_list'),
    path('mobile/login/', views.login_api, name='login_api'),

    # 🟢 Doctor Dashboard API
    path('mobile/doctor/dashboard/', views.doctor_dashboard_api, name='doctor_dashboard_api'),
    # 🟢 Checkup Screen API (GET = Details, POST = Save)
    path('mobile/doctor/checkup/<int:pk>/', views.patient_checkup_api, name='patient_checkup_api'),
    
    # 🟢 Reception APIs
    path('mobile/reception/dashboard/', views.reception_dashboard_api, name='reception_dashboard_api'),
    path('mobile/reception/book/', views.book_appointment_api, name='book_appointment_api'),

    # 🟢 Billing APIs
    path('mobile/billing/search-patient/', views.search_admitted_patient_api, name='search_admitted_patient_api'),
    path('mobile/billing/create/', views.create_bill_api, name='create_bill_api'),

    # 🟢 1. IPD & Bed Management
    path('mobile/reception/beds/', views.bed_dashboard_api, name='bed_dashboard_api'),
    path('mobile/reception/admit/', views.admit_patient_api, name='admit_patient_api'),

    # 🟢 2. Pending Requests
    path('mobile/reception/pending/', views.pending_requests_api, name='pending_requests_api'),
    path('mobile/reception/confirm/<int:pk>/', views.confirm_request_api, name='confirm_request_api'),
    path('mobile/reception/search-master/', views.search_patient_profile_api, name='search_patient_profile_api'),
    path('mobile/reception/ipd-rounds/<int:admission_id>/', views.ipd_daily_round_api, name='ipd_daily_round_api'),
    path('mobile/reception/discharge/<int:admission_id>/', views.discharge_patient_api, name='discharge_patient_api'),

    # 🟢 3. OT Schedule
    path('mobile/reception/ot-schedule/', views.ot_schedule_api, name='ot_schedule_api'),

    # 🟢 Doctor Discharge & OT
    path('mobile/doctor/discharge-summary/', views.save_discharge_summary_api, name='save_discharge_summary_api'),
    path('mobile/doctor/book-ot/', views.book_surgery_api, name='book_surgery_api'),
    path('mobile/doctor/ot-notes/<int:ot_id>/', views.save_ot_notes_api, name='save_ot_notes_api'),
]