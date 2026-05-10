from django.db import models
from django.contrib.auth.models import User
import datetime

# --- 1. CONFIGURATION & LOOKUPS ---
DEPARTMENT_CHOICES = [
    ('general-medicine', 'General Medicine'),
    ('cardiology', 'Cardiology'),
    ('diabetes', 'Diabetes Care'),
    ('gynecology', 'Gynecology & Obstetrics'),
    ('maternity', 'Maternity Care'),
]

# --- 2. INVENTORY & CLINICAL LOOKUP ---
class Medicine(models.Model):
    name = models.CharField(max_length=255) 
    composition = models.TextField(blank=True, null=True) 
    stock_quantity = models.IntegerField(default=0)
    added_on = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.name} ({self.composition})"

class Symptom(models.Model):
    name = models.CharField(max_length=255, unique=True)
    def __str__(self): return self.name

# --- 3. STAFF MODELS ---
class Doctor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE) 
    name = models.CharField(max_length=100)
    specialty = models.CharField(max_length=100)
    def __str__(self): return self.name

class Receptionist(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=20, unique=True, blank=True)
    def __str__(self): return self.name
    def save(self, *args, **kwargs):
        if not self.user.is_staff:
            self.user.is_staff = True
            self.user.save()
        super().save(*args, **kwargs)

class Pharmacist(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE) 
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    def __str__(self): return self.name

class DoctorPatientCounter(models.Model):
    doctor = models.OneToOneField(Doctor, on_delete=models.CASCADE)
    last_id = models.IntegerField(default=0) 
    def __str__(self): return f"Counter for {self.doctor.name}"

# --- 4. PATIENT & CLINICAL RECORDS ---
class PatientProfile(models.Model):
    assigned_doctor_code = models.CharField(
        max_length=10, 
        choices=[('GYN', 'Gynecology'), ('MED', 'General Medicine')], 
        default='MED'
    )
    reg_number = models.CharField(max_length=30, unique=True, editable=False)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    age = models.IntegerField(null=True, blank=True)
    address = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.reg_number:
            if self.assigned_doctor_code == 'GYN':
                target_doctor = Doctor.objects.filter(specialty__icontains='Gynec').first()
            else:
                target_doctor = Doctor.objects.filter(specialty__icontains='General').first()

            if target_doctor:
                counter, created = DoctorPatientCounter.objects.get_or_create(doctor=target_doctor)
                counter.last_id += 1
                counter.save()
                current_year = datetime.datetime.now().year
                sequential_id = str(counter.last_id).zfill(3)
                self.reg_number = f"{self.assigned_doctor_code}-{current_year}-{sequential_id}"
            else:
                self.reg_number = f"TEMP-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)

    def __str__(self): return f"{self.reg_number} - {self.name}"

class Appointment(models.Model):
    patient_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    age = models.IntegerField(null=True, blank=True)
    bp = models.CharField(max_length=20, blank=True, null=True, verbose_name="Blood Pressure")
    pulse = models.CharField(max_length=20, blank=True, null=True)
    sugar = models.CharField(max_length=20, blank=True, null=True)
    patient_profile = models.ForeignKey(PatientProfile, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, null=True, blank=True) 
    department = models.CharField(max_length=100, choices=DEPARTMENT_CHOICES, default='general-medicine')
    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    reason = models.TextField(blank=True)
    symptoms = models.TextField(blank=True, null=True)
    diagnosis = models.TextField(blank=True, null=True) 
    personal_history = models.JSONField(default=list, blank=True, null=True)
    comorbidities = models.JSONField(default=list, blank=True, null=True)
    other_comorbidities = models.CharField(max_length=255, blank=True, null=True)
    medication_json = models.JSONField(default=list, blank=True) 
    status = models.CharField(max_length=20, default='Pending', 
                              choices=[('Pending', 'Pending'), ('Confirmed', 'Confirmed'), ('Completed', 'Completed')])
    is_follow_up = models.BooleanField(default=False)
    booked_on = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.patient_name} - {self.status}"

# --- 5. IPD & OT MANAGEMENT (NEW LOGIC) ---
class Bed(models.Model):
    BED_TYPES = [('General', 'General'), ('ICU', 'ICU'), ('Special', 'Special')]
    bed_number = models.CharField(max_length=10, unique=True)
    bed_type = models.CharField(max_length=20, choices=BED_TYPES)
    is_occupied = models.BooleanField(default=False)
    def __str__(self): return f"Bed {self.bed_number} ({self.bed_type})"

class IPD_Admission(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE)
    admission_id = models.CharField(max_length=50, unique=True) # MH/BHU/NH0740/...
    bed = models.ForeignKey(Bed, on_delete=models.SET_NULL, null=True, related_name='admissions')
    attending_doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True)
    admission_date = models.DateTimeField(auto_now_add=True)
    diagnosis = models.TextField()
    is_discharged = models.BooleanField(default=False)
    discharge_date = models.DateTimeField(null=True, blank=True)

    def __str__(self): 
        return f"{self.admission_id} - {self.patient.name}"

class IPD_DailyRecord(models.Model):
    admission = models.ForeignKey(IPD_Admission, on_delete=models.CASCADE, related_name='daily_records')
    date = models.DateField(auto_now_add=True)
    time = models.TimeField(auto_now_add=True, verbose_name="Record Time")
    patient_reg_id = models.CharField(max_length=50, blank=True, null=True, help_text="Auto-saved Registration ID")
    saline_details = models.TextField(blank=True)
    injection_details = models.TextField(blank=True)
    other_notes = models.TextField(blank=True)
    vitals = models.CharField(max_length=100) 

    def save(self, *args, **kwargs):
        if not self.patient_reg_id and self.admission:
            self.patient_reg_id = self.admission.patient.reg_number
        super().save(*args, **kwargs)

    def __str__(self): 
        return f"Record: {self.patient_reg_id} on {self.date} at {self.time}"
