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
from django.views.decorators.clickjacking import xframe_options_exempt

from django.contrib.auth.models import User
def fix_admin(request):
    user = User.objects.filter(username='admin').first()
    if user:
        user.set_password('admin123')   # 🔥 password re-hash karega
        user.save()
        return HttpResponse("Password reset done")
    return HttpResponse("User not found")

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
    
    # 1. Monthly Count (Existing)
    monthly_count = Appointment.objects.filter(
        assigned_doctor=doctor, 
        status='Completed',
        appointment_date__month=today.month, 
        appointment_date__year=today.year
    ).count()

    # 🟢 2. NEW: Count Active IPD Patients (Admitted & Not Discharged)
    ipd_count = IPD_Admission.objects.filter(
        attending_doctor=doctor, 
        is_discharged=False
    ).count()

    # --- FILTER LOGIC (Existing) ---
    query = request.GET.get('q') 
    selected_date = request.GET.get('date') 
    
    appointments_queue = Appointment.objects.filter(assigned_doctor=doctor, status='Confirmed')

    if query:
        appointments_queue = appointments_queue.filter(
            Q(patient_name__icontains=query) | 
            Q(patient_profile__reg_number__icontains=query)
        )
    elif selected_date:
        appointments_queue = appointments_queue.filter(appointment_date=selected_date)
    else:
        appointments_queue = appointments_queue.filter(appointment_date=today)

    completed_today = Appointment.objects.filter(
        assigned_doctor=doctor, status='Completed', appointment_date=today
    ).order_by('-booked_on')
    
    return render(request, 'doctor/doctor_dashboard.html', {
        'doctor': doctor, 
        'appointments': appointments_queue.order_by('appointment_time'),
        'completed_today': completed_today, 
        'monthly_patient_count': monthly_count,
        'ipd_count': ipd_count,          # 🟢 Pass count to HTML
        'current_month_name': today.strftime('%B'),
        'selected_date': selected_date or str(today)
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

@xframe_options_exempt
@login_required
def generate_discharge_card(request):
    reg_id = request.GET.get('reg_id')
    discharge_id = request.GET.get('discharge_id')
    
    patient_data = None
    final_discharge_date = timezone.now()

    def parse_meds(json_str):
        try: return json.loads(json_str) if json_str else []
        except: return []

    def get_last_visit(profile):
        return Appointment.objects.filter(patient_profile=profile).last()

    if discharge_id:
        saved_record = get_object_or_404(DischargeSummary, id=discharge_id)
        profile = saved_record.patient
        reg_id = profile.reg_number 
        final_discharge_date = saved_record.date_of_discharge
        
        # 🟢 ADDED: Admission record fetch karna
        admission_rec = IPD_Admission.objects.filter(patient=profile).last()

        patient_data = {
            'profile': profile, 
            'is_saved': True, 
            'record': saved_record,
            'admission': admission_rec,  # ✅ Yeh key missing thi
            'last_visit': get_last_visit(profile),
            'hosp_meds': parse_meds(saved_record.treatment_given),
            'home_meds': parse_meds(saved_record.treatment_advised)
        }

    elif reg_id:
        profile = PatientProfile.objects.filter(reg_number=reg_id).first()
        if not profile:
            admission = IPD_Admission.objects.filter(admission_id=reg_id).first()
            if admission: profile = admission.patient

        if profile:
            saved_record = DischargeSummary.objects.filter(patient=profile).last()
            admission_rec = IPD_Admission.objects.filter(patient=profile).last() # Fetch admission

            if saved_record:
                final_discharge_date = saved_record.date_of_discharge
                patient_data = {
                    'profile': profile, 
                    'is_saved': True, 
                    'record': saved_record,
                    'admission': admission_rec, # ✅ Yeh key add ki
                    'last_visit': get_last_visit(profile),
                    'hosp_meds': parse_meds(saved_record.treatment_given),
                    'home_meds': parse_meds(saved_record.treatment_advised)
                }
            else:
                initial_record_data = {}
                if admission_rec:
                    initial_record_data['date_of_admission'] = admission_rec.admission_date
                
                patient_data = {
                    'profile': profile, 
                    'is_saved': False, 
                    'admission': admission_rec, # ✅ Yeh key add ki
                    'last_visit': get_last_visit(profile),
                    'record': initial_record_data, 
                    'hosp_meds': [], 
                    'home_meds': []
                }

    # 🟢 LOGIC C: SAVE DATA (POST)
    if request.method == 'POST':
        patient_profile = get_object_or_404(PatientProfile, id=request.POST.get('patient_id'))
        active_admission = IPD_Admission.objects.filter(patient=patient_profile, is_discharged=False).first()
        if active_admission:
            if active_admission.bed:
                bed_obj = active_admission.bed
                bed_obj.is_occupied = False
                bed_obj.save()
            active_admission.is_discharged = True
            if not active_admission.discharge_date:
                active_admission.discharge_date = timezone.now()
            active_admission.save()

        DischargeSummary.objects.update_or_create(
            patient=patient_profile,
            id=discharge_id if discharge_id else None, 
            defaults={
                'doctor_name': request.user.get_full_name() or request.user.username,
                'date_of_admission': request.POST.get('adm_date'), 
                'presenting_complaints': request.POST.get('presenting_complaints'),
                'final_diagnosis': request.POST.get('final_diagnosis'),
                'hb': request.POST.get('hb'), 'tlc': request.POST.get('tlc'),
                'platelets': request.POST.get('platelets'), 'bul': request.POST.get('bul'),
                'creatinine': request.POST.get('creatinine'), 'lft': request.POST.get('lft'),
                'xray': request.POST.get('xray'), 'ct_scan': request.POST.get('ct_scan'),
                'mri': request.POST.get('mri'),
                'condition_on_admission': request.POST.get('cond_admission'),
                'condition_on_discharge': request.POST.get('cond_discharge'),
                'treatment_given': request.POST.get('treatment_given_json', '[]'),
                'treatment_advised': request.POST.get('treatment_advised_json', '[]'),
                'discharge_advice': request.POST.get('discharge_advice'),
                'follow_up': request.POST.get('follow_up')
            }
        )
        messages.success(request, "Discharge Summary Saved Successfully!")
        return redirect(f"{request.path}?reg_id={patient_profile.reg_number}")

    return render(request, 'doctor/discharge_card.html', {
        'data': patient_data, 'reg_id': reg_id, 
        'discharge_date': final_discharge_date, 
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

@login_required
def doctor_admitted_patients(request):
    # 1. Check karein ki user Doctor hai ya nahi
    if not hasattr(request.user, 'doctor'):
        messages.error(request, "Access Denied. Doctors only.")
        return redirect('pulsehospital:dashboard')
    doctor = request.user.doctor
    admissions = IPD_Admission.objects.filter(
        attending_doctor=doctor, 
        is_discharged=False
    ).order_by('-admission_date')
    
    return render(request, 'doctor/ipd_list.html', {
        'admissions': admissions,
        'doctor': doctor
    })

@login_required
def doctor_view_ipd_history(request, adm_id):
    # 1. Admission Record 
    admission = get_object_or_404(IPD_Admission, id=adm_id)
    
    # 2. Security Check
    if admission.attending_doctor.user != request.user:
        messages.error(request, "You are not authorized to view this patient.")
        return redirect('pulsehospital:doctor_admitted_patients')

    # 3. Daily Records 
    records = admission.daily_records.all().order_by('-date', '-id')
    return render(request, 'doctor/ipd_details_view.html', {
        'admission': admission,
        'records': records
    })

@login_required
def doctor_view_ipd_history(request, adm_id):
    admission = get_object_or_404(IPD_Admission, id=adm_id)
    
    # Security Check
    if admission.attending_doctor.user != request.user:
        messages.error(request, "Authorized Access Only.")
        return redirect('pulsehospital:doctor_admitted_patients')

    # 🟢 LOGIC: Doctor Note Save Karna
    if request.method == "POST":
        record_id = request.POST.get('record_id')
        doc_note = request.POST.get('doctor_note')
        
        if record_id and doc_note:
            record = get_object_or_404(IPD_DailyRecord, id=record_id)
            
            # Current Time fetch karein (India Time)
            local_now = timezone.localtime(timezone.now())
            current_time_str = local_now.strftime("%I:%M %p")
            
            # Note ko format karein: [Time] (Doctor): Note
            new_entry = f"[{current_time_str}] (Dr. Remarks): {doc_note}"
            
            # Purane notes me append karein
            if record.other_notes:
                record.other_notes = f"{record.other_notes}\n{new_entry}"
            else:
                record.other_notes = new_entry
                
            record.save()
            messages.success(request, "Clinical Note Added Successfully")
            return redirect('pulsehospital:doctor_view_ipd_history', adm_id=admission.id)

    records = admission.daily_records.all().order_by('-date')
    
    return render(request, 'doctor/ipd_details_view.html', {
        'admission': admission,
        'records': records
    })


@login_required
def view_discharged_case(request, discharge_id):
    # 1. Discharge Summary Record nikalo
    discharge_record = get_object_or_404(DischargeSummary, id=discharge_id)
    patient = discharge_record.patient
    
    # 🟢 2. Admission Record Explicitly Find Karein (Jisme Bed Info hai)
    # Logic: Wo Admission jiska patient same ho aur discharge date match kare
    admission_obj = IPD_Admission.objects.filter(
        patient=patient,
        is_discharged=True
    ).order_by('-discharge_date').first() 
    # .first() latest wala uthayega agar dates match na bhi ho to

    # 3. Daily Records Fetching
    daily_records = IPD_DailyRecord.objects.filter(
        admission__patient=patient,
        date__gte=discharge_record.date_of_admission.date(),
        date__lte=discharge_record.date_of_discharge.date()
    ).order_by('-date')

    return render(request, 'doctor/discharged_case_view.html', {
        'discharge': discharge_record,
        'admission': admission_obj,  # <--- Ye naya variable template me bhej rahe hain
        'records': daily_records
    })

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
        bed_id = request.POST.get('bed_id')
        patient_id = request.POST.get('patient_id')
        
        bed_obj = get_object_or_404(Bed, id=bed_id)
        patient_obj = get_object_or_404(PatientProfile, id=patient_id)

        # 🟢 NEW DYNAMIC ADMISSION ID LOGIC
        # 1. Pehle check karein ki is patient ki pehle kitni admissions ho chuki hain
        previous_admissions_count = IPD_Admission.objects.filter(patient=patient_obj).count()
        
        # 2. Visit number generate karein (Pehli baar hai toh 1, doosri baar toh 2...)
        visit_number = previous_admissions_count + 1
        
        # 3. Format: IPD/MED-2026-001/1 (Ya 2, 3 jitni baar admit ho)
        # Isse database mein kabhi duplicate entry nahi aayegi
        adm_id = f"IPD/{patient_obj.reg_number}/{visit_number}"

        try:
            IPD_Admission.objects.create(
                patient=patient_obj, 
                admission_id=adm_id, 
                bed=bed_obj,
                attending_doctor_id=request.POST.get('doctor_id'), 
                diagnosis=request.POST.get('diagnosis'),
                admission_date=timezone.now()
            )
            
            # Bed ko block karein
            bed_obj.is_occupied = True
            bed_obj.save()
            
            messages.success(request, f"Patient Admitted Successfully! Admission ID: {adm_id}")
            return redirect('pulsehospital:admitted_patients_list')
            
        except Exception as e:
            messages.error(request, f"Admission Failed: {str(e)}")
            return redirect('pulsehospital:ipd_admission_form')

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
    today = timezone.now().date()
    local_now = timezone.localtime(timezone.now()) 
    today = local_now.date()
    current_time_str = local_now.strftime("%I:%M %p")
    if request.method == 'POST':
        # 1. Get Data from Form
        record_id = request.POST.get('record_id')
        bp = request.POST.get('bp', '')
        pulse = request.POST.get('pulse', '')
        spo2 = request.POST.get('spo2', '')
        temp = request.POST.get('temp', '')
        new_vitals_entry = f"[{current_time_str}] BP:{bp}, Pulse:{pulse}, SpO2:{spo2}, Temp:{temp}" if (bp or pulse) else ""
        saline = request.POST.get('saline', '').strip()
        injection = request.POST.get('injection', '').strip()
        notes = request.POST.get('notes', '').strip()

        # Logic to Append Time to Text
        def append_entry(old_text, new_text):
            if not new_text: return old_text
            entry = f"[{current_time_str}] {new_text}"
            if old_text:
                return f"{old_text}\n{entry}" 
            return entry

        # 🟢 CHECK: Kya Aaj ka Record Pehle se hai?
        existing_today_record = IPD_DailyRecord.objects.filter(admission=admission, date=today).first()

        if record_id:
            # --- EDIT MODE
            record = get_object_or_404(IPD_DailyRecord, id=record_id, admission=admission)
            record.vitals = request.POST.get('full_vitals_text') 
            record.saline_details = saline
            record.injection_details = injection
            record.other_notes = notes
            record.save()

        elif existing_today_record:
            # --- APPEND MODE  ---
            if new_vitals_entry:
                existing_today_record.vitals = append_entry(existing_today_record.vitals, f"BP:{bp}, P:{pulse}, SpO2:{spo2}, T:{temp}")
            
            existing_today_record.saline_details = append_entry(existing_today_record.saline_details, saline)
            existing_today_record.injection_details = append_entry(existing_today_record.injection_details, injection)
            existing_today_record.other_notes = append_entry(existing_today_record.other_notes, notes)
            existing_today_record.save()
            messages.success(request, f"Treatment updated for today at {current_time_str}")

        else:
            # --- CREATE MODE  ---
            IPD_DailyRecord.objects.create(
                admission=admission, 
                date=today,
                saline_details=f"[{current_time_str}] {saline}" if saline else "",
                injection_details=f"[{current_time_str}] {injection}" if injection else "", 
                vitals=new_vitals_entry, 
                other_notes=f"[{current_time_str}] {notes}" if notes else ""
            )
            messages.success(request, "New Daily Record Started")

        return redirect('pulsehospital:ipd_patient_profile', adm_id=admission.id)

    records = admission.daily_records.all().order_by('-date')
    return render(request, 'ipd/patient_profile.html', {
        'admission': admission, 
        'records': records,
        'today': today
    })

    # Records fetch 
    records = admission.daily_records.all().order_by('-date', '-id')
    context = {
        'admission': admission, 
        'records': records,
        'today': today 
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


# # Direct print by reception
@xframe_options_exempt
@login_required
def direct_print_discharge(request, reg_id):
    try:
        # 1. Patient Profile
        profile = PatientProfile.objects.filter(reg_number=reg_id).first()
        if not profile:
            # Agar patient nahi mila toh Iframe me alert bhejo
            return HttpResponse("<script>alert('Error: Patient Profile not found!');</script>")
        
        # 2. Discharge Summary (Check if Doctor has generated it)
        saved_record = DischargeSummary.objects.filter(patient=profile).last()
        if not saved_record:
            return HttpResponse("<script>alert('Error: Doctor ne abhi tak Discharge Summary generate nahi ki hai!');</script>")

        # 3. JSON Medicine Parse
        def parse_meds(json_str):
            try:
                return json.loads(json_str) if json_str else []
            except:
                return []
                
        hosp_meds = parse_meds(saved_record.treatment_given)
        home_meds = parse_meds(saved_record.treatment_advised)

        # 4. Context Send
        context = {
            'data': {
                'profile': profile,
                'record': saved_record,
            },
            'hosp_meds': hosp_meds,
            'home_meds': home_meds,
            'doctor_full_name': saved_record.doctor_name or "Consultant",
            'discharge_date': saved_record.date_of_discharge 
        }
        
        # 5. Render directly to print template
        return render(request, 'ipd/direct_print_discharge.html', context)
        
    except Exception as e:
        # Koi aur code error aaya toh alert aayega
        return HttpResponse(f"<script>alert('System Error: {str(e)}');</script>")
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
        # 🟢 .last() use kiya hai taaki latest admission record uthaye
        admission = IPD_Admission.objects.filter(
            Q(patient__phone=query) | Q(patient__reg_number=query)
        ).last()

    if request.method == "POST":
        admission_id = request.POST.get('admission_id')
        admission = get_object_or_404(IPD_Admission, id=admission_id)
        
        # Bill Numbering
        last_bill_count = Bill.objects.all().count()
        new_bill_no = f"INV-{last_bill_count + 1:02d}" 
        
        discharging_doctor = admission.attending_doctor

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
        
        # 🟢 saved_success flag template mein auto-print trigger karega
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

def bill_history(request):
    query = request.GET.get('q')
    bills = Bill.objects.all().order_by('-bill_date')
    
    if query:
        bills = bills.filter(
            Q(bill_number__icontains=query) | 
            Q(patient__name__icontains=query) | 
            Q(patient__reg_number__icontains=query) |
            Q(transaction_id__icontains=query)
        )
    
    return render(request, 'Billing/bill_history.html', {'bills': bills})

# 🟢 New View for Direct Print Popup
@xframe_options_exempt
@login_required
def print_bill(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    return render(request, 'Billing/print_bill.html', {'bill': bill})
