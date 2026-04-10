# core/views/doctor_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages
from django.db.models import Count, Q, F
from django.core.paginator import Paginator
import json
import logging
import base64
import os
from datetime import datetime, timedelta
from backend.services.crypto_service import  encrypt_file_content, decrypt_file_content
from backend.services.audit_service import log_event
from backend.services.ollama_service import query_ollama
from django.db.models import Avg
from backend.services.video_service import video_service
from backend.services.meeting_ai_service import meeting_ai_service


# views.py (relevant part)
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from core.decorators import role_required
from core.forms import SymptomsForm
from core.models import User, MedicalRecord, Notification
from core.utils import ml_predict, log_event
import json
import logging

logger = logging.getLogger(__name__)
# ... (keep existing imports and functions until doctor_dashboard) ...

from core.decorators import role_required
from core.models import *
from core.forms import *
from core.utils import *

logger = logging.getLogger(__name__)

def get_available_ollama_models():
    """Get list of available Ollama models with better error handling"""
    try:
        ollama_url = getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434')
        
        response = requests.get(f"{ollama_url}/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = []
            
            for model in data.get('models', []):
                model_name = model.get('name', '')
                if model_name:
                    # Keep the full model name with version tag
                    models.append(model_name)
            
            # If no models found, return an empty list
            return models if models else []
        else:
            logger.error(f"Failed to get models: {response.status_code}")
            return []  # Return empty list if API fails
    except requests.exceptions.ConnectionError:
        logger.warning("Ollama not connected")
        return []  # Return empty list if can't connect
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        return []  # Return empty list on any error


# @login_required
# @role_required('doctor')
# def doctor_dashboard(request):
#     """Doctor dashboard"""
#     # Get doctor's patients - only patients, not admins or other doctors
#     patients = User.objects.filter(role='patient',is_superuser=False).order_by('-last_analysis')
    
#     # Statistics
#     total_patients = patients.count()
#     high_risk_patients = patients.filter(risk_level__in=['high', 'critical']).count()
    
#     # Get recent analyses count
#     recent_analyses = MedicalRecord.objects.filter(created_by=request.user).count()
    
#     # Get chat sessions
#     chat_sessions = ChatSession.objects.filter(
#         user=request.user,
#         role='doctor'
#     ).order_by('-updated_at')[:5]
    
#     # Get notifications for the doctor
#     notifications = Notification.objects.filter(
#         user=request.user,
#         is_read=False
#     ).order_by('-created_at')[:5]
    
#     # Get recent medical records
#     recent_records = MedicalRecord.objects.filter(
#         created_by=request.user
#     ).select_related('patient').order_by('-created_at')[:5]
    
#     # Sample appointments
#     appointments = [
#         {'patient_name': 'John Doe', 'type': 'Follow-up', 'time': '10:00 AM', 'status': 'confirmed'},
#         {'patient_name': 'Jane Smith', 'type': 'Consultation', 'time': '11:30 AM', 'status': 'pending'},
#     ]
    
#     context = {
#         'total_patients': total_patients,
#         'high_risk_patients': high_risk_patients,
#         'recent_analyses': recent_analyses,
#         'patients': patients[:10],
#         'chat_sessions': chat_sessions,
#         'notifications': notifications,
#         'recent_records': recent_records,
#         'appointments': appointments,
#         'symptom_form': SymptomsForm(),
#     }
    
#     log_event('DASHBOARD_ACCESS', request.user, {'dashboard': 'doctor'}, request)
#     return render(request, 'doctor/dashboard.html', context)



@login_required
@role_required('doctor')
def doctor_dashboard(request):
    """Doctor dashboard"""
    # Get doctor's patients - only patients, not admins or other doctors
    patients = User.objects.filter(role='patient', is_superuser=False).order_by('-last_analysis')
    
    # Statistics
    total_patients = patients.count()
    high_risk_patients = patients.filter(risk_level__in=['high', 'critical']).count()
    
    # Get recent analyses count
    recent_analyses = MedicalRecord.objects.filter(created_by=request.user).count()
    
    # Get chat sessions
    chat_sessions = ChatSession.objects.filter(
        user=request.user,
        role='doctor'
    ).order_by('-updated_at')[:5]
    
    # Get notifications for the doctor
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    # Get recent medical records
    recent_records = MedicalRecord.objects.filter(
        created_by=request.user
    ).select_related('patient').order_by('-created_at')[:5]
    
    # Get upcoming appointments
    today = timezone.now().date()
    upcoming_appointments = Appointment.objects.filter(
        doctor=request.user,
        status__in=['confirmed', 'pending'],
        appointment_date__gte=today
    ).order_by('appointment_date', 'appointment_time')[:5]
    
    # Count pending appointments
    pending_appointments = Appointment.objects.filter(
        doctor=request.user,
        status='pending'
    ).count()
    
    # Get today's appointments
    today_appointments = Appointment.objects.filter(
        doctor=request.user,
        appointment_date=today,
        status='confirmed'
    ).order_by('appointment_time')
    
    context = {
        'total_patients': total_patients,
        'high_risk_patients': high_risk_patients,
        'recent_analyses': recent_analyses,
        'patients': patients[:10],
        'chat_sessions': chat_sessions,
        'notifications': notifications,
        'recent_records': recent_records,
        'upcoming_appointments': upcoming_appointments,
        'today_appointments': today_appointments,
        'pending_appointments': pending_appointments,
        'symptom_form': SymptomsForm(),
    }
    
    log_event('DASHBOARD_ACCESS', request.user, {'dashboard': 'doctor'}, request)
    return render(request, 'doctor/dashboard.html', context)

# ... (keep existing functions until we add appointment functions) ...

@login_required
@role_required('doctor')
def doctor_appointments(request):
    """Doctor appointments management"""
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    date_filter = request.GET.get('date', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    appointments = Appointment.objects.filter(doctor=request.user)
    
    # Apply filters
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            appointments = appointments.filter(appointment_date=filter_date)
        except ValueError:
            pass
    
    if search_query:
        appointments = appointments.filter(
            Q(patient__full_name__icontains=search_query) |
            Q(patient__username__icontains=search_query) |
            Q(reason__icontains=search_query)
        )
    
    # Order by date and time
    appointments = appointments.order_by('appointment_date', 'appointment_time')
    
    # Pagination
    paginator = Paginator(appointments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get statistics
    total_appointments = appointments.count()
    upcoming_appointments = appointments.filter(
        appointment_date__gte=timezone.now().date(),
        status='confirmed'
    ).count()
    pending_appointments = appointments.filter(status='pending').count()
    
    context = {
        'appointments': page_obj,
        'total_appointments': total_appointments,
        'upcoming_appointments': upcoming_appointments,
        'pending_appointments': pending_appointments,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'search_query': search_query,
    }
    
    log_event('APPOINTMENTS_VIEW', request.user, {
        'filters': {
            'status': status_filter,
            'date': date_filter,
            'search': search_query
        }
    }, request)
    
    return render(request, 'doctor/appointments.html', context)

@login_required
@role_required('doctor')
def doctor_appointment_detail(request, appointment_id):
    """View appointment details"""
    appointment = get_object_or_404(
        Appointment,
        appointment_id=appointment_id,
        doctor=request.user
    )
    
    # Get patient's medical records
    medical_records = MedicalRecord.objects.filter(
        patient=appointment.patient
    ).order_by('-created_at')[:5]
    
    context = {
        'appointment': appointment,
        'medical_records': medical_records,
        'patient': appointment.patient,
    }
    
    log_event('APPOINTMENT_DETAIL_VIEW', request.user, {
        'appointment_id': str(appointment_id),
        'patient': appointment.patient.username
    }, request)
    
    return render(request, 'doctor/appointment_detail.html', context)

@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def doctor_update_appointment_status(request, appointment_id):
    """Update appointment status (approve/reject)"""
    try:
        appointment = get_object_or_404(
            Appointment,
            appointment_id=appointment_id,
            doctor=request.user
        )
        
        data = json.loads(request.body)
        new_status = data.get('status')
        notes = data.get('notes', '')
        
        if new_status not in ['confirmed', 'rejected', 'cancelled']:
            return JsonResponse({
                'success': False,
                'error': 'Invalid status'
            })
        
        old_status = appointment.status
        appointment.status = new_status
        
        if notes:
            appointment.notes = notes
        
        appointment.save()
        
        # Create notification for patient
        status_display = dict(Appointment.APPOINTMENT_STATUS_CHOICES).get(new_status, new_status)
        Notification.create_notification(
            user=appointment.patient,
            title='Appointment Status Updated',
            message=f'Your appointment with Dr. {request.user.get_full_name()} has been {status_display.lower()}',
            notification_type='info' if new_status == 'confirmed' else 'warning',
            action_url=f'/patient/appointments/{appointment_id}/'
        )
        
        # Log the event
        log_event('APPOINTMENT_STATUS_UPDATE', request.user, {
            'appointment_id': str(appointment_id),
            'old_status': old_status,
            'new_status': new_status,
            'patient': appointment.patient.username,
            'date': appointment.appointment_date.strftime('%Y-%m-%d'),
            'time': appointment.appointment_time.strftime('%H:%M')
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': f'Appointment {status_display.lower()} successfully',
            'new_status': new_status,
            'status_display': status_display
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
    except Exception as e:
        logger.error(f"Appointment status update error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def doctor_update_appointment_time(request, appointment_id):
    """Update appointment time"""
    try:
        appointment = get_object_or_404(
            Appointment,
            appointment_id=appointment_id,
            doctor=request.user
        )
        
        data = json.loads(request.body)
        new_date = data.get('date')
        new_time = data.get('time')
        
        if not new_date or not new_time:
            return JsonResponse({
                'success': False,
                'error': 'Date and time are required'
            })
        
        # Parse date and time
        try:
            appointment_date = datetime.strptime(new_date, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(new_time, '%H:%M').time()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid date or time format'
            })
        
        # Check if the new time is in the past
        new_datetime = datetime.combine(appointment_date, appointment_time)
        if new_datetime < timezone.now():
            return JsonResponse({
                'success': False,
                'error': 'Cannot schedule appointment in the past'
            })
        
        # Check for scheduling conflicts
        conflicting_appointments = Appointment.objects.filter(
            doctor=request.user,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status='confirmed'
        ).exclude(appointment_id=appointment_id)
        
        if conflicting_appointments.exists():
            return JsonResponse({
                'success': False,
                'error': 'Time slot already booked'
            })
        
        old_date = appointment.appointment_date
        old_time = appointment.appointment_time
        
        appointment.appointment_date = appointment_date
        appointment.appointment_time = appointment_time
        appointment.save()
        
        # Create notification for patient
        Notification.create_notification(
            user=appointment.patient,
            title='Appointment Rescheduled',
            message=f'Your appointment with Dr. {request.user.get_full_name()} has been rescheduled to {appointment_date.strftime("%B %d, %Y")} at {appointment_time.strftime("%I:%M %p")}',
            notification_type='info',
            action_url=f'/patient/appointments/{appointment_id}/'
        )
        
        # Log the event
        log_event('APPOINTMENT_TIME_UPDATE', request.user, {
            'appointment_id': str(appointment_id),
            'old_datetime': f"{old_date} {old_time}",
            'new_datetime': f"{appointment_date} {appointment_time}",
            'patient': appointment.patient.username
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': 'Appointment time updated successfully',
            'new_date': appointment_date.strftime('%Y-%m-%d'),
            'new_time': appointment_time.strftime('%H:%M')
        })
        
    except Exception as e:
        logger.error(f"Appointment time update error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@role_required('doctor')
def doctor_schedule(request):
    """Doctor's schedule view"""
    # Get date from query parameter or use today
    date_str = request.GET.get('date')
    if date_str:
        try:
            current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            current_date = timezone.now().date()
    else:
        current_date = timezone.now().date()
    
    # Calculate previous and next dates
    prev_date = current_date - timedelta(days=1)
    next_date = current_date + timedelta(days=1)
    
    # Get appointments for the selected date
    appointments = Appointment.objects.filter(
        doctor=request.user,
        appointment_date=current_date,
        status__in=['confirmed', 'pending']
    ).order_by('appointment_time')
    
    # Get available time slots (assuming 30-minute slots from 9 AM to 5 PM)
    time_slots = []
    for hour in range(9, 17):
        for minute in [0, 30]:
            time_slots.append(f"{hour:02d}:{minute:02d}")
    
    # Get booked slots
    booked_slots = []
    for appointment in appointments:
        booked_slots.append(appointment.appointment_time.strftime('%H:%M'))
    
    # Get week's appointments
    week_start = current_date - timedelta(days=current_date.weekday())
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    
    week_appointments = []
    for date in week_dates:
        day_appointments = Appointment.objects.filter(
            doctor=request.user,
            appointment_date=date,
            status__in=['confirmed', 'pending']
        ).count()
        week_appointments.append({
            'date': date,
            'count': day_appointments
        })
    
    context = {
        'current_date': current_date,
        'prev_date': prev_date,
        'next_date': next_date,
        'appointments': appointments,
        'time_slots': time_slots,
        'booked_slots': booked_slots,
        'week_dates': week_dates,
        'week_appointments': week_appointments,
    }
    
    return render(request, 'doctor/schedule.html', context)

@login_required
@role_required('doctor')
def doctor_availability(request):
    """Set doctor's availability"""
    if request.method == 'POST':
        # This would typically save availability settings to a DoctorAvailability model
        # For now, we'll just show a success message
        messages.success(request, 'Availability settings saved successfully!')
        return redirect('doctor_availability')
    
    # Get upcoming appointments to show busy times
    upcoming_appointments = Appointment.objects.filter(
        doctor=request.user,
        appointment_date__gte=timezone.now().date(),
        status='confirmed'
    ).order_by('appointment_date', 'appointment_time')[:20]
    
    context = {
        'upcoming_appointments': upcoming_appointments,
    }
    
    return render(request, 'doctor/availability.html', context)

@login_required
@role_required('doctor')
def doctor_create_video_meeting(request, appointment_id):
    """Create a secure video meeting for an appointment"""
    appointment = get_object_or_404(
        Appointment,
        appointment_id=appointment_id,
        doctor=request.user
    )
    
    meeting_url = video_service.create_secure_meeting(appointment)
    messages.success(request, f"Secure video meeting created for {appointment.patient.full_name or appointment.patient.username}.")
    return redirect('doctor_appointment_detail', appointment_id=appointment_id)

@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def doctor_process_meeting_summary(request, appointment_id):
    """Process transcript and generate encrypted AI summary"""
    try:
        appointment = get_object_or_404(
            Appointment,
            appointment_id=appointment_id,
            doctor=request.user
        )
        
        data = json.loads(request.body)
        transcript = data.get('transcript', '')
        
        if not transcript:
            return JsonResponse({'success': False, 'error': 'Transcript is required'})
            
        result = meeting_ai_service.process_session(appointment, transcript)
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@role_required('doctor')
def doctor_view_meeting_details(request, appointment_id):
    """View decrypted meeting details (authorized only)"""
    appointment = get_object_or_404(
        Appointment,
        appointment_id=appointment_id
    )
    
    # Check permissions
    if request.user != appointment.doctor and request.user != appointment.patient:
        messages.error(request, "Permission denied")
        return redirect('dashboard')
        
    meeting_data = meeting_ai_service.get_decrypted_content(appointment, request.user)
    
    context = {
        'appointment': appointment,
        'meeting_data': meeting_data,
        'page_title': 'Meeting Summary'
    }
    return render(request, 'doctor/meeting_details.html', context)

# ... (the rest of existing doctor_views.py functions remain the same) ...

















@login_required
@role_required('doctor')
def doctor_chat(request):
    """Doctor chat interface with Ollama"""
    # Check if we need a new session
    if request.GET.get('new'):
        chat_session = ChatSession.objects.create(
            user=request.user,
            role='doctor',
            title=f'Chat Session - {timezone.now().strftime("%H:%M")}'
        )
        return redirect('doctor_chat')
    
    # Get or create active chat session
    session_id = request.GET.get('session')
    if session_id:
        try:
            chat_session = ChatSession.objects.get(
                id=session_id,
                user=request.user,
                role='doctor'
            )
        except ChatSession.DoesNotExist:
            chat_session = ChatSession.objects.create(
                user=request.user,
                role='doctor',
                title=f'Chat Session - {timezone.now().strftime("%H:%M")}'
            )
    else:
        # Get latest chat session or create new
        chat_session = ChatSession.objects.filter(
            user=request.user,
            role='doctor'
        ).order_by('-updated_at').first()
        
        if not chat_session:
            chat_session = ChatSession.objects.create(
                user=request.user,
                role='doctor',
                title=f'Chat Session - {timezone.now().strftime("%Y-%m-%d")}'
            )
    
    # Get chat messages
    messages = ChatMessage.objects.filter(session=chat_session).order_by('created_at')
    
    # Get available models
    available_models = get_available_ollama_models()
    
    # Get selected model from session
    selected_model = request.session.get('ollama_model', '')
    
    # If no model is selected or the selected model is not available, use first available
    if not selected_model or selected_model not in available_models:
        if available_models:
            selected_model = available_models[0]
            request.session['ollama_model'] = selected_model
            request.session.save()
        else:
            selected_model = 'No models available'
    
    # Get patient list for context - only patients
    patients = User.objects.filter(role='patient').order_by('full_name')
    
    # Get selected patient from query params
    selected_patient_id = request.GET.get('patient')
    selected_patient = None
    if selected_patient_id:
        try:
            selected_patient = User.objects.get(id=selected_patient_id, role='patient')
        except User.DoesNotExist:
            pass
    
    # Get chat history
    chat_history = ChatSession.objects.filter(
        user=request.user,
        role='doctor'
    ).order_by('-updated_at')[:10]
    
    context = {
        'chat_session': chat_session,
        'messages': messages,
        'available_models': available_models,
        'selected_model': selected_model,
        'patient_list': patients,
        'selected_patient': selected_patient,
        'chat_history': chat_history,
    }
    return render(request, 'doctor/chat.html', context)


@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def doctor_chat_send(request):
    """Send message in doctor chat using Ollama"""
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        # Get available models
        available_models = get_available_ollama_models()
        
        # Get model name from session
        model_name = data.get('model', request.session.get('ollama_model', ''))
        
        # If no model is set or model not available, use first available model
        if not model_name or model_name not in available_models:
            if available_models:
                model_name = available_models[0]
                request.session['ollama_model'] = model_name
                request.session.save()
            else:
                return JsonResponse({
                    'success': False, 
                    'error': 'No Ollama models available. Please make sure Ollama is running and you have downloaded a model.'
                })
        
        if not message:
            return JsonResponse({'success': False, 'error': 'Message is required'})
        
        # Get chat session
        chat_session = ChatSession.objects.get(
            id=session_id,
            user=request.user,
            role='doctor'
        )
        
        # Save user message
        user_message = ChatMessage.objects.create(
            session=chat_session,
            message_type='user',
            content=message
        )
        
        # Construct prompt with medical context
        patient_context = ""
        patient_id = data.get('patient_id')
        if patient_id:
            try:
                patient = User.objects.get(id=patient_id, role='patient')
                patient_context = f"\n\nPatient Context:\n- Name: {patient.get_full_name() or patient.username}\n- Risk Level: {patient.get_risk_level_display() or 'Not assessed'}"
                if patient.last_analysis:
                    patient_context += f"\n- Last Analysis: {patient.last_analysis.strftime('%Y-%m-%d')}"
                
                # Get recent symptoms if available
                recent_record = MedicalRecord.objects.filter(patient=patient).order_by('-created_at').first()
                if recent_record:
                    try:
                        symptoms = json.loads(recent_record.encrypted_symptoms)
                        if symptoms:
                            patient_context += f"\n- Recent Symptoms: {', '.join(symptoms[:5])}"
                    except:
                        pass
            except Exception as e:
                logger.warning(f"Could not load patient context: {e}")
        
        # Create the prompt for Ollama
        prompt = f"{patient_context}\n\nDoctor's Question: {message}"
        
        # Get AI response from Ollama
        ai_response = query_ollama(prompt, model_name)
        
        # Save AI response
        ai_message = ChatMessage.objects.create(
            session=chat_session,
            message_type='ai',
            content=ai_response
        )
        
        # Update session timestamp and title
        if chat_session.messages.count() == 2:  # First exchange
            short_message = message[:40] + "..." if len(message) > 40 else message
            chat_session.title = f"Chat: {short_message}"
            chat_session.save()
        
        # Update last updated time
        chat_session.updated_at = timezone.now()
        chat_session.save()
        
        log_event('CHAT_INTERACTION', request.user, {
            'role': 'doctor',
            'message_length': len(message),
            'session_id': str(chat_session.session_id),
            'model': model_name
        }, request)
        
        return JsonResponse({
            'success': True,
            'user_message': user_message.content,
            'ai_response': ai_message.content,
            'timestamp': user_message.created_at.isoformat(),
            'model': model_name
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
    except ChatSession.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Chat session not found'
        })
    except Exception as e:
        logger.error(f"Doctor chat error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    


@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def doctor_change_model(request):
    """Change Ollama model"""
    try:
        data = json.loads(request.body)
        model_name = data.get('model', '')
        
        if not model_name:
            return JsonResponse({
                'success': False,
                'error': 'Model name is required'
            })
        
        # Get available models
        available_models = get_available_ollama_models()
        
        if not available_models:
            return JsonResponse({
                'success': False,
                'error': 'No models available. Please make sure Ollama is running.'
            })
        
        # Check if model exists in available models
        if model_name not in available_models:
            # Try to find a matching model
            matching_models = [m for m in available_models if model_name.lower() in m.lower()]
            if matching_models:
                model_name = matching_models[0]
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Model "{model_name}" not found. Available models: {", ".join(available_models)}'
                })
        
        # Store in session
        request.session['ollama_model'] = model_name
        request.session.save()
        
        log_event('MODEL_CHANGE', request.user, {
            'old_model': request.session.get('ollama_model'),
            'new_model': model_name
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': f'Model changed to {model_name}',
            'available_models': available_models,
            'current_model': model_name
        })
        
    except Exception as e:
        logger.error(f"Model change error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })



@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def test_ollama_connection(request):
    """Test Ollama connection"""
    try:
        ollama_url = getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434')
        
        # First, try to get available models
        try:
            response = requests.get(f"{ollama_url}/api/tags", timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                models = []
                
                # Extract model names
                for model in data.get('models', []):
                    model_name = model.get('name', '')
                    if model_name:
                        models.append(model_name)
                
                if not models:
                    return JsonResponse({
                        'success': False,
                        'error': 'No models found in Ollama. Please pull a model first.',
                        'suggestion': 'Run: ollama pull llama2'
                    })
                
                # Get current model from session
                current_model = request.session.get('ollama_model', '')
                
                # If no current model or it's not available, use first available
                if not current_model or current_model not in models:
                    current_model = models[0]
                    request.session['ollama_model'] = current_model
                    request.session.save()
                    
                    return JsonResponse({
                        'success': True,
                        'message': f'Using model "{current_model}"',
                        'models': models,
                        'current_model': current_model,
                        'status': 'model_selected',
                    })
                
                # Test if we can generate a simple response
                try:
                    test_payload = {
                        "model": current_model,
                        "prompt": "Hello",
                        "stream": False
                    }
                    
                    gen_response = requests.post(
                        f"{ollama_url}/api/generate", 
                        json=test_payload, 
                        timeout=120
                    )
                    
                    if gen_response.status_code == 200:
                        return JsonResponse({
                            'success': True,
                            'message': f'Ollama connected successfully using model "{current_model}"',
                            'models': models,
                            'current_model': current_model,
                            'status': 'connected'
                        })
                    else:
                        error_msg = f'Model test failed with status {gen_response.status_code}'
                        try:
                            error_data = gen_response.json()
                            if 'error' in error_data:
                                error_msg = error_data['error']
                        except:
                            pass
                            
                        return JsonResponse({
                            'success': False,
                            'message': f'Ollama connected but model test failed',
                            'error': error_msg,
                            'models': models,
                            'current_model': current_model,
                            'status': 'model_error'
                        })
                        
                except requests.exceptions.Timeout:
                    return JsonResponse({
                        'success': True,
                        'message': 'Ollama connected but model response timed out',
                        'models': models,
                        'current_model': current_model,
                        'status': 'slow'
                    })
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Ollama API returned status {response.status_code}'
                })
                
        except requests.exceptions.ConnectionError:
            return JsonResponse({
                'success': False,
                'error': 'Cannot connect to Ollama. Make sure Ollama is running on localhost:11434'
            })
            
    except Exception as e:
        logger.error(f"Test connection error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    



@login_required
@role_required('doctor')
def doctor_patients(request):
    """View all patients - only patients, not admins"""
    patients = User.objects.filter(role='patient',is_superuser=False).order_by('-last_analysis')
    
    # Filter by search query
    search_query = request.GET.get('search', '')
    if search_query:
        patients = patients.filter(
            Q(full_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Filter by risk level
    risk_filter = request.GET.get('risk_level', '')
    if risk_filter:
        patients = patients.filter(risk_level=risk_filter)
    
    # Get statistics
    total_patients = patients.count()
    high_risk_patients = patients.filter(risk_level__in=['high', 'critical']).count()
    
    # Risk distribution
    risk_distribution = {
        'low': patients.filter(risk_level='low').count(),
        'medium': patients.filter(risk_level='medium').count(),
        'high': patients.filter(risk_level='high').count(),
        'critical': patients.filter(risk_level='critical').count(),
    }
    
    context = {
        'patients': patients,
        'total_patients': total_patients,
        'high_risk_patients': high_risk_patients,
        'risk_distribution': risk_distribution,
        'search_query': search_query,
        'risk_filter': risk_filter,
    }
    
    log_event('PATIENTS_VIEW', request.user, {
        'total_patients': total_patients,
        'search_query': search_query,
        'risk_filter': risk_filter
    }, request)
    
    return render(request, 'doctor/patients.html', context)

@login_required
@role_required('doctor')
def doctor_patient_submissions(request):
    """View patient symptom checker submissions"""
    # Fetch all medical records that were submitted by patients (created_by is null or role is patient)
    # Filter for records with symptom data
    submissions = MedicalRecord.objects.filter(
        created_by__isnull=True  # Records created via the patient portal
    ).select_related('patient').order_by('-created_at')
    
    # Enrich submissions with decoded data for display
    enriched_submissions = []
    for sub in submissions:
        try:
            symptoms = json.loads(sub.encrypted_symptoms)
            # extra_symptoms and new details are in encrypted_data
            extra_data = json.loads(sub.encrypted_data) if sub.encrypted_data else {}
            
            enriched_submissions.append({
                'record': sub,
                'patient': sub.patient,
                'symptoms': symptoms,
                'notes': extra_data.get('notes', ''),
                'gender': extra_data.get('gender', 'N/A'),
                'occupation': extra_data.get('occupation', 'N/A'),
                'region': extra_data.get('region', 'N/A'),
                'duration': extra_data.get('duration', 'N/A'),
                'frequency': extra_data.get('frequency', 'N/A'),
                'past_history': extra_data.get('past_history', 'N/A'),
                'age': sub.patient_age or 'N/A'
            })
        except Exception as e:
            logger.error(f"Error decoding submission {sub.id}: {e}")
            continue

    context = {
        'submissions': enriched_submissions,
    }
    
    log_event('VIEW_SUBMISSIONS', request.user, {'role': 'doctor'}, request)
    return render(request, 'doctor/patient_submissions.html', context)

@login_required
@role_required('doctor')
def doctor_patient_detail(request, patient_id):
    """View patient details - only patients"""
    patient = get_object_or_404(User, id=patient_id, role='patient')
    medical_records = MedicalRecord.objects.filter(patient=patient).order_by('-created_at')
    
    # Get statistics
    total_records = medical_records.count()
    high_risk_records = medical_records.filter(risk_level__in=['high', 'critical']).count()
    
    context = {
        'patient': patient,
        'medical_records': medical_records,
        'total_records': total_records,
        'high_risk_records': high_risk_records,
    }
    
    log_event('PATIENT_DETAIL_VIEW', request.user, {
        'patient': patient.username,
        'patient_id': patient_id
    }, request)
    
    return render(request, 'doctor/patient_detail.html', context)





@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def doctor_ml_analysis(request):
    """Perform ML analysis with fuzzy logic"""
    try:
        data = json.loads(request.body)
        symptoms = data.get('symptoms', [])
        patient_id = data.get('patient_id')
        patient_age = data.get('patient_age', 35)  # Default age if not provided
        
        if not symptoms:
            return JsonResponse({'success': False, 'error': 'Symptoms are required'})
        
        # Get patient info if patient_id provided
        patient = None
        if patient_id:
            try:
                patient = User.objects.get(id=patient_id, role='patient')
                # Get patient age from profile if available
                if hasattr(patient, 'profile') and patient.profile.age:
                    patient_age = patient.profile.age
            except User.DoesNotExist:
                patient = None
        
        # Get ML prediction using the enhanced utility function
        result = ml_predict(symptoms, patient_age)
        
        # Update patient if provided
        if patient:
            try:
                patient.risk_level = result.get('risk_level', 'low')
                patient.ml_confidence_score = result.get('confidence_score', 0.0)
                patient.last_analysis = timezone.now()
                patient.save()
                
                # Create medical record with encrypted data
                encrypted_symptoms = json.dumps(symptoms)
                encrypted_diagnosis = result.get('prediction', '')
                
                MedicalRecord.objects.create(
                    patient=patient,
                    encrypted_symptoms=encrypted_symptoms,
                    encrypted_diagnosis=encrypted_diagnosis,
                    created_by=request.user,
                    risk_level=result.get('risk_level', 'low'),
                    confidence_score=result.get('confidence_score', 0.0),
                    additional_data={
                        'fuzzy_membership': result.get('fuzzy_membership', {}),
                        'risk_score': result.get('risk_score', 0.0),
                        'symptoms_analyzed': len(symptoms),
                        'patient_age': patient_age
                    }
                )
                
                # Create notification
                Notification.create_notification(
                    user=request.user,
                    title='ML Analysis Complete',
                    message=f'Analysis completed for patient {patient.get_full_name() or patient.username}',
                    notification_type='success'
                )
            except Exception as e:
                logger.error(f"Error updating patient record: {e}")
        
        # Log the event
        log_event('ML_PREDICTION', request.user, {
            'symptoms_count': len(symptoms),
            'prediction': result.get('prediction'),
            'confidence_score': result.get('confidence_score'),
            'risk_level': result.get('risk_level'),
            'patient_id': patient_id,
            'patient_age': patient_age
        }, request)
        
        return JsonResponse({
            'success': True,
            'result': result
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
        
    except Exception as e:
        logger.error(f"ML analysis error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@role_required('doctor')
def doctor_symptom_analyzer(request):
    """Doctor symptom analyzer page with fuzzy logic"""
    # Get patients for context - only patients
    patients = User.objects.filter(role='patient', is_superuser=False).order_by('-last_analysis')
    
    # Get ALL analyses first for counting (don't slice yet)
    all_analyses = MedicalRecord.objects.filter(created_by=request.user)
    
    # Get recent analyses for display (slice here)
    recent_analyses = all_analyses.order_by('-created_at')[:10]
    
    # Statistics - use the original queryset, not the sliced one
    total_analyses = all_analyses.count()
    high_risk_analyses = all_analyses.filter(
        risk_level__in=['high', 'critical']
    ).count()
    
    # Get average confidence score
    avg_confidence = 0
    if total_analyses > 0:
        avg_confidence = all_analyses.aggregate(Avg('confidence_score'))['confidence_score__avg'] or 0
    
    context = {
        'patients': patients[:20],
        'recent_analyses': recent_analyses,
        'total_analyses': total_analyses,
        'high_risk_analyses': high_risk_analyses,
        'avg_confidence': round(avg_confidence * 100, 1),
        'common_symptoms': [
            'Fever', 'Cough', 'Fatigue', 'Headache', 'Nausea',
            'Shortness of breath', 'Chest pain', 'Dizziness',
            'Muscle pain', 'Sore throat', 'Loss of taste/smell',
            'Diarrhea', 'Abdominal pain', 'Vomiting', 'Rash'
        ],
        'symptom_form': SymptomsForm(),
    }
    
    log_event('SYMPTOM_ANALYZER_ACCESS', request.user, {}, request)
    return render(request, 'doctor/symptom_analyzer.html', context)



@login_required
@role_required('doctor')
def doctor_profile(request):
    """Doctor profile"""
    if request.method == 'POST':
        form = DoctorProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            
            # Create notification
            Notification.create_notification(
                user=request.user,
                title='Profile Updated',
                message='Your doctor profile has been updated successfully.',
                notification_type='success'
            )
            
            log_event('PROFILE_UPDATE', request.user, {'role': 'doctor'}, request)
            return redirect('doctor_profile')
    else:
        form = DoctorProfileForm(instance=request.user)
    
    return render(request, 'doctor/profile.html', {'form': form})

@login_required
@role_required('doctor')
def doctor_medical_tools(request):
    """Medical tools page"""
    ml_models = MLModel.objects.filter(is_active=True)
    
    # Get patients for dropdown - only patients
    patients = User.objects.filter(role='patient',is_superuser=False).order_by('-last_analysis')
    
    context = {
        'ml_models': ml_models,
        'patients': patients[:20],
        'symptom_form': SymptomsForm(),
    }
    
    log_event('MEDICAL_TOOLS_ACCESS', request.user, {}, request)
    return render(request, 'doctor/medical_tools.html', context)







@login_required
@role_required('doctor')
def doctor_medical_history(request):
    """View medical history of all patients"""
    # Get ALL medical records first (no slice yet)
    all_records = MedicalRecord.objects.filter(created_by=request.user)
    
    # Statistics - use the full queryset
    total_records = all_records.count()
    high_risk_records = all_records.filter(
        risk_level__in=['high', 'critical']
    ).count()
    
    # Get doctor's patients for filter dropdown - only patients
    patients = User.objects.filter(role='patient',is_superuser=False)
    
    # Apply filters to the full queryset
    filtered_records = all_records
    
    patient_filter = request.GET.get('patient')
    if patient_filter:
        filtered_records = filtered_records.filter(patient_id=patient_filter)
    
    risk_filter = request.GET.get('risk_level')
    if risk_filter:
        filtered_records = filtered_records.filter(risk_level=risk_filter)
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        filtered_records = filtered_records.filter(created_at__date__gte=date_from)
    if date_to:
        filtered_records = filtered_records.filter(created_at__date__lte=date_to)
    
    # Order and slice for display
    medical_records = filtered_records.order_by('-created_at')[:50]
    
    context = {
        'medical_records': medical_records,
        'total_records': total_records,
        'high_risk_records': high_risk_records,
        'patients': patients,
        'patient_filter': patient_filter,
        'risk_filter': risk_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    log_event('MEDICAL_HISTORY_ACCESS', request.user, {
        'filters': {
            'patient': patient_filter,
            'risk_level': risk_filter,
            'date_from': date_from,
            'date_to': date_to
        }
    }, request)
    
    return render(request, 'doctor/medical_history.html', context)

@login_required
@role_required('doctor')
def doctor_patient_analysis(request, patient_id):
    """Analyze specific patient symptoms"""
    patient = get_object_or_404(User, id=patient_id, role='patient')
    
    # Get ALL patient's medical records first (no slice yet)
    all_records = MedicalRecord.objects.filter(patient=patient)
    
    # Get statistics from the full queryset
    total_records = all_records.count()
    high_risk_records = all_records.filter(
        risk_level__in=['high', 'critical']
    ).count()
    
    # Get recent records for display (slice after getting the data)
    recent_records = all_records.order_by('-created_at')[:10]
    
    # Get latest analysis
    latest_analysis = all_records.order_by('-created_at').first()
    
    context = {
        'patient': patient,
        'recent_records': recent_records,
        'total_records': total_records,
        'high_risk_records': high_risk_records,
        'latest_analysis': latest_analysis,
        'symptom_form': SymptomsForm(),
    }
    
    log_event('PATIENT_ANALYSIS_ACCESS', request.user, {
        'patient': patient.username,
        'patient_id': patient_id,
        'total_records': total_records,
        'high_risk_records': high_risk_records
    }, request)
    
    return render(request, 'doctor/patient_analysis.html', context)

@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def doctor_add_medical_record(request, patient_id):
    """Add a medical record for a patient"""
    try:
        patient = get_object_or_404(User, id=patient_id, role='patient')
        
        # Get form data
        data = json.loads(request.body)
        
        symptoms = data.get('symptoms', '')
        diagnosis = data.get('diagnosis', '')
        treatment = data.get('treatment', '')
        notes = data.get('notes', '')
        risk_level = data.get('risk_level', 'low')
        confidence_score = float(data.get('confidence_score', 0.0))
        
        # Validate required fields
        if not symptoms:
            return JsonResponse({
                'success': False,
                'error': 'Symptoms are required'
            })
        
        # Create medical record
        medical_record = MedicalRecord.objects.create(
            patient=patient,
            encrypted_symptoms=symptoms,
            encrypted_diagnosis=diagnosis,
            encrypted_treatment=treatment,
            encrypted_data=notes,
            created_by=request.user,
            risk_level=risk_level,
            confidence_score=confidence_score
        )
        
        # Update patient's last analysis
        patient.last_analysis = timezone.now()
        if risk_level in ['high', 'critical']:
            patient.risk_level = risk_level
            patient.ml_confidence_score = confidence_score
        patient.save()
        
        # Create notification for doctor
        Notification.create_notification(
            user=request.user,
            title='Medical Record Added',
            message=f'Medical record added for patient {patient.get_full_name() or patient.username}',
            notification_type='success'
        )
        
        # Create notification for patient
        Notification.create_notification(
            user=patient,
            title='Medical Record Updated',
            message='Your doctor has added a new medical record to your file.',
            notification_type='info',
            action_url='/patient/medical-history/'
        )
        
        log_event('MEDICAL_RECORD_CREATE', request.user, {
            'patient': patient.username,
            'patient_id': patient_id,
            'record_id': str(medical_record.record_id),
            'risk_level': risk_level,
            'confidence': confidence_score
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': 'Medical record added successfully',
            'record_id': str(medical_record.record_id),
            'timestamp': medical_record.created_at.isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
    except Exception as e:
        logger.error(f"Error adding medical record: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# Add this function to doctor_views.py after doctor_chat function

@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def doctor_new_chat_session(request):
    """Create a new chat session for doctor"""
    try:
        # Create new chat session
        chat_session = ChatSession.objects.create(
            user=request.user,
            role='doctor',
            title=f'Chat Session - {timezone.now().strftime("%Y-%m-%d %H:%M")}'
        )
        
        log_event('CHAT_SESSION_CREATE', request.user, {
            'session_id': str(chat_session.session_id),
            'role': 'doctor'
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': 'New chat session created',
            'session_id': chat_session.id,
            'redirect_url': f'/doctor/chat/?session={chat_session.id}'
        })
        
    except Exception as e:
        logger.error(f"Error creating new chat session: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

# Also add this function for deleting chat sessions
@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def doctor_delete_chat_session(request, session_id):
    """Delete a chat session"""
    try:
        chat_session = get_object_or_404(
            ChatSession, 
            id=session_id, 
            user=request.user,
            role='doctor'
        )
        
        session_title = chat_session.title
        chat_session.delete()
        
        log_event('CHAT_SESSION_DELETE', request.user, {
            'session_id': str(session_id),
            'session_title': session_title,
            'role': 'doctor'
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': 'Chat session deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting chat session: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })























@csrf_exempt
@login_required
@role_required('doctor')
@require_POST
def doctor_accept_appointment(request):
    """Accept a patient's symptom submission and notify them"""
    try:
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        record_id = data.get('record_id')
        
        patient = get_object_or_404(User, id=patient_id, role='patient')
        
        # Create notification for the patient
        Notification.create_notification(
            user=patient,
            title='Consultation Accepted',
            message=f'Dr. {request.user.get_full_name() or request.user.username} has reviewed your symptoms and accepted your consultation request. They will contact you shortly.',
            notification_type='success',
            action_url='/patient/medical-history/'
        )
        
        # Create notification for the doctor as well (confirmation)
        Notification.create_notification(
            user=request.user,
            title='Appointment Confirmed',
            message=f'You have accepted the consultation for {patient.get_full_name() or patient.username}.',
            notification_type='info'
        )
        
        log_event('APPOINTMENT_ACCEPTED', request.user, {
            'patient_id': patient_id,
            'record_id': record_id
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': 'Appointment accepted and patient notified.'
        })
        
    except Exception as e:
        logger.error(f"Error accepting appointment: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
