from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import validate_email
from .models import User, MedicalRecord, MLModel
import re
from django import forms
from core.models import *
from datetime import datetime, timedelta
from django.utils import timezone
import os



class BaseRegistrationForm(UserCreationForm):
    """Base form for all user registrations"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your first name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your last name'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email
    
    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        if len(password1) < 8:
            raise forms.ValidationError('Password must be at least 8 characters long.')
        if not re.search(r'[A-Za-z]', password1):
            raise forms.ValidationError('Password must contain at least one letter.')
        if not re.search(r'\d', password1):
            raise forms.ValidationError('Password must contain at least one number.')
        return password1

class DoctorRegistrationForm(BaseRegistrationForm):
    """Doctor registration form"""
    specialization = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Cardiology, Neurology'
        })
    )
    license_number = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Medical license number'
        })
    )
    
    class Meta(BaseRegistrationForm.Meta):
        fields = BaseRegistrationForm.Meta.fields + ['specialization', 'license_number']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'doctor'
        user.specialization = self.cleaned_data['specialization']
        user.license_number = self.cleaned_data['license_number']
        if commit:
            user.save()
        return user

class ResearcherRegistrationForm(BaseRegistrationForm):
    """Researcher registration form"""
    institution = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., University of Medical Sciences'
        })
    )
    research_area = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Describe your research area'
        })
    )
    
    class Meta(BaseRegistrationForm.Meta):
        fields = BaseRegistrationForm.Meta.fields + ['institution', 'research_area']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'researcher'
        user.institution = self.cleaned_data['institution']
        user.research_area = self.cleaned_data['research_area']
        if commit:
            user.save()
        return user

class PatientRegistrationForm(BaseRegistrationForm):
    """Patient registration form"""
    date_of_birth = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    phone = forms.CharField(
        max_length=17,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1234567890'
        })
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Enter your address'
        })
    )
    
    class Meta(BaseRegistrationForm.Meta):
        fields = BaseRegistrationForm.Meta.fields + ['date_of_birth', 'phone', 'address']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'patient'
        user.date_of_birth = self.cleaned_data['date_of_birth']
        user.phone = self.cleaned_data['phone']
        user.address = self.cleaned_data['address']
        if commit:
            user.save()
        return user

class ProfileForm(forms.ModelForm):
    """Profile update form"""
    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone', 'address', 'date_of_birth', 'profile_picture']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }

class DoctorProfileForm(ProfileForm):
    """Doctor profile form"""
    class Meta(ProfileForm.Meta):
        fields = ProfileForm.Meta.fields + [
            'specialization', 'license_number', 'qualifications', 
            'clinic_name', 'clinic_address', 'signature', 'biography'
        ]
        widgets = {
            **ProfileForm.Meta.widgets,
            'specialization': forms.TextInput(attrs={'class': 'form-control'}),
            'license_number': forms.TextInput(attrs={'class': 'form-control'}),
            'qualifications': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., M.B.B.S, M.D.'}),
            'clinic_name': forms.TextInput(attrs={'class': 'form-control'}),
            'clinic_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'signature': forms.FileInput(attrs={'class': 'form-control'}),
        }

class ResearcherProfileForm(ProfileForm):
    """Researcher profile form"""
    class Meta(ProfileForm.Meta):
        fields = ProfileForm.Meta.fields + ['institution', 'research_area']
        widgets = {
            **ProfileForm.Meta.widgets,
            'institution': forms.TextInput(attrs={'class': 'form-control'}),
            'research_area': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class PatientProfileForm(ProfileForm):
    """Patient profile form"""
    class Meta(ProfileForm.Meta):
        fields = ProfileForm.Meta.fields

class MedicalRecordForm(forms.ModelForm):
    """Form for medical record entry"""
    class Meta:
        model = MedicalRecord
        fields = ['encrypted_data', 'encrypted_symptoms', 'risk_level']
        widgets = {
            'encrypted_data': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter encrypted medical data'
            }),
            'encrypted_symptoms': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter encrypted symptoms'
            }),
            'risk_level': forms.Select(attrs={'class': 'form-control'}),
        }

class SymptomsForm(forms.Form):
    """Form for symptom input"""
    SYMPTOM_CHOICES = [
        ('itching', 'Itching'),
        ('skin_rash', 'Skin Rash'),
        ('nodal_skin_eruptions', 'Nodal Skin Eruptions'),
        ('continuous_sneezing', 'Continuous Sneezing'),
        ('shivering', 'Shivering'),
        ('chills', 'Chills'),
        ('joint_pain', 'Joint Pain'),
        ('stomach_pain', 'Stomach Pain'),
        ('acidity', 'Acidity'),
        ('ulcers_on_tongue', 'Ulcers on Tongue'),
        ('muscle_wasting', 'Muscle Wasting'),
        ('vomiting', 'Vomiting'),
        ('burning_micturition', 'Burning Micturition'),
        ('spotting_urination', 'Spotting Urination'),
        ('fatigue', 'Fatigue'),
        ('weight_gain', 'Weight Gain'),
        ('anxiety', 'Anxiety'),
        ('cold_hands_and_feets', 'Cold Hands and Feets'),
        ('mood_swings', 'Mood Swings'),
        ('weight_loss', 'Weight Loss'),
        ('restlessness', 'Restlessness'),
        ('lethargy', 'Lethargy'),
        ('patches_in_throat', 'Patches in Throat'),
        ('irregular_sugar_level', 'Irregular Sugar Level'),
        ('cough', 'Cough'),
        ('high_fever', 'High Fever'),
        ('sunken_eyes', 'Sunken Eyes'),
        ('breathlessness', 'Breathlessness'),
        ('sweating', 'Sweating'),
        ('dehydration', 'Dehydration'),
        ('indigestion', 'Indigestion'),
        ('headache', 'Headache'),
        ('yellowish_skin', 'Yellowish Skin'),
        ('dark_urine', 'Dark Urine'),
        ('nausea', 'Nausea'),
        ('loss_of_appetite', 'Loss of Appetite'),
        ('pain_behind_the_eyes', 'Pain behind the Eyes'),
        ('back_pain', 'Back Pain'),
        ('constipation', 'Constipation'),
        ('abdominal_pain', 'Abdominal Pain'),
        ('diarrhoea', 'Diarrhoea'),
        ('mild_fever', 'Mild Fever'),
        ('yellow_urine', 'Yellow Urine'),
        ('yellowing_of_eyes', 'Yellowing of Eyes'),
        ('acute_liver_failure', 'Acute Liver Failure'),
        ('fluid_overload', 'Fluid Overload'),
        ('swelling_of_stomach', 'Swelling of Stomach'),
        ('swelled_lymph_nodes', 'Swelled Lymph Nodes'),
        ('malaise', 'Malaise'),
        ('blurred_and_distorted_vision', 'Blurred and Distorted Vision'),
        ('phlegm', 'Phlegm'),
        ('throat_irritation', 'Throat Irritation'),
        ('redness_of_eyes', 'Redness of Eyes'),
        ('sinus_pressure', 'Sinus Pressure'),
        ('runny_nose', 'Runny Nose'),
        ('congestion', 'Congestion'),
        ('chest_pain', 'Chest Pain'),
        ('weakness_in_limbs', 'Weakness in Limbs'),
        ('fast_heart_rate', 'Fast Heart Rate'),
        ('pain_during_bowel_movements', 'Pain during Bowel Movements'),
        ('pain_in_anal_region', 'Pain in Anal Region'),
        ('bloody_stool', 'Bloody Stool'),
        ('irritation_in_anus', 'Irritation in Anus'),
        ('neck_pain', 'Neck Pain'),
        ('dizziness', 'Dizziness'),
        ('cramps', 'Cramps'),
        ('bruising', 'Bruising'),
        ('obesity', 'Obesity'),
        ('swollen_legs', 'Swollen Legs'),
        ('swollen_blood_vessels', 'Swollen Blood Vessels'),
        ('puffy_face_and_eyes', 'Puffy Face and Eyes'),
        ('enlarged_thyroid', 'Enlarged Thyroid'),
        ('brittle_nails', 'Brittle Nails'),
        ('swollen_extremeties', 'Swollen Extremeties'),
        ('excessive_hunger', 'Excessive Hunger'),
        ('extra_marital_contacts', 'Extra Marital Contacts'),
        ('drying_and_tingling_lips', 'Drying and Tingling Lips'),
        ('slurred_speech', 'Slurred Speech'),
        ('knee_pain', 'Knee Pain'),
        ('hip_joint_pain', 'Hip Joint Pain'),
        ('muscle_weakness', 'Muscle Weakness'),
        ('stiff_neck', 'Stiff Neck'),
        ('swelling_joints', 'Swelling Joints'),
        ('movement_stiffness', 'Movement Stiffness'),
        ('spinning_movements', 'Spinning Movements'),
        ('loss_of_balance', 'Loss of Balance'),
        ('unsteadiness', 'Unsteadiness'),
        ('weakness_of_one_body_side', 'Weakness of One Body Side'),
        ('loss_of_smell', 'Loss of Smell'),
        ('bladder_discomfort', 'Bladder Discomfort'),
        ('foul_smell_of_urine', 'Foul Smell of Urine'),
        ('continuous_feel_of_urine', 'Continuous Feel of Urine'),
        ('passage_of_gases', 'Passage of Gases'),
        ('internal_itching', 'Internal Itching'),
        ('toxic_look_typhos', 'Toxic Look (Typhos)'),
        ('depression', 'Depression'),
        ('irritability', 'Irritability'),
        ('muscle_pain', 'Muscle Pain'),
        ('altered_sensorium', 'Altered Sensorium'),
        ('red_spots_over_body', 'Red Spots Over Body'),
        ('belly_pain', 'Belly Pain'),
        ('abnormal_menstruation', 'Abnormal Menstruation'),
        ('dischromic_patches', 'Dischromic Patches'),
        ('watering_from_eyes', 'Watering from Eyes'),
        ('increased_appetite', 'Increased Appetite'),
        ('polyuria', 'Polyuria'),
        ('family_history', 'Family History'),
        ('mucoid_sputum', 'Mucoid Sputum'),
        ('rusty_sputum', 'Rusty Sputum'),
        ('lack_of_concentration', 'Lack of Concentration'),
        ('visual_disturbances', 'Visual Disturbances'),
        ('receiving_blood_transfusion', 'Receiving Blood Transfusion'),
        ('receiving_unsterile_injections', 'Receiving Unsterile Injections'),
        ('coma', 'Coma'),
        ('stomach_bleeding', 'Stomach Bleeding'),
        ('distention_of_abdomen', 'Distention of Abdomen'),
        ('history_of_alcohol_consumption', 'History of Alcohol Consumption'),
        ('fluid_overload', 'Fluid Overload'),
        ('blood_in_sputum', 'Blood in Sputum'),
        ('prominent_veins_on_calf', 'Prominent Veins on Calf'),
        ('palpitations', 'Palpitations'),
        ('painful_walking', 'Painful Walking'),
        ('pus_filled_pimples', 'Pus Filled Pimples'),
        ('blackheads', 'Blackheads'),
        ('scurring', 'Scurring'),
        ('skin_peeling', 'Skin Peeling'),
        ('silver_like_dusting', 'Silver Like Dusting'),
        ('small_dents_in_nails', 'Small Dents in Nails'),
        ('inflammatory_nails', 'Inflammatory Nails'),
        ('blister', 'Blister'),
        ('red_sore_around_nose', 'Red Sore Around Nose'),
        ('yellow_crust_ooze', 'Yellow Crust Ooze'),
    ]
    
    symptoms = forms.MultipleChoiceField(
        choices=SYMPTOM_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'symptom-checkbox'}),
        required=True,
        label="Select Symptoms"
    )
    
    age = forms.IntegerField(
        min_value=0,
        max_value=120,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Age'}),
        required=True
    )
    
    gender = forms.ChoiceField(
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        widget=forms.RadioSelect(attrs={'class': 'gender-radio'}),
        required=True
    )


# core/forms.py (add to existing forms)


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['doctor', 'appointment_date', 'appointment_time', 'appointment_type', 'reason', 'symptoms', 'is_urgent']
        widgets = {
            'appointment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'appointment_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Brief reason for appointment...'}),
            'symptoms': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Describe your symptoms...'}),
            'doctor': forms.Select(attrs={'class': 'form-control'}),
            'appointment_type': forms.Select(attrs={'class': 'form-control'}),
            'is_urgent': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter only active doctors
        self.fields['doctor'].queryset = User.objects.filter(
            role='doctor',
            is_active=True,
            status='approved'
        ).order_by('full_name')
        
        # Set minimum date to tomorrow
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        self.fields['appointment_date'].widget.attrs['min'] = tomorrow
    
    def clean_appointment_date(self):
        appointment_date = self.cleaned_data.get('appointment_date')
        if appointment_date < datetime.now().date():
            raise forms.ValidationError("Cannot book appointment in the past.")
        return appointment_date
    
    def clean(self):
        cleaned_data = super().clean()
        appointment_date = cleaned_data.get('appointment_date')
        appointment_time = cleaned_data.get('appointment_time')
        doctor = cleaned_data.get('doctor')
        
        if appointment_date and appointment_time and doctor:
            # Check if appointment is during working hours (9 AM to 5 PM)
            hour = appointment_time.hour
            if hour < 9 or hour >= 17:
                raise forms.ValidationError("Appointments can only be scheduled between 9 AM and 5 PM.")
            
            # Check if time is in 30-minute increments
            if appointment_time.minute not in [0, 30]:
                raise forms.ValidationError("Appointments must be scheduled at :00 or :30 minutes.")
        
        return cleaned_data
    













# core/forms.py (add to existing forms)

class MedicalDocumentForm(forms.ModelForm):
    """Form for uploading medical documents"""
    class Meta:
        model = MedicalDocument
        fields = ['document_type', 'document_date']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'document_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
    
    def clean_document_date(self):
        document_date = self.cleaned_data.get('document_date')
        if document_date and document_date > timezone.now().date():
            raise forms.ValidationError("Document date cannot be in the future.")
        return document_date

class EMRFileUploadForm(forms.Form):
    """Form for uploading EMR files"""
    ALLOWED_FILE_TYPES = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    document_type = forms.ChoiceField(
        choices=MedicalDocument.DOCUMENT_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    document_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    document_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png,.tiff,.bmp'
        })
    )
    auto_extract = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def clean_document_file(self):
        document_file = self.cleaned_data.get('document_file')
        if document_file:
            # Check file size
            if document_file.size > self.MAX_FILE_SIZE:
                raise forms.ValidationError(f"File size must be less than {self.MAX_FILE_SIZE/1024/1024}MB")
            
            # Check file extension
            ext = os.path.splitext(document_file.name)[1].lower()
            if ext not in self.ALLOWED_FILE_TYPES:
                raise forms.ValidationError(f"Unsupported file type. Allowed types: {', '.join(self.ALLOWED_FILE_TYPES)}")
        
        return document_file
    
    def clean_document_date(self):
        document_date = self.cleaned_data.get('document_date')
        if document_date and document_date > timezone.now().date():
            raise forms.ValidationError("Document date cannot be in the future.")
        return document_date





















class MedicalCertificateForm(forms.ModelForm):
    """Form for doctors to issue medical certificates"""
    class Meta:
        model = MedicalCertificate
        fields = [
            'diagnosis', 'treatment_from', 'treatment_to',
            'rest_advised_from', 'rest_advised_to',
            'fit_to_resume_date', 'additional_advice', 'issued_date'
        ]
        widgets = {
            'diagnosis': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'e.g., Dengue Fever'}),
            'treatment_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'treatment_to': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'rest_advised_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'rest_advised_to': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fit_to_resume_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'additional_advice': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'e.g., He need rest for further 15 days'}),
            'issued_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Default issued_date to today if not set
        if not self.initial.get('issued_date'):
            self.initial['issued_date'] = timezone.now().date()
