import csv
import io
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from datetime import date, datetime
from django.contrib import messages
from .models import (
    Appointment, Doctor, PatientProfile, Medicine, Symptom, 
    Receptionist, DischargeSummary, Pharmacist, IPD_Admission, 
    Bed, IPD_DailyRecord,OTBooking
)
from .forms import AppointmentForm
from django.core import serializers
from django.utils import timezone
from django.db.models import Q
from .models import Bill, IPD_Admission, Doctor 
from django.utils import timezone
import time



# --- 1. LOGIN REDIRECT LOGIC ---
@login_required
def dashboard_redirect(request):
    if request.user.is_superuser:
        return redirect('/pulse-control/')
    
    if Doctor.objects.filter(user=request.user).exists():
        return redirect('pulsehospital:dashboard')
    
    is_pharmacist = Pharmacist.objects.filter(user=request.user).exists()
    if is_pharmacist or request.user.groups.filter(name='Pharmacists').exists():
        return redirect('pulsehospital:pharmacy_dashboard')
  
    is_receptionist = Receptionist.objects.filter(user=request.user).exists()
    if is_receptionist or request.user.is_staff:
        return redirect('pulsehospital:reception_dashboard')
    
    return redirect('pulsehospital:home')

# --- 2. STATIC PAGE VIEWS ---
def home(request):
    real_count = PatientProfile.objects.count()
    patient_count = 0 + real_count
    return render(request, 'index.html', {'patient_count': patient_count})

def services(request): return render(request, 'services.html')
def doctors(request): return render(request, 'doctors.html')
def pharmacy(request): return render(request, 'pharmacy.html')
def gallery(request): return render(request, 'gallery.html')

# --- 3. PUBLIC APPOINTMENT ---
def contact(request):
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.status = 'Pending'
            appointment.save()
            return redirect('pulsehospital:home')
    else:
        form = AppointmentForm()
    return render(request, 'contact.html', {'form': form})

# --- 4. RECEPTION DASHBOARD ---
@login_required
def reception_dashboard(request):
    if Doctor.objects.filter(user=request.user).exists():
        return redirect('pulsehospital:dashboard')
    
    today = date.today()
    
    # --- Purana Logic (Bina kuch hataye) ---
    pending_requests = Appointment.objects.filter(status='Pending').order_by('-booked_on')
    confirmed_appointments = Appointment.objects.filter(status='Confirmed', appointment_date=today).order_by('appointment_time')
    completed_today_count = Appointment.objects.filter(status='Completed', appointment_date=today).count()
    gyn_confirmed = confirmed_appointments.filter(patient_profile__assigned_doctor_code='GYN').count()
    gyn_completed = Appointment.objects.filter(status='Completed', appointment_date=today, patient_profile__assigned_doctor_code='GYN').count()
    med_confirmed = confirmed_appointments.filter(patient_profile__assigned_doctor_code='MED').count()
    med_completed = Appointment.objects.filter(status='Completed', appointment_date=today, patient_profile__assigned_doctor_code='MED').count()
    total_bookings_today = confirmed_appointments.count() + completed_today_count
    all_doctors = Doctor.objects.all()
    
    # --- 🏥 Naya OT Management Logic (Update) ---
    # Aaj ki saari Scheduled surgeries reception ko dikhane ke liye
    upcoming_surgeries = OTBooking.objects.filter(
        ot_date=today, 
        status='Scheduled'
    ).order_by('ot_time')
    
    # --- Context Data ---
    return render(request, 'reception/reception_dashboard.html', {
        'pending': pending_requests, 
        'confirmed': confirmed_appointments,
        'completed_count': completed_today_count, 
        'total_today': total_bookings_today,
        'doctors': all_doctors, 
        'today_date': today,
        'gyn_total': gyn_confirmed + gyn_completed, 
        'med_total': med_confirmed + med_completed,
        'gyn_pending': gyn_confirmed, 
        'med_pending': med_confirmed,
        'upcoming_surgeries': upcoming_surgeries,
    })