class OT_Management(models.Model):
    SURGERY_STATUS = [('Scheduled', 'Scheduled'), ('In Progress', 'In Progress'), ('Completed', 'Completed')]
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE)
    surgery_name = models.CharField(max_length=200)
    lead_surgeon = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    ot_number = models.CharField(max_length=20)
    surgery_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=SURGERY_STATUS, default='Scheduled')
    def __str__(self): return f"OT: {self.surgery_name} - {self.patient.name}"

# --- 6. UTILS ---
class VisitorCount(models.Model):
    counter = models.PositiveIntegerField(default=0)
    def __str__(self): return f"Total Visitors: {self.counter}"

# pulsehospital/models.py

class DischargeSummary(models.Model):
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE)
    
    # Snapshot fields
    patient_name_snapshot = models.CharField(max_length=150, blank=True)
    reg_id_snapshot = models.CharField(max_length=50, blank=True)

    doctor_name = models.CharField(max_length=100) 
    date_of_admission = models.DateTimeField()
    date_of_discharge = models.DateTimeField(auto_now_add=True)
    
    # Lab & Vitals
    hb = models.CharField(max_length=50, blank=True, verbose_name="Hemoglobin")
    tlc = models.CharField(max_length=50, blank=True, verbose_name="Total Leucocyte Count")
    platelets = models.CharField(max_length=50, blank=True)
    bul = models.CharField(max_length=50, blank=True, verbose_name="Blood Urea Level")
    creatinine = models.CharField(max_length=50, blank=True)
    lft = models.CharField(max_length=100, blank=True, verbose_name="LFT (TB/DB/IB)")
    xray = models.TextField(blank=True, verbose_name="X-Ray Findings")
    ct_scan = models.TextField(blank=True, verbose_name="CT Scan Findings")
    mri = models.TextField(blank=True, verbose_name="MRI Findings")
    
    # Clinical Notes
    presenting_complaints = models.TextField(blank=True)
    final_diagnosis = models.TextField(blank=True)
    condition_on_admission = models.TextField(blank=True)
    condition_on_discharge = models.TextField(blank=True)
    
    # 🟢 Updated: These will store JSON strings (List of medicines)
    treatment_given = models.TextField(help_text="JSON Data: In-hospital meds", default="[]")
    treatment_advised = models.TextField(help_text="JSON Data: Home Rx", default="[]")
    
    # 🟢 New Field
    discharge_advice = models.TextField(blank=True, help_text="General advice/diet/rest", verbose_name="Discharge Advice")
    
    follow_up = models.CharField(max_length=200, blank=True)

    def save(self, *args, **kwargs):
        if self.patient:
            self.patient_name_snapshot = self.patient.name
            self.reg_id_snapshot = self.patient.reg_number
        super().save(*args, **kwargs)

    def __str__(self): 
        return f"Discharge: {self.patient_name_snapshot}"

    # Operation Management

class OTBooking(models.Model):
    STATUS_CHOICES = [
        ('Scheduled', 'Scheduled'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]
    
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    # --- Patient Details (Ab manual entry support ke liye) ---
    # Appointment ko null=True kiya taki bina purane record ke bhi entry ho sake
    appointment = models.ForeignKey('Appointment', on_delete=models.SET_NULL, null=True, blank=True)
    doctor = models.ForeignKey('Doctor', on_delete=models.CASCADE)
    
    # Manual Entry Fields
    patient_name = models.CharField(max_length=255, null=True, blank=True)
    patient_mobile = models.CharField(max_length=15, null=True, blank=True)
    patient_age = models.IntegerField(null=True, blank=True) # Integer ke liye null allow karein
    patient_gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    reg_id_manual = models.CharField(max_length=50, blank=True, null=True)

    # --- Surgery Details ---
    surgery_name = models.CharField(max_length=255)
    ot_date = models.DateField()
    ot_time = models.TimeField()
    anaesthesia_type = models.CharField(max_length=100, blank=True)
    anaesthetist_name = models.CharField(max_length=255, blank=True)
    assistant_surgeon = models.CharField(max_length=255, blank=True)
    
    # --- OT Notes ---
    pre_op_diagnosis = models.TextField(blank=True)
    post_op_diagnosis = models.TextField(blank=True)
    surgical_findings = models.TextField(blank=True)
    procedure_description = models.TextField(blank=True)
    implants_used = models.TextField(blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Scheduled')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.surgery_name} - {self.patient_name}"
    
    #invoice Generate

class Bill(models.Model):
    
    PAYMENT_MODES = [('Cash', 'Cash'), ('Online', 'Online'), ('Cheque', 'Cheque')]
    
    bill_number = models.CharField(max_length=20, unique=True)
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE)
    admission = models.ForeignKey('IPD_Admission', on_delete=models.SET_NULL, null=True, blank=True)
    ot_booking = models.ForeignKey(OTBooking, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Billing Details
    consultation_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ward_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ot_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medicine_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Payment Details
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES)
    transaction_id = models.CharField(max_length=100, blank=True, null=True) # Sirf Online ke liye
    bill_date = models.DateTimeField(auto_now_add=True)
    discharged_by = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name='bills_discharged')
    def __str__(self):
        return f"Bill {self.bill_number} - {self.patient.name}"