# pulsehospital/forms.py
from django import forms
from .models import Appointment, Doctor # Note: DEPARTMENT_CHOICES is automatically linked via Appointment model

class AppointmentForm(forms.ModelForm):
    # ModelChoiceField for Doctor (Pulls data from the Doctor model)
    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.all(),
        empty_label="Select Doctor",
        label="Preferred Doctor",
        widget=forms.Select(attrs={'class': 'form-control'}) 
    )

    class Meta:
        model = Appointment
        fields = [
            'patient_name', 'phone', 'email', 'department', 
            'appointment_date', 'appointment_time', 'reason'
        ]
        
        widgets = {
            # Apply 'form-control' class directly in widgets
            'patient_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Full Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10 Digit Mobile Number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            
            # Department field will automatically get choices from models.py
            'department': forms.Select(attrs={'class': 'form-control'}),
            
            'appointment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'appointment_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Briefly describe your reason for visit', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set required status
        self.fields['patient_name'].required = True
        self.fields['phone'].required = True
        self.fields['department'].required = True
        self.fields['appointment_date'].required = True
        self.fields['appointment_time'].required = True
        
        # Ensure initial empty label for department is set correctly
        self.fields['department'].empty_label = 'Select Department'
        
        # Note: No need to set choices here, as they are inherited from the model.