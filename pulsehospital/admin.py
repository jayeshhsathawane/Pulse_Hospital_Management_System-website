from django.contrib import admin
from import_export.admin import ImportExportModelAdmin 
from django.shortcuts import redirect
from .models import Doctor, Appointment, Receptionist, PatientProfile, Medicine, Symptom, Pharmacist, DischargeSummary # Added Pharmacist & DischargeSummary
from django.utils.html import format_html
from django.urls import path
from .models import Bed, IPD_Admission, IPD_DailyRecord
from .models import Bill


# 1. Doctor Model Admin
@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'specialty', 'user')
    search_fields = ('name', 'specialty')
    list_filter = ('specialty',)

# 2. NEW: Receptionist Model Admin
@admin.register(Receptionist)
class ReceptionistAdmin(admin.ModelAdmin):
    list_display = ('name', 'employee_id', 'user')
    search_fields = ('name', 'employee_id')

# 3. Appointment Model Admin
@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient_name', 'assigned_doctor', 'appointment_date', 'status', 'booked_on')
    list_filter = ('status', 'assigned_doctor', 'department', 'appointment_date')
    search_fields = ('patient_name', 'phone', 'reason')
    readonly_fields = ('booked_on',) 
    fieldsets = (
        ('Patient Info', {'fields': ('patient_name', 'phone', 'email', 'age', 'patient_profile')}),
        ('Appointment Details', {'fields': ('department', 'assigned_doctor', 'appointment_date', 'appointment_time', 'status')}),
        ('Medical Records', {'fields': ('symptoms', 'diagnosis', 'medication_json')}),
    )

# 4. NEW: Patient Profile Admin (History tracking)
@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('reg_number', 'name', 'phone', 'age')
    search_fields = ('reg_number', 'name', 'phone')
    readonly_fields = ('reg_number',) 

# 5. UPDATED: Medicine Admin with Composition & CSV Support
@admin.register(Medicine)
class MedicineAdmin(ImportExportModelAdmin): 
    # Added 'composition' and 'added_on' to the list display
    list_display = ('name', 'composition', 'added_on')
    search_fields = ('name', 'composition')
    list_filter = ('added_on',)

# 6. NEW: Symptom Admin
@admin.register(Symptom)
class SymptomAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

# 🟢 7. ADDED: Pharmacist Model Admin (To show in sidebar)
@admin.register(Pharmacist)
class PharmacistAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'user')
    search_fields = ('name', 'phone')

# 🟢 8. ADDED: Discharge Summary Admin
@admin.register(DischargeSummary)
class DischargeSummaryAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor_name', 'date_of_discharge')
    search_fields = ('patient__name', 'doctor_name')

    #IPD MANAGE

@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ('bed_number', 'bed_type', 'is_occupied')
    list_filter = ('is_occupied', 'bed_type')
    search_fields = ('bed_number',)

# IPD Admission  register 
@admin.register(IPD_Admission)
class IPD_AdmissionAdmin(admin.ModelAdmin):
    list_display = ('admission_id', 'patient', 'bed', 'admission_date', 'is_discharged')
    search_fields = ('admission_id', 'patient__name', 'patient__phone')

# Daily Records register
admin.site.register(IPD_DailyRecord)

# Invoice 
from .models import Bill

@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    # Admin table mein kaunse columns dikhne chahiye
    list_display = ('bill_number', 'patient', 'total_amount', 'payment_mode', 'bill_date')
    
    # Filter karne ke liye options (side bar mein)
    list_filter = ('payment_mode', 'bill_date')
    
    # Search karne ke liye fields
    search_fields = ('bill_number', 'patient__name', 'transaction_id')
    
    # Sirf read-only banane ke liye (taki koi purana bill change na kar sake)
    readonly_fields = ('bill_number', 'bill_date')
    
    # Date hierarchy (top par calendar filter ke liye)
    # date_hierarchy = 'bill_date'