@login_required
def confirm_appointment(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        doctor_id = request.POST.get('doctor')
        profile, created = PatientProfile.objects.get_or_create(
            phone=appointment.phone,
            defaults={'name': appointment.patient_name, 'age': appointment.age}
        )
        appointment.patient_profile = profile
        appointment.assigned_doctor = get_object_or_404(Doctor, id=doctor_id)
        appointment.status = 'Confirmed'
        appointment.is_follow_up = not created
        appointment.save()
        messages.success(request, "Appointment confirmed successfully!")
    return redirect('pulsehospital:reception_dashboard')

# --- 5. DOCTOR DASHBOARD ---
@login_required
def doctor_dashboard(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return redirect('pulsehospital:reception_dashboard')
    today = date.today()
    
    # --- NEW LOGIC START: Search and Date Filter ---
    query = request.GET.get('q') # For searching by name or Reg ID
    selected_date = request.GET.get('date') # For filtering by specific date
    
    # Base query for confirmed appointments for this doctor
    appointments_queue = Appointment.objects.filter(assigned_doctor=doctor, status='Confirmed')

    if query:
        # Search across patient name or registration number
        appointments_queue = appointments_queue.filter(
            Q(patient_name__icontains=query) | Q(patient_profile__reg_number__icontains=query)
        )
    elif selected_date:
        # Filter by the date selected in the picker (e.g., 2025-12-23)
        appointments_queue = appointments_queue.filter(appointment_date=selected_date)
    else:
        # Default view: only show today's confirmed patients
        appointments_queue = appointments_queue.filter(appointment_date=today)
        monthly_count = Appointment.objects.filter(
        assigned_doctor=doctor, status='Completed',
        appointment_date__month=today.month, appointment_date__year=today.year
    ).count()

    # Original logic for completed patients today
    completed_today = Appointment.objects.filter(
        assigned_doctor=doctor, status='Completed', appointment_date=today
    ).order_by('-booked_on')
    
    return render(request, 'doctor/doctor_dashboard.html', {
        'doctor': doctor, 
        'appointments': appointments_queue.order_by('appointment_time'),
        'completed_today': completed_today, 
        'monthly_patient_count': monthly_count,
        'current_month_name': today.strftime('%B'),
        'selected_date': selected_date or str(today) # Pass selected date back to template
    })

# --- NEW FUNCTION: Doctor Delete Appointment ---
@login_required
def doctor_delete_appointment(request, pk):
    """Doctor can delete an appointment and stay on the same filtered date."""
    appointment = get_object_or_404(Appointment, pk=pk)
    current_date = request.GET.get('date', '') # 🟢 Capture current filters from the URL to maintain state after redirect
    current_search = request.GET.get('q', '')
    
    try:
        doctor = Doctor.objects.get(user=request.user)
        # Security: Only the assigned doctor can delete their own appointment
        if appointment.assigned_doctor == doctor:
            patient_name = appointment.patient_name
            appointment.delete() # Permanently remove from database
            messages.error(request, f"Appointment for {patient_name} deleted successfully.")
        else:
            messages.warning(request, "You are not authorized to delete this.")
    except Doctor.DoesNotExist:
        messages.error(request, "Access Denied.")
    
    # 🟢 Redirect back with the same date and search parameters
    return redirect(f"/dashboard/?date={current_date}&q={current_search}")

# --- 6. PATIENT CHECKUP ---
@login_required
def patient_detail(request, pk):
    # Current appointment uthao
    appointment = get_object_or_404(Appointment, pk=pk)
    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        doctor = None 
    if request.method == 'POST':
        
        appointment.diagnosis = request.POST.get('diagnosis')
        appointment.symptoms = request.POST.get('symptoms')
        appointment.personal_history = request.POST.getlist('history') 
        appointment.comorbidities = request.POST.getlist('comorbidities') 
        appointment.other_comorbidities = request.POST.get('other_comorbidities')
        medication_data = request.POST.get('medication_json')
        if medication_data:
            try:
                appointment.medication_json = json.loads(medication_data)
            except json.JSONDecodeError:
                appointment.medication_json = []

        # Status completed mark
        appointment.status = 'Completed'
        appointment.save()
        messages.success(request, f"Medical record for {appointment.patient_name} archived.")
        return redirect('pulsehospital:dashboard')
    
    # HISTORY LOGIC
    past_visits = Appointment.objects.filter(
        patient_profile=appointment.patient_profile, 
        status='Completed'
    ).order_by('-appointment_date')

    context = {
        'appointment': appointment, 
        'past_visits': past_visits,
        'doctor': doctor 
    }
    return render(request, 'doctor/patient_detail.html', context)

# --- 7. DISCHARGE CARD ---
@login_required
def generate_discharge_card(request):
    reg_id = request.GET.get('reg_id')
    patient_data = None
    
    if reg_id:
        profile = PatientProfile.objects.filter(reg_number=reg_id).first()
        if profile:
            # 1. Check karo agar Discharge Summary pehle se saved hai
            saved_record = DischargeSummary.objects.filter(patient=profile).last()
            
            if saved_record:
                # Agar purana record hai, wahi dikhao
                patient_data = {'profile': profile, 'is_saved': True, 'record': saved_record}
            else:
                # 2. Agar Naya Discharge hai (Not Saved)
                last_visit = Appointment.objects.filter(patient_profile=profile).last()
                
                # 🟢 FIX START: Active Admission Data Fetch Karo
                active_admission = IPD_Admission.objects.filter(patient=profile).last()
                
               
                initial_record_data = {}
                if active_admission:
            
                    local_admission_date = timezone.localtime(active_admission.admission_date)
                    initial_record_data['date_of_admission'] = active_admission.admission_date
                
                patient_data = {
                    'profile': profile, 
                    'is_saved': False, 
                    'last_visit': last_visit,
                    'record': initial_record_data # 🟢 Ye line Date show karegi
                }
                # 🟢 FIX END

    if request.method == 'POST':
        patient_profile = get_object_or_404(PatientProfile, id=request.POST.get('patient_id'))
        
        # --- 🟢 EXISTING LOGIC: Auto-Bed Release & IPD Status Update ---
        active_admission = IPD_Admission.objects.filter(patient=patient_profile, is_discharged=False).first()
        if active_admission:
            if active_admission.bed:
                bed_obj = active_admission.bed
                bed_obj.is_occupied = False
                bed_obj.save()
            
            active_admission.is_discharged = True
            active_admission.discharge_date = timezone.now()
            active_admission.save()

        # --- 🟢 UPDATED LOGIC: Saving All Fields (Old + New) ---
        DischargeSummary.objects.update_or_create(
            patient=patient_profile,
            defaults={
                'doctor_name': request.user.get_full_name() or request.user.username,
                # Ab POST request mein HTML se sahi date aayegi kyunki humne GET fix kar diya hai
                'date_of_admission': request.POST.get('adm_date'), 
                
                # Naye Clinical Fields
                'presenting_complaints': request.POST.get('presenting_complaints'),
                'final_diagnosis': request.POST.get('final_diagnosis'),
                
                # Pehle wale Investigations
                'hb': request.POST.get('hb'), 
                'tlc': request.POST.get('tlc'),
                'platelets': request.POST.get('platelets'), 
                'bul': request.POST.get('bul'),
                'creatinine': request.POST.get('creatinine'), 
                
                # Naye Investigation Fields
                'lft': request.POST.get('lft'),
                'xray': request.POST.get('xray'),
                'ct_scan': request.POST.get('ct_scan'),
                'mri': request.POST.get('mri'),

                # Condition Fields
                'condition_on_admission': request.POST.get('cond_admission'),
                'condition_on_discharge': request.POST.get('cond_discharge'),

                # Treatment & Follow-up
                'treatment_given': request.POST.get('treatment_given'),
                'treatment_advised': request.POST.get('treatment_advised'), 
                'follow_up': request.POST.get('follow_up')
            }
        )
        messages.success(request, "Discharge Details Saved & Bed Released Successfully!")
        return redirect(f"{request.path}?reg_id={reg_id}")

    return render(request, 'doctor/discharge_card.html', {
        'data': patient_data, 
        'reg_id': reg_id, 
        'current_time': timezone.now(),
        'doctor_full_name': request.user.get_full_name() or request.user.username
    })

# --- 8. DASHBOARD TODAY (AS REQUESTED) ---
@login_required
def dashboard_today(request):
    try:
        doctor = Doctor.objects.get(user=request.user)
        today_appointments = Appointment.objects.filter(
            assigned_doctor=doctor, appointment_date=date.today(), status='Confirmed'
        ).order_by('appointment_time')
        return render(request, 'doctor/doctor_dashboard.html', {'doctor': doctor, 'appointments': today_appointments})
    except Doctor.DoesNotExist:
        return redirect('pulsehospital:reception_dashboard')

# --- 9. PHARMACY LOGIC ---
@login_required
def pharmacy_dashboard(request):
    if request.method == 'POST':
        if 'csv_file' in request.FILES:
            csv_file = request.FILES['csv_file']
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            next(io_string)
            for row in csv.reader(io_string):
                if len(row) >= 2:
                    Medicine.objects.update_or_create(name=row[0].strip(), defaults={'composition': row[1].strip()})
            messages.success(request, "Stock updated successfully!")
        else:
            name = request.POST.get('name'); comp = request.POST.get('composition')
            Medicine.objects.update_or_create(name=name, defaults={'composition': comp})
            messages.success(request, f"{name} added.")
    medicines = Medicine.objects.all().order_by('-id')
    return render(request, 'pharmacy/pharmacy_dashboard.html', {'medicines': medicines})

@login_required
@user_passes_test(lambda u: u.is_staff)
def upload_medicine_csv(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        decoded_file = csv_file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        next(io_string)
        for row in csv.reader(io_string, delimiter=','):
            Medicine.objects.get_or_create(name=row[0])
        return redirect('pulsehospital:reception_dashboard')
    return render(request, 'upload_csv.html')

def medicine_lookup(request):
    term = request.GET.get('term', '')
    medicines = Medicine.objects.filter(Q(name__icontains=term) | Q(composition__icontains=term))[:20]
    results = [{"label": f"{m.name} ({m.composition})", "value": m.name} for m in medicines]
    return JsonResponse(results, safe=False)

def symptom_lookup(request):
    term = request.GET.get('term', '')
    symptoms = Symptom.objects.filter(name__icontains=term)[:10]
    return JsonResponse([s.name for s in symptoms], safe=False)

@login_required
def patient_history(request):
    doctor = get_object_or_404(Doctor, user=request.user)
    today = timezone.now().date()
    
    # URL parameters lena
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    query = request.GET.get('q')

    # Base Query
    history = Appointment.objects.filter(assigned_doctor=doctor, status='Completed')

    # Logic: Agar koi date select nahi ki, toh sirf AAJ ke patients dikhao
    # Agar date select ki hai, toh us range ke patients dikhao
    if start_date and end_date:
        history = history.filter(appointment_date__range=[start_date, end_date])
    elif start_date:
        history = history.filter(appointment_date__gte=start_date)
    elif not query: # Agar search bhi nahi hai aur date bhi nahi, toh sirf aaj ka records
        history = history.filter(appointment_date=today)

    # Search filter
    if query:
        history = history.filter(
            Q(patient_name__icontains=query) | 
            Q(patient_profile__reg_number__icontains=query)
        )

    history = history.order_by('-appointment_date')

    context = {
        'history': history,
        'doctor': doctor,
        'selected_start': start_date,
        'selected_end': end_date,
        'query': query,
        'is_today': not (start_date or end_date or query) # Check karne ke liye ki aaj ka view hai ya nahi
    }
    return render(request, 'doctor/patient_history.html', context)

#  When Appoinment book 
def search_patient(request):
    # 'q' ya 'phone' dono mein se jo bhi mile use utha lo
    query = request.GET.get('q') or request.GET.get('phone', '')
    query = query.strip()

    if query:
        # Q object ka use karke phone ya reg_number dono ko search karein
        patient = PatientProfile.objects.filter(
            Q(phone=query) | Q(reg_number__iexact=query)
        ).first()

        if patient:
            return JsonResponse({
                'exists': True, 
                'name': patient.name, 
                'age': patient.age, 
                'gender': patient.gender, # Gender bhi add kar diya taaki select ho jaye
                'address': patient.address, 
                'reg_number': patient.reg_number
            })
            
    return JsonResponse({'exists': False})
# --- 10. WALKIN APPOINTMENT ---
@login_required
def walkin_appointment(request):
    if Doctor.objects.filter(user=request.user).exists():
        return redirect('pulsehospital:dashboard')
    pre_fill = {'phone': request.GET.get('phone', ''), 'name': request.GET.get('name', ''), 'address': request.GET.get('address', '')}
    if request.method == 'POST':
        doctor_obj = get_object_or_404(Doctor, id=request.POST.get('doctor'))
        dr_code = 'GYN' if 'gynec' in doctor_obj.specialty.lower() else 'MED'
        profile, created = PatientProfile.objects.get_or_create(
            phone=request.POST.get('phone'), assigned_doctor_code=dr_code,
            defaults={'name': request.POST.get('patient_name'), 'age': request.POST.get('age'), 'address': request.POST.get('address'), 'gender': request.POST.get('gender')}
        )
        if not created:
            profile.address = request.POST.get('address'); profile.age = request.POST.get('age'); profile.save()
        
        Appointment.objects.create(
            patient_name=request.POST.get('patient_name'), phone=request.POST.get('phone'), age=request.POST.get('age'),
            bp=request.POST.get('bp'), pulse=request.POST.get('pulse'), sugar=request.POST.get('sugar'),
            patient_profile=profile, assigned_doctor=doctor_obj, appointment_date=date.today(),
            appointment_time=datetime.now().time(), status='Confirmed', is_follow_up=not created
        )
        Appointment.objects.filter(phone=request.POST.get('phone'), status='Pending').delete()
        messages.success(request, "Appointment booked successfully!")
        return redirect('pulsehospital:reception_dashboard')
    return render(request, 'reception/reception_new_appointment.html', {'doctors': Doctor.objects.all(), 'pre_fill': pre_fill})

# --- 11. IPD MANAGEMENT (NEW ADDITIONS) ---
@login_required
def ipd_admission_form(request):
    query = request.GET.get('q')
    patient = None
    if query:
        # Search patient by phone or reg number
        patient = PatientProfile.objects.filter(Q(phone=query) | Q(reg_number=query)).first()
    
    if request.method == 'POST':
        bed_obj = Bed.objects.get(id=request.POST.get('bed_id'))
        patient_id = request.POST.get('patient_id')
        patient_obj = PatientProfile.objects.get(id=patient_id)

        # 🟢 NEW LOGIC: Admission ID = Patient Reg Number
        # Purana NH0740 wala format comment karke naya logic apply kiya gaya hai
        adm_id = patient_obj.reg_number 
        IPD_Admission.objects.create(
            patient=patient_obj, 
            admission_id=adm_id, 
            bed=bed_obj,
            attending_doctor_id=request.POST.get('doctor_id'), 
            diagnosis=request.POST.get('diagnosis'),
            admission_date=timezone.now() # Current date and time
        )
        
        # Bed ko block karein
        bed_obj.is_occupied = True
        bed_obj.save()
        
        messages.success(request, f"Patient Admitted Successfully with ID: {adm_id}")
        return redirect('pulsehospital:admitted_patients_list')

    # Available beds aur doctors ki list template ko bhej rahe hain
    return render(request, 'ipd/admission_form.html', {
        'patient': patient, 
        'beds': Bed.objects.filter(is_occupied=False), 
        'doctors': Doctor.objects.all()
    })

@login_required
def ipd_bed_dashboard(request):
    """Visual Bed Grid for Reception."""
    beds = Bed.objects.all().order_by('bed_number')
    return render(request, 'ipd/bed_dashboard.html', {'beds': beds})

@login_required
def admitted_patients_list(request):
    admissions = IPD_Admission.objects.filter(is_discharged=False).order_by('-admission_date')
    return render(request, 'ipd/admitted_list.html', {'admissions': admissions})

@login_required
def ipd_patient_profile(request, adm_id):
    admission = get_object_or_404(IPD_Admission, id=adm_id)
    
    # Today Date COmparisam
    today = timezone.now().date()
    
    if request.method == 'POST':
        record_id = request.POST.get('record_id') # Hidden field form se
        vitals = request.POST.get('vitals')
        saline = request.POST.get('saline')
        injection = request.POST.get('injection')
        notes = request.POST.get('notes')

        if record_id:
            # 🟢 Edit Existing Record Logic
            record = get_object_or_404(IPD_DailyRecord, id=record_id, admission=admission)
            # Security Check: Sirf aaj ka record hi edit ho sakega
            if record.date == today:
                record.vitals = vitals
                record.saline_details = saline
                record.injection_details = injection
                record.other_notes = notes
                record.save()
        else:
            # 🟢 Create New Record Logic
            IPD_DailyRecord.objects.create(
                admission=admission, 
                date=today,
                saline_details=saline,
                injection_details=injection, 
                vitals=vitals, 
                other_notes=notes
            )      
        return redirect('pulsehospital:ipd_patient_profile', adm_id=admission.id)

    # Records fetch 
    records = admission.daily_records.all().order_by('-date', '-id')
    context = {
        'admission': admission, 
        'records': records,
        'today': today # Template mein {% if record.date == today %} ke liye
    }
    return render(request, 'ipd/patient_profile.html', context)

@login_required
def ipd_discharge_history(request):
    """Shows list of all patients who have been discharged with search and date filters."""
    # Base query for all discharged patients
    history = IPD_Admission.objects.filter(is_discharged=True).order_by('-discharge_date')
    
    query = request.GET.get('q') # Search by Name or ID
    filter_date = request.GET.get('date') # Filter by Discharge Date

    if query:
        # Filter across patient name or admission ID
        history = history.filter(
            Q(patient__name__icontains=query) | Q(admission_id__icontains=query)
        )
    
    if filter_date:
        # Filter specifically by the discharge date (ignoring time)
        history = history.filter(discharge_date__date=filter_date)
        
    return render(request, 'ipd/ipd_discharge_history.html', {
        'history': history,
        'query': query,
        'filter_date': filter_date
    })


    #Reception Daily report
@login_required
def daily_report(request):
    # Get parameters from request
    selected_date = request.GET.get('date', str(date.today()))
    doctor_id = request.GET.get('doctor_filter', '')
    search_query = request.GET.get('report_q', '').strip()

    # Initial queryset
    report_data = Appointment.objects.all().order_by('-appointment_date', 'appointment_time')

    # Priority 1: Global Search (Bypasses date/doctor filters if searching by Name/ID)
    if search_query:
        report_data = report_data.filter(
            Q(patient_name__icontains=search_query) | 
            Q(patient_profile__reg_number__icontains=search_query)
        )

    # Priority 2: Standard Filters (Applied only if search_query is empty)
    else:
        if selected_date:
            report_data = report_data.filter(appointment_date=selected_date)   
        if doctor_id:
            report_data = report_data.filter(assigned_doctor_id=doctor_id)
    context = {
        'report': report_data,
        'selected_date': selected_date,
        'doctors': Doctor.objects.all(),
        'selected_doctor': doctor_id,
        'search_query': search_query,
        'total_count': report_data.count()
    }
    return render(request, 'reception/reception_report.html', context)

@login_required
def discharge_history(request):
    # 1. GET request se date_filter parameter nikaalein
    date_query = request.GET.get('date_filter')
    discharges = DischargeSummary.objects.all().order_by('-date_of_discharge')
    if date_query:
        discharges = discharges.filter(date_of_discharge=date_query)    
    return render(request, 'doctor/discharge_history.html', {
        'discharges': discharges,
        'selected_date': date_query
    })

@login_required
def delete_appointment(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk, status='Pending')
    if request.method == 'POST':
        appointment.delete(); messages.warning(request, "Request deleted.")
    return redirect('pulsehospital:reception_dashboard')

#Pharamacy
def edit_medicine(request, pk):
    medicine = get_object_or_404(Medicine, pk=pk)
    if request.method == 'POST':
        medicine.name = request.POST.get('name'); medicine.composition = request.POST.get('composition'); medicine.save()
        messages.success(request, "Updated successfully.")
    return redirect('pulsehospital:pharmacy_dashboard')
def delete_medicine(request, pk):
    medicine = get_object_or_404(Medicine, pk=pk); medicine.delete()
    return redirect('pulsehospital:pharmacy_dashboard')
def bulk_delete_medicine(request):
    if request.method == 'POST':
        Medicine.objects.filter(id__in=request.POST.getlist('medicine_ids')).delete()
    return redirect('pulsehospital:pharmacy_dashboard')


# Direct print by reception
@login_required
def direct_print_discharge(request, reg_id):
    """Receptionist directly prints the card generated by the doctor"""
    # 1. Patient Profile dhoondo
    profile = get_object_or_404(PatientProfile, reg_number=reg_id)
    
    # 2. Doctor ka save kiya hua data uthao
    saved_record = DischargeSummary.objects.filter(patient=profile).last()
    
    # 3. Admission records (dates ke liye)
    ipd_record = IPD_Admission.objects.filter(patient=profile).last()
    if not saved_record:
        messages.error(request, "Discharge Summary has not been prepared by the Doctor yet.")
        return redirect('pulsehospital:ipd_discharge_history')
    context = {
        'data': {
            'profile': profile,
            'record': saved_record,
        },
        'doctor_full_name': saved_record.doctor_name or "Consultant",
        'current_time': datetime.now(),
        'ipd': ipd_record
    }
    return render(request, 'ipd/direct_print_discharge.html', context)

# operation Theater Management

@login_required
def ot_management(request):
    doctor = get_object_or_404(Doctor, user=request.user)
    
    if request.method == 'POST':
        # Surgery Note Save Logic
        ot_id = request.POST.get('ot_id')
        ot_record = get_object_or_404(OTBooking, id=ot_id, doctor=doctor)
        ot_record.anaesthesia_type = request.POST.get('anaesthesia')
        ot_record.anaesthetist_name = request.POST.get('anaesthetist')
        ot_record.procedure_description = request.POST.get('procedure')
        ot_record.surgical_findings = request.POST.get('findings')
        ot_record.status = 'Completed'
        ot_record.save()
        
        messages.success(request, f"Operation Note for {ot_record.surgery_name} saved.")
        return redirect('pulsehospital:ot_management')

    # --- 🔍 Filter & Search Logic ---
    search_query = request.GET.get('q', '')
    # Agar date select nahi ki toh current date default hogi
    selected_date = request.GET.get('search_date') or str(timezone.now().date())
    
    # Filter by Doctor and Selected Date
    ot_list = OTBooking.objects.filter(doctor=doctor, ot_date=selected_date).order_by('ot_time')
    
    # Apply Search (Name or ID)
    if search_query:
        ot_list = ot_list.filter(
            Q(patient_name__icontains=search_query) | 
            Q(appointment__patient_name__icontains=search_query) |
            Q(reg_id_manual__icontains=search_query) |
            Q(appointment__patient_profile__reg_number__icontains=search_query)
        )
    
    return render(request, 'ot/ot_management.html', {
        'ot_list': ot_list,
        'selected_date': selected_date,
        'search_query': search_query
    })

@login_required
def schedule_ot_action(request, appt_id):
    if request.method == 'POST':
        appointment = get_object_or_404(Appointment, id=appt_id)
        doctor = get_object_or_404(Doctor, user=request.user)
        
        # OTBooking model yahan use ho raha hai
        OTBooking.objects.create(
            appointment=appointment,
            doctor=doctor,
            surgery_name=request.POST.get('surgery_name'),
            ot_date=request.POST.get('ot_date'),
            ot_time=request.POST.get('ot_time'),
            notes=request.POST.get('ot_notes')
        )
        messages.success(request, "OT Scheduled successfully.")
        return redirect('pulsehospital:ot_management')
    
#OT Form PRint
@login_required
def print_operation_note(request, ot_id):
    ot_record = get_object_or_404(OTBooking, id=ot_id)
    return render(request, 'ot/print_op_note.html', {'ot': ot_record})

@login_required
def ot_scheduling_form(request):
    doctor = get_object_or_404(Doctor, user=request.user)
    if request.method == 'POST':
        # 1. Manual Form Data fetch
        p_name = request.POST.get('patient_name')
        p_mobile = request.POST.get('patient_mobile')
        p_age = request.POST.get('patient_age')
        p_gender = request.POST.get('patient_gender')
        p_reg = request.POST.get('reg_id') # Manual entry field
        s_name = request.POST.get('surgery_name')
        a_name = request.POST.get('anaesthetist_name')
        o_date = request.POST.get('ot_date')
        o_time = request.POST.get('ot_time')
        a_mode = request.POST.get('anaesthesia')
        o_notes = request.POST.get('notes')

       # Manual Surgeon Name fetch 
        p_surgeon = request.POST.get('assistant_surgeon')

        # 2. Logic: Validation Check 
        if not p_name or not p_mobile or not s_name or not o_date:
            messages.error(request, "Please fill all mandatory fields.")
            return render(request, 'ot/ot_scheduling_form.html')

        # 3. Logic: Date Validation 
        if o_date < str(timezone.now().date()):
            messages.error(request, "Surgery cannot be scheduled for a past date.")
            return render(request, 'ot/ot_scheduling_form.html')

        # 4. Database mein Save karna
        try:
            OTBooking.objects.create(
                doctor=doctor,
                patient_name=p_name,
                patient_mobile=p_mobile,
                patient_age=p_age,
                patient_gender=p_gender,
                reg_id_manual=p_reg, 
                surgery_name=s_name,
                anaesthetist_name=a_name,
                ot_date=o_date,
                ot_time=o_time,
                anaesthesia_type=a_mode,
                pre_op_diagnosis=o_notes,
                # 🟢 Manual Surgeon Name yahan save ho raha hai
                assistant_surgeon=p_surgeon 
            )
            messages.success(request, f"OT Slot confirmed for {p_name} on {o_date}")
            return redirect('pulsehospital:ot_management')
        except Exception as e:
            messages.error(request, f"Error while booking: {e}")     
    return render(request, 'ot/ot_scheduling_form.html')

@login_required
def get_patient_details(request):
    query = request.GET.get('q', '').strip()
    # Database se Reg ID ya Phone ke basis par verified patient dhundna
    appointment = Appointment.objects.filter(
        Q(patient_profile__reg_number__iexact=query) | 
        Q(patient_profile__phone=query),
        status='Confirmed' # Sirf active patients dikhao
    ).first()
    if appointment:
        return JsonResponse({
            'success': True,
            'id': appointment.id,
            'name': appointment.patient_name.upper()
        })
    return JsonResponse({'success': False})


# 1. Upcoming Surgeries View (Sirf Scheduled status)
@login_required
def reception_ot_scheduled(request):
    query_date = request.GET.get('search_date') or str(date.today())
    search_query = request.GET.get('q', '')
    
    # Sirf 'Scheduled' status aur date filter
    ot_list = OTBooking.objects.filter(status='Scheduled', ot_date=query_date).order_by('ot_time')
    if search_query:
        ot_list = ot_list.filter(
            Q(patient_name__icontains=search_query) | 
            Q(appointment__patient_name__icontains=search_query) |
            Q(reg_id_manual__icontains=search_query)
        )
    return render(request, 'ot/reception_ot_scheduled.html', {
        'ot_list': ot_list,
        'selected_date': query_date,
        'search_query': search_query
    })

# 2. Completed Surgeries View (Sirf Completed status)
@login_required
def reception_ot_completed(request):
    query_date = request.GET.get('search_date')
    search_query = request.GET.get('q', '')
    
    # Base filter: Status 'Completed' honi chahiye
    ot_list = OTBooking.objects.filter(status='Completed')
    
    # Date filter apply karein
    if query_date:
        ot_list = ot_list.filter(ot_date=query_date)
    else:
        query_date = str(date.today())
        ot_list = ot_list.filter(ot_date=query_date)

    # 🟢 Registration ID aur Name search logic (Null Safe)
    if search_query:
        ot_list = ot_list.filter(
            Q(patient_name__icontains=search_query) | 
            Q(reg_id_manual__icontains=search_query) |
            Q(appointment__patient_name__icontains=search_query) |
            Q(appointment__patient_profile__reg_number__icontains=search_query)
        )
    
    ot_list = ot_list.order_by('-ot_time')
    
    return render(request, 'ot/reception_ot_completed.html', {
        'ot_list': ot_list,
        'selected_date': query_date,
        'search_query': search_query
    })

# Invoice generate

@login_required
def create_bill(request):
    query = request.GET.get('q')
    admission = None
    bill = None 
    if query:
        admission = IPD_Admission.objects.filter(
            Q(patient__phone=query) | Q(patient__reg_number=query)
        ).first()
    if request.method == "POST":
        admission_id = request.POST.get('admission_id')
        admission = get_object_or_404(IPD_Admission, id=admission_id)
        
        # 🟢 Sequential Bill Numbering Logic
        last_bill_count = Bill.objects.all().count()
        new_bill_no = f"INV-{last_bill_count + 1:02d}" 
        
        # 🟢 Correcting the attribute name as per your model
        discharging_doctor = admission.attending_doctor # ✅ Fixed from assigned_doctor

        bill = Bill.objects.create(
            bill_number=new_bill_no,
            patient=admission.patient,
            admission=admission,
            discharged_by=discharging_doctor, 
            consultation_charges=request.POST.get('consultation', 0) or 0,
            ward_charges=request.POST.get('ward_charges', 0) or 0,
            ot_charges=request.POST.get('ot_charges', 0) or 0,
            medicine_charges=request.POST.get('medicine', 0) or 0,
            other_charges=request.POST.get('other', 0) or 0,
            total_amount=request.POST.get('total_hidden', 0),
            payment_mode=request.POST.get('payment_mode'),
            transaction_id=request.POST.get('transaction_id', '-')
        )
        
        return render(request, 'Billing/create_bill.html', {
            'admission': admission, 
            'bill': bill,
            'query': query,
            'today': timezone.now(),
            'saved_success': True 
        })

    return render(request, 'Billing/create_bill.html', {
        'admission': admission, 
        'query': query,
        'today': timezone.now()
    })

@login_required
def bill_history(request):
    """ Optional: View to see all generated bills """
    bills = Bill.objects.all().order_by('-bill_date')
    return render(request, 'Billing/bill_history.html', {'bills': bills})

# 🟢 New View for Direct Print Popup
@login_required
def print_bill(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    return render(request, 'Billing/print_bill.html', {'bill': bill})




# Rest Framework api testing
# Rest Framework
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Medicine
from .serializers import MedicineSerializer
from .serializers import AppointmentSerializer, DoctorSerializer
from .serializers import BookAppointmentSerializer
from .serializers import IPDAdmissionSerializer, BillSerializer
from .models import Bill
from .serializers import (
    BedSerializer, AdmitPatientSerializer, IPDAdmissionSerializer, 
    OTBookingSerializer, AppointmentSerializer
)
from .models import Bed, IPD_Admission, OTBooking, Appointment
from .serializers import PatientProfileSerializer
from .serializers import IPDDailyRecordSerializer
from .models import IPD_Admission, IPD_DailyRecord
from .serializers import DischargeSummarySerializer, OTActionSerializer


@api_view(['GET'])
@permission_classes([AllowAny]) # Login zaroori hai
def medicine_api_list(request):
    # 🕵️‍♂️ DEBUG: Terminal mein check karein ye print hota hai ya nahi
    print("---------------------------------------")
    print("DEBUG: API Function Call Hua!")
    # 1. Search parameter uthao
    search_query = request.GET.get('search')
    print(f"DEBUG: Search Query Mila: '{search_query}'")

    # 2. Filter Logic
    if search_query:
        medicines = Medicine.objects.filter(
            Q(name__icontains=search_query) | 
            Q(composition__icontains=search_query)
        )
    else:
        medicines = Medicine.objects.all()

    # 🕵️‍♂️ DEBUG: Count check
    print(f"DEBUG: Total Medicines Found: {medicines.count()}")
    print("---------------------------------------")

    # 3. Serializer (HTML nahi, JSON bhejo)
    serializer = MedicineSerializer(medicines, many=True)
    
    return Response(serializer.data)



@api_view(['POST'])
@permission_classes([AllowAny]) 
def login_api(request):
    # 1. App se Username/Password lo
    username = request.data.get('username')
    password = request.data.get('password')

    # 2. Check karo user sahi hai ya nahi
    user = authenticate(username=username, password=password)

    if user is not None:
        # 3. Token banao ya purana wala lao
        token, created = Token.objects.get_or_create(user=user)
        
        # 4. Role Pata karo 
        role = 'unknown'
        
        # Check karte hain ki ye user kis table mein hai
        if hasattr(user, 'doctor'): 
            role = 'doctor'
        elif hasattr(user, 'pharmacist'):
            role = 'pharmacist'
        elif hasattr(user, 'receptionist'): 
            role = 'receptionist'
        # Superuser check (Optional)
        if user.is_superuser:
            role = 'admin'

        # 5. Token aur Role wapas bhejo
        return Response({
            'status': 'success',
            'token': token.key,
            'role': role,
            'username': user.username
        })
    else:
        return Response({'status': 'error', 'message': 'Invalid Username or Password'}, status=401)
    

# Logged in Doctor
@api_view(['GET'])
@permission_classes([IsAuthenticated]) # Sirf Logged in Doctor dekh sakega
def doctor_dashboard_api(request):
    
    # 1. Check karo ki User Doctor hai ya nahi
    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response({'error': 'You are not authorized as a Doctor'}, status=403)

    today = date.today()
    
    # --- 2. FILTERS (Search & Date)---
    query = request.GET.get('q') 
    selected_date = request.GET.get('date')
    
    # Base Query: Sirf is Doctor ki Confirmed Appointments
    appointments_queue = Appointment.objects.filter(assigned_doctor=doctor, status='Confirmed')

    # Filter Logic
    if query:
        # Naam ya Reg ID se search
        appointments_queue = appointments_queue.filter(
            Q(patient_name__icontains=query) | Q(patient_profile__reg_number__icontains=query)
        )
    elif selected_date:
        # Date select ki hai toh wo dikhao
        appointments_queue = appointments_queue.filter(appointment_date=selected_date)
    else:
        # Default: Aaj ki list
        appointments_queue = appointments_queue.filter(appointment_date=today)

    # --- 3. Statistics (Monthly Count) ---
    monthly_count = Appointment.objects.filter(
        assigned_doctor=doctor, status='Completed',
        appointment_date__month=today.month, appointment_date__year=today.year
    ).count()

    # --- 4. Completed Patients (Jo check ho chuke hain) ---
    completed_today = Appointment.objects.filter(
        assigned_doctor=doctor, status='Completed', appointment_date=today
    ).order_by('-booked_on')

    # --- 5. Data Pack karo (Serialization) ---
    queue_serializer = AppointmentSerializer(appointments_queue.order_by('appointment_time'), many=True)
    completed_serializer = AppointmentSerializer(completed_today, many=True)
    doctor_serializer = DoctorSerializer(doctor)

    # --- 6. Final JSON Response ---
    return Response({
        'doctor_info': doctor_serializer.data,
        'stats': {
            'monthly_patient_count': monthly_count,
            'current_month': today.strftime('%B'),
            'today_queue_count': appointments_queue.count()
        },
        'appointments_queue': queue_serializer.data,   
        'completed_list': completed_serializer.data  
    })

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def patient_checkup_api(request, pk):
    # 1. Appointment dhundo
    try:
        appointment = Appointment.objects.get(pk=pk)
    except Appointment.DoesNotExist:
        return Response({'error': 'Appointment not found'}, status=404)

    # Security: Check karo ki ye usi doctor ka patient hai
    doctor = Doctor.objects.get(user=request.user)
    if appointment.assigned_doctor != doctor:
        return Response({'error': 'Not authorized to treat this patient'}, status=403)

    # --- 🟢 GET Request: Data Dikhana (History + Details) ---
    if request.method == 'GET':
        # Patient ki purani history nikalo (Completed wali)
        history = Appointment.objects.filter(
            patient_profile=appointment.patient_profile, 
            status='Completed'
        ).exclude(id=pk).order_by('-appointment_date')
        
        # History ko JSON banayenge
        history_serializer = AppointmentSerializer(history, many=True)
        current_serializer = AppointmentSerializer(appointment)

        return Response({
            'patient_details': current_serializer.data,
            'past_history': history_serializer.data,
            # Agar pehle se kuch save hai to wo bhi bhejo
            'saved_diagnosis': appointment.diagnosis,
            'saved_symptoms': appointment.symptoms,
            'saved_medication': appointment.medication_json
        })

    # --- 🔴 POST Request: Data Save Karna (Prescription) ---
    elif request.method == 'POST':
        # App se data aayega
        data = request.data 

        # 1. Basic Fields update
        appointment.diagnosis = data.get('diagnosis', '')
        appointment.symptoms = data.get('symptoms', '')
        appointment.other_comorbidities = data.get('other_comorbidities', '')
        
        # 2. Medicine List (JSON Format mein aayegi)
        # App bhejege: [{"name": "Dolo", "dose": "1-0-1"}, ...]
        medicines = data.get('medication_json')
        if medicines:
            appointment.medication_json = medicines # Direct JSON save
        
        # 3. Status Complete karo
        appointment.status = 'Completed'
        appointment.save()

        return Response({'status': 'success', 'message': 'Prescription Saved Successfully!'})

# --- A. RECEPTION DASHBOARD API ---
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reception_dashboard_api(request):
    today = date.today()

    # 1. Stats Calculate karo
    pending_count = Appointment.objects.filter(status='Pending').count()
    confirmed_today = Appointment.objects.filter(status='Confirmed', appointment_date=today).count()
    completed_today = Appointment.objects.filter(status='Completed', appointment_date=today).count()
    
    # 2. Doctors List (Availability dikhane ke liye)
    doctors = Doctor.objects.all()
    doctor_data = []
    for dr in doctors:
        # Har doctor ke aaj ke patients count karo
        patient_count = Appointment.objects.filter(
            assigned_doctor=dr, 
            appointment_date=today, 
            status='Confirmed'
        ).count()
        
        doctor_data.append({
            'id': dr.id,
            'name': dr.name,
            'specialty': dr.specialty,
            'today_patients': patient_count
        })

    # 3. JSON Response
    return Response({
        'stats': {
            'pending_requests': pending_count,
            'confirmed_today': confirmed_today,
            'completed_today': completed_today,
            'total_today': confirmed_today + completed_today
        },
        'doctors_status': doctor_data,
        'today_date': today.strftime("%d %B %Y")
    })


# --- B. BOOK APPOINTMENT API (Walk-in) ---
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def book_appointment_api(request):
    serializer = BookAppointmentSerializer(data=request.data)
    
    if serializer.is_valid():
        data = serializer.validated_data
        
        # 1. Doctor dhundo
        try:
            doctor_obj = Doctor.objects.get(id=data['doctor_id'])
        except Doctor.DoesNotExist:
            return Response({'error': 'Invalid Doctor ID'}, status=400)

        # 2. Patient Profile
        dr_code = 'GYN' if 'gynec' in doctor_obj.specialty.lower() else 'MED'
        
        profile, created = PatientProfile.objects.get_or_create(
            phone=data['phone'],
            defaults={
                'name': data['patient_name'],
                'age': data['age'],
                'gender': data.get('gender', 'M'), # ✅ Yahan Gender hona chahiye
                'address': data.get('address', ''),
                'assigned_doctor_code': dr_code
            }
        )
        
        if not created:
            profile.age = data['age']
            profile.address = data.get('address', '')
            profile.save()

        # 3. Appointment Create 
        Appointment.objects.create(
            patient_name=data['patient_name'],
            phone=data['phone'],
            age=data['age'],
            patient_profile=profile,
            assigned_doctor=doctor_obj,
            appointment_date=date.today(),
            appointment_time=datetime.now().time(),
            status='Confirmed',
            is_follow_up=not created,
            bp=data.get('bp', ''),
            pulse=data.get('pulse', ''),
            sugar=data.get('sugar', '')
        )

        return Response({'status': 'success', 'message': 'Appointment Booked Successfully!'})
    
    return Response(serializer.errors, status=400)



# --- A. SEARCH ADMITTED PATIENT (GET) ---
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_admitted_patient_api(request):
    query = request.GET.get('search')
    
    if query:
        # find Phone or Reg Number 
        admissions = IPD_Admission.objects.filter(
            Q(patient__phone__icontains=query) | 
            Q(patient__reg_number__icontains=query),
            is_discharged=False # Sirf jo abhi admitted hain
        )
        serializer = IPDAdmissionSerializer(admissions, many=True)
        return Response(serializer.data)
    
    return Response([])

# --- B. CREATE BILL API (POST) ---
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_bill_api(request):
    # 1. INV Number Generate Logic
    last_bill_count = Bill.objects.all().count()
    new_bill_no = f"INV-{last_bill_count + 1:02d}"
    
    # 2. Data Tayyar karo
    data = request.data.copy()
    data['bill_number'] = new_bill_no
    
    # 3. Admission ID se Doctor Pata karo (Discharged By)
    try:
        admission = IPD_Admission.objects.get(id=data.get('admission'))
        # Discharging doctor wahi hoga jo admission ke waqt tha
        discharging_doctor = admission.attending_doctor 
    except IPD_Admission.DoesNotExist:
        return Response({'error': 'Invalid Admission ID'}, status=400)

    # 4. Save Bill
    serializer = BillSerializer(data=data)
    if serializer.is_valid():
        bill = serializer.save(
            bill_number=new_bill_no,
            patient=admission.patient,
            discharged_by=discharging_doctor # Doctor name save
        )
        return Response({
            'status': 'success', 
            'message': 'Bill Generated Successfully!',
            'bill_number': bill.bill_number,
            'total': bill.total_amount
        })
    
    return Response(serializer.errors, status=400)


# A. Bed Status (Red/Green Grid)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def bed_dashboard_api(request):
    beds = Bed.objects.all().order_by('bed_number')
    serializer = BedSerializer(beds, many=True)
    
    return Response({
        'stats': {
            'total': beds.count(),
            'occupied': beds.filter(is_occupied=True).count(),
            'available': beds.filter(is_occupied=False).count()
        },
        'beds': serializer.data
    })

# B. Admit Patient (Action)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admit_patient_api(request):
    serializer = AdmitPatientSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data
        try:
            patient = PatientProfile.objects.get(id=data['patient_id'])
            bed = Bed.objects.get(id=data['bed_id'])
            
            if bed.is_occupied:
                return Response({'error': 'Bed is already occupied!'}, status=400)

            # Admission Create karo
            IPD_Admission.objects.create(
                patient=patient,
                admission_id=patient.reg_number, # Logic same as website
                bed=bed,
                attending_doctor_id=data['doctor_id'],
                diagnosis=data.get('diagnosis', ''),
                admission_date=timezone.now()
            )
            
            # Bed Block karo
            bed.is_occupied = True
            bed.save()
            
            return Response({'status': 'success', 'message': f'Patient Admitted to Bed {bed.bed_number}'})
            
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    return Response(serializer.errors, status=400)


# ==========================================
# 🕒 2. PENDING REQUESTS MANAGEMENT
# ==========================================

# A. List Pending Requests
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_requests_api(request):
    # Website logic: Filter status='Pending'
    pending = Appointment.objects.filter(status='Pending').order_by('-booked_on')
    serializer = AppointmentSerializer(pending, many=True)
    return Response(serializer.data)

# B. Confirm Appointment (Action)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_request_api(request, pk):
    try:
        appointment = Appointment.objects.get(pk=pk, status='Pending')
        doctor_id = request.data.get('doctor_id') # Receptionist select karegi doctor
        
        if not doctor_id:
            return Response({'error': 'Please select a Doctor'}, status=400)

        # 1. Doctor Assign karo
        doctor_obj = Doctor.objects.get(id=doctor_id)
        appointment.assigned_doctor = doctor_obj
        
        # 2. Patient Profile Create/Get karo (Reg ID generate hogi)
        dr_code = 'GYN' if 'gynec' in doctor_obj.specialty.lower() else 'MED'
        profile, created = PatientProfile.objects.get_or_create(
            phone=appointment.phone,
            defaults={
                'name': appointment.patient_name,
                'age': appointment.age,
                'assigned_doctor_code': dr_code
            }
        )
        
        # 3. Status Update
        appointment.patient_profile = profile
        appointment.status = 'Confirmed'
        appointment.is_follow_up = not created
        appointment.save()
        
        return Response({'status': 'success', 'message': 'Appointment Confirmed!'})

    except Appointment.DoesNotExist:
        return Response({'error': 'Request not found'}, status=404)


# ==========================================
# 🔪 3. OT SCHEDULE API
# ==========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ot_schedule_api(request):
    today = date.today()
    # Logic: Aaj ki aur aane wali surgeries dikhao
    upcoming_ot = OTBooking.objects.filter(
        ot_date__gte=today, 
        status='Scheduled'
    ).order_by('ot_date', 'ot_time')
    
    serializer = OTBookingSerializer(upcoming_ot, many=True)
    return Response(serializer.data)


# 🟢 MASTER PATIENT SEARCH (General Search)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_patient_profile_api(request):
    query = request.GET.get('search')
    
    if query:
        # Patient ko Naam, Phone ya Reg ID se dhundo
        patients = PatientProfile.objects.filter(
            Q(name__icontains=query) | 
            Q(phone__icontains=query) | 
            Q(reg_number__icontains=query)
        )
        
        # Yahan hum wo Serializer use kar rahe hain jo 'miss' ho gaya tha
        serializer = PatientProfileSerializer(patients, many=True)
        return Response(serializer.data)
    
    return Response([])

# 🟢 RECEPTION: IPD DAILY ROUNDS (Treatment Entry)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def ipd_daily_round_api(request, admission_id):
    # 1. Pehle check karo Admission exist karta hai ya nahi
    try:
        admission = IPD_Admission.objects.get(id=admission_id)
    except IPD_Admission.DoesNotExist:
        return Response({'error': 'Admission Record Not Found'}, status=404)

    # --- A. GET REQUEST: History Dekhna ---
    if request.method == 'GET':
        # Sirf isi patient ke records nikalo, naya pehle (Reverse order)
        records = IPD_DailyRecord.objects.filter(admission=admission).order_by('-date', '-id')
        serializer = IPDDailyRecordSerializer(records, many=True)
        return Response({
            'patient_name': admission.patient.name,
            'bed_number': admission.bed.bed_number,
            'records': serializer.data
        })

    # --- B. POST REQUEST: Naya Treatment Add Karna ---
    elif request.method == 'POST':
        serializer = IPDDailyRecordSerializer(data=request.data)
        
        if serializer.is_valid():
            # 🟢 Important: Admission object hum code se jodenge (User se nahi mangenge)
            serializer.save(admission=admission, date=date.today())
            return Response({'status': 'success', 'message': 'Daily Treatment Record Added!'})
        
        return Response(serializer.errors, status=400)


# 🟢 RECEPTION: DISCHARGE PATIENT API
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def discharge_patient_api(request, admission_id):
    try:
        # 1. Admission Record dhundo
        admission = IPD_Admission.objects.get(id=admission_id, is_discharged=False)
        
        # 2. Bed dhundo jo is patient ke paas hai
        bed = admission.bed
        
        # 3. Discharge Updates
        admission.is_discharged = True
        admission.discharge_date = timezone.now()
        admission.save()
        
        # 4. Bed Free karo (Green Signal 🟢)
        bed.is_occupied = False
        bed.save()
        
        return Response({
            'status': 'success', 
            'message': f'Patient Discharged. Bed {bed.bed_number} is now Available.'
        })

    except IPD_Admission.DoesNotExist:
        return Response({'error': 'Patient already discharged or Invalid ID'}, status=400)
    

    # 📄 DOCTOR: DISCHARGE SUMMARY
# ==========================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_discharge_summary_api(request):
    # Patient Reg ID se dhundenge (Mobile se Reg ID aayegi)
    reg_id = request.data.get('reg_id')
    
    try:
        profile = PatientProfile.objects.get(reg_number=reg_id)
        
        # Data prepare karo
        data = request.data.copy()
        data['patient'] = profile.id
        data['doctor_name'] = request.user.get_full_name()
        
        # Save karo
        serializer = DischargeSummarySerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            
            # Optional: Agar Discharge Summary ban gayi, toh Bed release signal de sakte hain
            # Lekin usually Doctor summary banata hai, Reception discharge karti hai.
            
            return Response({'status': 'success', 'message': 'Discharge Summary Saved!'})
        return Response(serializer.errors, status=400)
        
    except PatientProfile.DoesNotExist:
        return Response({'error': 'Invalid Registration Number'}, status=404)


# ==========================================
# 🔪 DOCTOR: OT MANAGEMENT
# ==========================================

# 1. Book Surgery (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def book_surgery_api(request):
    # Doctor ID user se lenge
    try:
        doctor = Doctor.objects.get(user=request.user)
        data = request.data.copy()
        data['doctor'] = doctor.id
        
        serializer = OTActionSerializer(data=data)
        if serializer.is_valid():
            serializer.save(status='Scheduled')
            return Response({'status': 'success', 'message': 'Surgery Scheduled!'})
        return Response(serializer.errors, status=400)
    except Doctor.DoesNotExist:
        return Response({'error': 'You are not a Doctor'}, status=403)

# 2. Save OT Notes & Complete (POST)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_ot_notes_api(request, ot_id):
    try:
        ot_record = OTBooking.objects.get(id=ot_id)
        
        ot_record.procedure_description = request.data.get('procedure')
        ot_record.surgical_findings = request.data.get('findings')
        ot_record.anaesthesia_type = request.data.get('anaesthesia')
        ot_record.status = 'Completed' # 🟢 Status Complete ho jayega
        ot_record.save()
        
        return Response({'status': 'success', 'message': 'Operation Notes Saved & Completed!'})
    except OTBooking.DoesNotExist:
        return Response({'error': 'OT Record not found'}, status=404)