from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from core.models import User, MedicalCertificate
from core.forms import MedicalCertificateForm

@login_required
def issue_certificate(request, patient_id):
    """View to issue a new medical certificate"""
    if not request.user.is_doctor():
        messages.error(request, "Only doctors can issue certificates.")
        return redirect('dashboard_redirect')
        
    patient = get_object_or_404(User, id=patient_id, role='patient')
    
    if request.method == 'POST':
        form = MedicalCertificateForm(request.POST)
        if form.is_valid():
            certificate = form.save(commit=False)
            certificate.doctor = request.user
            certificate.patient = patient
            certificate.save()
            messages.success(request, f"Medical Certificate issued successfully for {patient.full_name or patient.username}.")
            return redirect('view_certificate', certificate_id=certificate.certificate_id)
    else:
        form = MedicalCertificateForm()
        
    context = {
        'form': form,
        'patient': patient,
        'page_title': 'Issue Medical Certificate'
    }
    return render(request, 'core/issue_certificate.html', context)

@login_required
def view_certificate(request, certificate_id):
    """View to display the medical certificate in a print-friendly format"""
    certificate = get_object_or_404(MedicalCertificate, certificate_id=certificate_id)
    
    # Check permissions (doctor who issued, patient who received, or admin)
    if not (request.user == certificate.doctor or request.user == certificate.patient or request.user.is_admin()):
        messages.error(request, "You don't have permission to view this certificate.")
        return redirect('dashboard_redirect')
        
    context = {
        'certificate': certificate,
        'doctor': certificate.doctor,
        'patient': certificate.patient,
        'page_title': 'Medical Certificate'
    }
    return render(request, 'core/medical_certificate_print.html', context)

@login_required
def list_certificates(request):
    """List certificates for the logged-in user (patient or doctor)"""
    if request.user.is_doctor():
        certificates = MedicalCertificate.objects.filter(doctor=request.user)
    elif request.user.is_patient():
        certificates = MedicalCertificate.objects.filter(patient=request.user)
    else:
         certificates = MedicalCertificate.objects.none()
         
    context = {
        'certificates': certificates,
        'page_title': 'Medical Certificates'
    }
    return render(request, 'core/list_certificates.html', context)
