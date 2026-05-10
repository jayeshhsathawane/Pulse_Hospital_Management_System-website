from rest_framework import serializers
from pulsehospital.models import (
    Medicine, Doctor, Appointment, PatientProfile, 
    IPD_Admission, Bed, IPD_DailyRecord, Bill, OTBooking
)
from pulsehospital.models import IPD_Admission, Bill
from pulsehospital.models import OTBooking
from pulsehospital.models import DischargeSummary, OTBooking
# ==========================================
# 1. 💊 PHARMACY & COMMON SERIALIZERS
# ==========================================

class MedicineSerializer(serializers.ModelSerializer):
    """ Used for Pharmacy Inventory List & Search """
    class Meta:
        model = Medicine
        fields = '__all__'

class DoctorSerializer(serializers.ModelSerializer):
    """ Used for Dropdowns and Profile Info """
    class Meta:
        model = Doctor
        fields = ['id', 'name', 'specialty', ]

class PatientProfileSerializer(serializers.ModelSerializer):
    """ Used for Patient Search & Details """
    class Meta:
        model = PatientProfile
        fields = '__all__'

# ==========================================
# 2. 👨‍⚕️ DOCTOR DASHBOARD SERIALIZERS
# ==========================================

class AppointmentSerializer(serializers.ModelSerializer):
    """ 
    Used for Doctor Dashboard Queue & Patient History.
    We fetch 'reg_number' from the related PatientProfile model.
    """
    # Nested Data: Patient ka Reg Number dikhane ke liye
    reg_number = serializers.CharField(source='patient_profile.reg_number', read_only=True)
    doctor_name = serializers.CharField(source='assigned_doctor.name', read_only=True)
    
    class Meta:
        model = Appointment
        fields = [
            'id', 
            'patient_name', 
            'age',  
            'phone', 
            'appointment_date', 
            'appointment_time', 
            'status', 
            'diagnosis', 
            'symptoms', 
            'medication_json', # Doctor prescription data
            'reg_number',      # Custom field from above
            'doctor_name',     # Custom field from above
            'booked_on'
        ]

# ==========================================
# 3. 🏥 IPD & BED MANAGEMENT SERIALIZERS
# ==========================================

class BedSerializer(serializers.ModelSerializer):
    """ Used for Reception Bed Dashboard (Green/Red Grid) """
    ward_name = serializers.CharField(source='ward.name', read_only=True)
    
    class Meta:
        model = Bed
        fields = ['id', 'bed_number', 'ward_name', 'is_occupied', ]

class IPDAdmissionSerializer(serializers.ModelSerializer):
    """ Used for Admitted Patients List """
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    reg_number = serializers.CharField(source='patient.reg_number', read_only=True)
    bed_number = serializers.CharField(source='bed.bed_number', read_only=True)
    doctor_name = serializers.CharField(source='attending_doctor.name', read_only=True)

    class Meta:
        model = IPD_Admission
        fields = [
            'id', 
            'admission_id', 
            'patient_name', 
            'reg_number', 
            'bed_number', 
            'doctor_name', 
            'admission_date', 
            'is_discharged',
            'diagnosis'
        ]

class IPDDailyRecordSerializer(serializers.ModelSerializer):
    """ Used for Doctor to see Daily Rounds History """
    class Meta:
        model = IPD_DailyRecord
        fields = '__all__'



# 🟢 1. Patient Admit karne ke liye (Input Serializer)
class AdmitPatientSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()  # PatientProfile ID
    bed_id = serializers.IntegerField()      # Bed ID
    doctor_id = serializers.IntegerField()   # Doctor ID
    diagnosis = serializers.CharField(required=False, allow_blank=True)

# 🟢 2. OT Schedule dikhane ke liye
class OTBookingSerializer(serializers.Serializer): # ModelSerializer bhi use kar sakte hain
    id = serializers.IntegerField()
    surgery_name = serializers.CharField()
    patient_name = serializers.CharField()
    doctor_name = serializers.CharField(source='doctor.name')
    ot_date = serializers.DateField()
    ot_time = serializers.TimeField()
    status = serializers.CharField()

# ==========================================
# 4. 🧾 BILLING SERIALIZERS
# ==========================================

class BillSerializer(serializers.ModelSerializer):
    """ Used for Invoice Generation & History """
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    reg_number = serializers.CharField(source='patient.reg_number', read_only=True)
    
    class Meta:
        model = Bill
        fields = [
            'id', 'bill_number', 'bill_date', 
            'patient_name', 'reg_number', 
            'total_amount', 'payment_mode', 
            'consultation_charges', 'ward_charges', 
            'medicine_charges', 'ot_charges', 'other_charges'
        ]

# ==========================================
# 5. ✂️ OT MANAGEMENT SERIALIZERS
# ==========================================

class OTBookingSerializer(serializers.ModelSerializer):
    """ Used for OT Schedules """
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    
    class Meta:
        model = OTBooking
        fields = '__all__'


        # 🟢 Receptionist ke liye: Appointment Book karne ka Serializer
class BookAppointmentSerializer(serializers.Serializer):
    patient_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=15)
    age = serializers.IntegerField()
    address = serializers.CharField(required=False, allow_blank=True)
    # Doctor ki ID chahiye hogi
    doctor_id = serializers.IntegerField()
    # Vitals (Optional)
    bp = serializers.CharField(required=False, allow_blank=True)
    pulse = serializers.CharField(required=False, allow_blank=True)
    sugar = serializers.CharField(required=False, allow_blank=True)

  


# 5. Admitted Patient List (Billing ke liye search karne ko)
class IPDAdmissionSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    reg_number = serializers.CharField(source='patient.reg_number', read_only=True)
    bed_number = serializers.CharField(source='bed.bed_number', read_only=True)
    
    class Meta:
        model = IPD_Admission
        fields = ['id', 'patient_name', 'reg_number', 'bed_number', 'admission_date']


        # . Discharge Summary (Doctor jo bharega)
class DischargeSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = DischargeSummary
        fields = '__all__'

# . OT Booking (Doctor jo book karega)
class OTActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTBooking
        fields = '__all__'

