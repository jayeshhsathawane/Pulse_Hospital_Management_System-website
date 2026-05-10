from django.shortcuts import render
import csv
import io
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from datetime import date, datetime
from django.contrib import messages
from pulsehospital.models import (
    Appointment, Doctor, PatientProfile, Medicine, Symptom, 
    Receptionist, DischargeSummary, Pharmacist, IPD_Admission, 
    Bed, IPD_DailyRecord,OTBooking
)
from pulsehospital.forms import AppointmentForm
from django.core import serializers
from django.utils import timezone
from django.db.models import Q
from pulsehospital.models import Bill, IPD_Admission, Doctor 
from django.utils import timezone
import time
from django.views.decorators.clickjacking import xframe_options_exempt

# Rest Framework
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from pulsehospital.models import Medicine
from .serializers import MedicineSerializer
from .serializers import AppointmentSerializer, DoctorSerializer
from .serializers import BookAppointmentSerializer
from .serializers import IPDAdmissionSerializer, BillSerializer
from pulsehospital.models import Bill
from .serializers import (
    BedSerializer, AdmitPatientSerializer, IPDAdmissionSerializer, 
    OTBookingSerializer, AppointmentSerializer
)
from pulsehospital.models import Bed, IPD_Admission, OTBooking, Appointment
from .serializers import PatientProfileSerializer
from .serializers import IPDDailyRecordSerializer
from pulsehospital.models import IPD_Admission, IPD_DailyRecord
from .serializers import DischargeSummarySerializer, OTActionSerializer



@api_view(['GET'])
@permission_classes([AllowAny]) 
def medicine_api_list(request):
    #  DEBUG:
    print("---------------------------------------")
    print("DEBUG: API Function ")
    # 1. Search parameter uthao
    search_query = request.GET.get('search')
    print(f"DEBUG: Search Query: '{search_query}'")
    if search_query:
        medicines = Medicine.objects.filter(
            Q(name__icontains=search_query) | 
            Q(composition__icontains=search_query)
        )
    else:
        medicines = Medicine.objects.all()

    #  DEBUG: Count check
    print(f"DEBUG: Total Medicines Found: {medicines.count()}")
    print("---------------------------------------")
    # 3. Serializer (JSON )
    serializer = MedicineSerializer(medicines, many=True)
    
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny]) 
def login_api(request):
    # 1. App Username/Password 
    username = request.data.get('username')
    password = request.data.get('password')

    # 2. Check  user
    user = authenticate(username=username, password=password)
    if user is not None:
        # 3. Token 
        token, created = Token.objects.get_or_create(user=user)
    
        # 4. Role
        role = 'unknown'
        if hasattr(user, 'doctor'): 
            role = 'doctor'
        elif hasattr(user, 'pharmacist'):
            role = 'pharmacist'
        elif hasattr(user, 'receptionist'): 
            role = 'receptionist'
        # Superuser check
        if user.is_superuser:
            role = 'admin'
        # 5. Token & Role 
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