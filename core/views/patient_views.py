# core/views/patient_views.py - Complete Updated Version
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
import json
import logging
import requests
from django.conf import settings
from datetime import datetime, timedelta

from core.decorators import role_required
from core.models import User, MedicalRecord, ChatSession, ChatMessage, Notification, Appointment
from core.forms import PatientProfileForm, SymptomsForm, AppointmentForm
from core.utils import log_event, query_ollama, ml_predict

logger = logging.getLogger(__name__)

def get_available_ollama_models():
    """Get list of available Ollama models"""
    try:
        ollama_url = getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434')
        
        response = requests.get(f"{ollama_url}/api/tags", timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = []
            
            for model in data.get('models', []):
                model_name = model.get('name', '')
                if model_name:
                    models.append(model_name)
            
            return models if models else []
        else:
            logger.error(f"Failed to get models: {response.status_code}")
            return []
    except requests.exceptions.ConnectionError:
        logger.warning("Ollama not connected")
        return []
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        return []

@login_required
@role_required('patient')
def patient_dashboard(request):
    """Patient dashboard"""
    # Get medical records
    medical_records = MedicalRecord.objects.filter(
        patient=request.user
    ).order_by('-created_at')[:5]
    
    # Get chat sessions
    chat_sessions = ChatSession.objects.filter(
        user=request.user,
        role='patient'
    ).order_by('-updated_at')[:5]
    
    # Get notifications for dropdown
    recent_notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    # Get unread count for badge
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    # Get upcoming appointments
    today = timezone.now().date()
    upcoming_appointments = Appointment.objects.filter(
        patient=request.user,
        status__in=['confirmed', 'pending'],
        appointment_date__gte=today
    ).order_by('appointment_date', 'appointment_time')[:5]
    
    # Statistics
    total_records = MedicalRecord.objects.filter(patient=request.user).count()
    total_appointments = Appointment.objects.filter(patient=request.user).count()
    pending_appointments = Appointment.objects.filter(
        patient=request.user,
        status='pending'
    ).count()
    
    # Get today's appointments
    today_appointments = Appointment.objects.filter(
        patient=request.user,
        appointment_date=today,
        status='confirmed'
    ).order_by('appointment_time')
    
    # Health Insights (Custom feature for "useful info popping in")
    insights = []
    if total_records == 0:
        insights.append({
            'type': 'new',
            'title': 'Welcome to your Health Portal!',
            'content': 'Start your first symptom check to get personalized AI health analysis.',
            'icon': 'fa-hand-sparkles'
        })
    elif request.user.risk_level == 'critical' or request.user.risk_level == 'high':
        insights.append({
            'type': 'warning',
            'title': 'High Risk Alert',
            'content': 'Your recent analysis indicates high risk. Please consult your doctor or review your recommendations.',
            'icon': 'fa-exclamation-circle'
        })
    else:
        insights.append({
            'type': 'info',
            'title': 'Good Progress!',
            'content': 'Your health monitoring is active. Stay hydrated and continue your regular check-ins.',
            'icon': 'fa-check-circle'
        })

    # Add a random health tip
    import random
    tips = [
        "Include more leaf greens in your diet for essential vitamins.",
        "Walking just 30 minutes a day can significantly improve heart health.",
        "Maintain a consistent sleep schedule even on weekends.",
        "Limit screen time an hour before bed for better sleep quality.",
        "Drinking water throughout the day helps maintain focus and energy."
    ]
    insights.append({
        'type': 'tip',
        'title': 'Daily Health Tip',
        'content': random.choice(tips),
        'icon': 'fa-lightbulb'
    })

    context = {
        'medical_records': medical_records,
        'chat_sessions': chat_sessions,
        'recent_notifications': recent_notifications,
        'unread_notifications_count': unread_notifications_count,
        'upcoming_appointments': upcoming_appointments,
        'today_appointments': today_appointments,
        'total_records': total_records,
        'total_appointments': total_appointments,
        'pending_appointments': pending_appointments,
        'risk_level': request.user.risk_level or 'Not assessed',
        'last_analysis': request.user.last_analysis,
        'symptom_form': SymptomsForm(),
        'health_insights': insights,
    }
    
    log_event('DASHBOARD_ACCESS', request.user, {'dashboard': 'patient'}, request)
    return render(request, 'patient/dashboard.html', context)

@login_required
@role_required('patient')
def patient_chat(request):
    """Patient chat interface with Ollama"""
    # Check if we need a new session
    if request.GET.get('new'):
        chat_session = ChatSession.objects.create(
            user=request.user,
            role='patient',
            title=f'Health Chat - {timezone.now().strftime("%H:%M")}'
        )
        return redirect('patient_chat')
    
    # Get or create active chat session
    session_id = request.GET.get('session')
    if session_id:
        try:
            chat_session = ChatSession.objects.get(
                id=session_id,
                user=request.user,
                role='patient'
            )
        except ChatSession.DoesNotExist:
            chat_session = ChatSession.objects.create(
                user=request.user,
                role='patient',
                title=f'Health Chat - {timezone.now().strftime("%Y-%m-%d")}'
            )
    else:
        # Get latest chat session or create new
        chat_session = ChatSession.objects.filter(
            user=request.user,
            role='patient'
        ).order_by('-updated_at').first()
        
        if not chat_session:
            chat_session = ChatSession.objects.create(
                user=request.user,
                role='patient',
                title=f'Health Chat - {timezone.now().strftime("%Y-%m-%d")}'
            )
    
    # Get chat messages
    messages = ChatMessage.objects.filter(session=chat_session).order_by('created_at')
    
    # Get available models
    available_models = get_available_ollama_models()
    
    # Get selected model from session
    selected_model = request.session.get('patient_ollama_model', '')
    
    # If no model is selected or the selected model is not available, use first available
    if not selected_model or selected_model not in available_models:
        if available_models:
            selected_model = available_models[0]
            request.session['patient_ollama_model'] = selected_model
            request.session.save()
        else:
            selected_model = 'No models available'
    
    # Get chat history
    chat_history = ChatSession.objects.filter(
        user=request.user,
        role='patient'
    ).order_by('-updated_at')[:10]
    
    # Get patient's medical info for context
    patient_info = {
        'name': request.user.get_full_name() or request.user.username,
        'risk_level': request.user.risk_level or 'Not assessed',
        'last_analysis': request.user.last_analysis
    }
    
    context = {
        'chat_session': chat_session,
        'messages': messages,
        'available_models': available_models,
        'selected_model': selected_model,
        'chat_history': chat_history,
        'patient_info': patient_info,
    }
    return render(request, 'patient/chat.html', context)

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_chat_send(request):
    """Send message in patient chat using Ollama"""
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        # Get available models
        available_models = get_available_ollama_models()
        
        # Get model name from session
        model_name = data.get('model', request.session.get('patient_ollama_model', ''))
        
        # If no model is set or model not available, use first available model
        if not model_name or model_name not in available_models:
            if available_models:
                model_name = available_models[0]
                request.session['patient_ollama_model'] = model_name
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
            role='patient'
        )
        
        # Save user message
        user_message = ChatMessage.objects.create(
            session=chat_session,
            message_type='user',
            content=message
        )
        
        # Construct prompt with patient context
        patient_context = f"""
        Patient Context:
        - Name: {request.user.get_full_name() or request.user.username}
        - Age: {request.user.date_of_birth.strftime('%Y-%m-%d') if request.user.date_of_birth else 'Not provided'}
        - Risk Level: {request.user.risk_level or 'Not assessed'}
        """
        
        if request.user.last_analysis:
            patient_context += f"\n- Last Analysis: {request.user.last_analysis.strftime('%Y-%m-%d')}"
        
        # Get recent symptoms if available
        recent_record = MedicalRecord.objects.filter(patient=request.user).order_by('-created_at').first()
        if recent_record:
            try:
                symptoms = json.loads(recent_record.encrypted_symptoms)
                if symptoms:
                    patient_context += f"\n- Recent Symptoms: {', '.join(symptoms[:3])}"
            except:
                pass
        
        # Create the prompt for Ollama with medical disclaimer
        prompt = f"""{patient_context}

        You are a helpful health assistant for patients. The patient has asked:
        "{message}"

        IMPORTANT GUIDELINES:
        1. DO NOT provide medical diagnoses
        2. DO NOT prescribe medications
        3. DO NOT suggest specific treatments
        4. DO provide general health information
        5. DO encourage consulting with healthcare professionals
        6. DO suggest lifestyle tips and wellness advice
        7. DO explain medical terms in simple language
        8. DO be empathetic and supportive

        Provide a helpful, informative, and supportive response that follows these guidelines.
        Response:"""
        
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
            chat_session.title = f"Health Chat: {short_message}"
            chat_session.save()
        
        # Update last updated time
        chat_session.updated_at = timezone.now()
        chat_session.save()
        
        log_event('CHAT_INTERACTION', request.user, {
            'role': 'patient',
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
        logger.error(f"Patient chat error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_change_model(request):
    """Change Ollama model for patient chat"""
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
        request.session['patient_ollama_model'] = model_name
        request.session.save()
        
        log_event('MODEL_CHANGE', request.user, {
            'old_model': request.session.get('patient_ollama_model'),
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
@role_required('patient')
@require_POST
def test_patient_ollama_connection(request):
    """Test Ollama connection for patient"""
    try:
        ollama_url = getattr(settings, 'OLLAMA_API_URL', 'http://localhost:11434')
        
        # First, try to get available models
        try:
            response = requests.get(f"{ollama_url}/api/tags", timeout=10)
            
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
                current_model = request.session.get('patient_ollama_model', '')
                
                # If no current model or it's not available, use first available
                if not current_model or current_model not in models:
                    current_model = models[0]
                    request.session['patient_ollama_model'] = current_model
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
                    test_prompt = "Hello, I'm a patient. Can you help me with general health questions?"
                    test_payload = {
                        "model": current_model,
                        "prompt": test_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9
                        }
                    }
                    
                    gen_response = requests.post(
                        f"{ollama_url}/api/generate", 
                        json=test_payload, 
                        timeout=15
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

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_new_chat_session(request):
    """Create a new chat session"""
    try:
        chat_session = ChatSession.objects.create(
            user=request.user,
            role='patient',
            title=f'Health Chat - {timezone.now().strftime("%H:%M")}'
        )
        
        log_event('NEW_CHAT_SESSION', request.user, {
            'session_id': str(chat_session.session_id),
            'role': 'patient'
        }, request)
        
        return JsonResponse({
            'success': True,
            'session_id': chat_session.id,
            'session_uuid': str(chat_session.session_id),
            'title': chat_session.title,
            'redirect_url': f'/patient/chat/?session={chat_session.id}'
        })
        
    except Exception as e:
        logger.error(f"New chat session error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_delete_chat_session(request, session_id):
    """Delete a chat session"""
    try:
        chat_session = ChatSession.objects.get(
            id=session_id,
            user=request.user,
            role='patient'
        )
        
        session_uuid = str(chat_session.session_id)
        chat_session.delete()
        
        log_event('DELETE_CHAT_SESSION', request.user, {
            'session_id': session_uuid,
            'role': 'patient'
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': 'Chat session deleted successfully'
        })
        
    except ChatSession.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Chat session not found'
        })
    except Exception as e:
        logger.error(f"Delete chat session error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@role_required('patient')
def patient_notifications(request):
    """Patient notifications page"""
    # Get filter parameters
    notification_type = request.GET.get('type', '')
    is_read = request.GET.get('read', '')
    sort_by = request.GET.get('sort', 'newest')
    
    # Base queryset
    notifications = Notification.objects.filter(user=request.user)
    
    # Apply filters
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    if is_read == 'read':
        notifications = notifications.filter(is_read=True)
    elif is_read == 'unread':
        notifications = notifications.filter(is_read=False)
    
    # Apply sorting
    if sort_by == 'oldest':
        notifications = notifications.order_by('created_at')
    elif sort_by == 'unread':
        notifications = notifications.order_by('is_read', '-created_at')
    else:  # newest
        notifications = notifications.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get statistics
    total_notifications = notifications.count()
    unread_count = notifications.filter(is_read=False).count()
    read_count = notifications.filter(is_read=True).count()
    
    # Get notification types for filter
    notification_types = Notification._meta.get_field('notification_type').choices

    
    # Get recent notifications for sidebar
    recent_notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    
    # Get unread count for badge
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    context = {
        'notifications': page_obj,
        'total_notifications': total_notifications,
        'unread_count': unread_count,
        'read_count': read_count,
        'notification_type': notification_type,
        'is_read': is_read,
        'sort_by': sort_by,
        'notification_types': notification_types,
        'recent_notifications': recent_notifications,
        'unread_notifications_count': unread_notifications_count,
    }
    
    log_event('NOTIFICATIONS_VIEW', request.user, {
        'filters': {
            'type': notification_type,
            'read': is_read,
            'sort': sort_by
        }
    }, request)
    
    return render(request, 'patient/patient_notify.html', context)

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user
        )
        
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        
        log_event('NOTIFICATION_MARKED_READ', request.user, {
            'notification_id': notification_id,
            'notification_title': notification.title
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': 'Notification marked as read'
        })
        
    except Notification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notification not found'
        })
    except Exception as e:
        logger.error(f"Mark notification read error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_mark_all_read(request):
    """Mark all notifications as read"""
    try:
        updated_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        log_event('ALL_NOTIFICATIONS_MARKED_READ', request.user, {
            'count': updated_count
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': f'Marked {updated_count} notifications as read'
        })
        
    except Exception as e:
        logger.error(f"Mark all notifications read error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_delete_notification(request, notification_id):
    """Delete a notification"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user
        )
        
        notification_title = notification.title
        notification.delete()
        
        log_event('NOTIFICATION_DELETED', request.user, {
            'notification_id': notification_id,
            'notification_title': notification_title
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': 'Notification deleted successfully'
        })
        
    except Notification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notification not found'
        })
    except Exception as e:
        logger.error(f"Delete notification error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_delete_all_read(request):
    """Delete all read notifications"""
    try:
        deleted_count, _ = Notification.objects.filter(
            user=request.user,
            is_read=True
        ).delete()
        
        log_event('ALL_READ_NOTIFICATIONS_DELETED', request.user, {
            'count': deleted_count
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': f'Deleted {deleted_count} read notifications'
        })
        
    except Exception as e:
        logger.error(f"Delete all read notifications error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@role_required('patient')
def patient_medical_history(request):
    """View medical history"""
    medical_records = MedicalRecord.objects.filter(
        patient=request.user
    ).order_by('-created_at')
    
    # Statistics
    total_records = medical_records.count()
    high_risk_records = medical_records.filter(
        risk_level__in=['high', 'critical']
    ).count()
    
    # Get unread notification count for badge
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    context = {
        'medical_records': medical_records,
        'total_records': total_records,
        'high_risk_records': high_risk_records,
        'unread_notifications_count': unread_notifications_count,
    }
    
    log_event('MEDICAL_HISTORY_VIEW', request.user, {
        'total_records': total_records,
        'high_risk_records': high_risk_records
    }, request)
    
    return render(request, 'patient/medical_history.html', context)

@login_required
@role_required('patient')
def patient_appointments(request):
    """Patient appointments management"""
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    doctor_filter = request.GET.get('doctor', '')
    date_filter = request.GET.get('date', '')
    
    # Base queryset
    appointments = Appointment.objects.filter(patient=request.user)
    
    # Apply filters
    if status_filter:
        appointments = appointments.filter(status=status_filter)
    
    if doctor_filter:
        appointments = appointments.filter(doctor_id=doctor_filter)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            appointments = appointments.filter(appointment_date=filter_date)
        except ValueError:
            pass
    
    # Order by date and time
    appointments = appointments.order_by('-appointment_date', 'appointment_time')
    
    # Get available doctors for filter
    doctors = User.objects.filter(role='doctor', is_active=True)
    
    # Statistics
    total_appointments = appointments.count()
    upcoming_appointments = appointments.filter(
        appointment_date__gte=timezone.now().date(),
        status='confirmed'
    ).count()
    pending_appointments = appointments.filter(status='pending').count()
    
    # Get unread notification count for badge
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    context = {
        'appointments': appointments,
        'doctors': doctors,
        'total_appointments': total_appointments,
        'upcoming_appointments': upcoming_appointments,
        'pending_appointments': pending_appointments,
        'status_filter': status_filter,
        'doctor_filter': doctor_filter,
        'date_filter': date_filter,
        'unread_notifications_count': unread_notifications_count,
    }
    
    log_event('APPOINTMENTS_VIEW', request.user, {
        'filters': {
            'status': status_filter,
            'doctor': doctor_filter,
            'date': date_filter
        }
    }, request)
    
    return render(request, 'patient/appointments.html', context)

@login_required
@role_required('patient')
def patient_appointment_detail(request, appointment_id):
    """View appointment details"""
    appointment = get_object_or_404(
        Appointment,
        appointment_id=appointment_id,
        patient=request.user
    )
    
    # Get unread notification count for badge
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    context = {
        'appointment': appointment,
        'doctor': appointment.doctor,
        'unread_notifications_count': unread_notifications_count,
    }
    
    log_event('APPOINTMENT_DETAIL_VIEW', request.user, {
        'appointment_id': str(appointment_id),
        'doctor': appointment.doctor.username
    }, request)
    
    return render(request, 'patient/appointment_detail.html', context)

@login_required
@role_required('patient')
def patient_book_appointment(request, doctor_id=None):
    """Book an appointment with a doctor"""
    doctor = None
    if doctor_id:
        doctor = get_object_or_404(
            User, 
            id=doctor_id, 
            role='doctor',
            is_active=True
        )
    
    # Get unread notification count for badge
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.patient = request.user
            
            if not doctor and form.cleaned_data.get('doctor'):
                doctor = form.cleaned_data['doctor']
            
            appointment.doctor = doctor
            
            # Check for scheduling conflicts
            conflicting_appointments = Appointment.objects.filter(
                patient=request.user,
                appointment_date=appointment.appointment_date,
                appointment_time=appointment.appointment_time,
                status__in=['confirmed', 'pending']
            )
            
            if conflicting_appointments.exists():
                messages.error(request, 'You already have an appointment at this time.')
            else:
                appointment.save()
                
                # Create notification for doctor
                Notification.create_notification(
                    user=doctor,
                    title='New Appointment Request',
                    message=f'Patient {request.user.get_full_name()} has requested an appointment',
                    notification_type='info',
                    action_url=f'/doctor/appointments/{appointment.appointment_id}/'
                )
                
                # Create notification for patient
                Notification.create_notification(
                    user=request.user,
                    title='Appointment Requested',
                    message=f'Your appointment request with Dr. {doctor.get_full_name()} has been sent',
                    notification_type='success',
                    action_url=f'/patient/appointments/{appointment.appointment_id}/'
                )
                
                messages.success(request, 'Appointment requested successfully!')
                log_event('APPOINTMENT_BOOKED', request.user, {
                    'doctor': doctor.username,
                    'date': appointment.appointment_date.strftime('%Y-%m-%d'),
                    'time': appointment.appointment_time.strftime('%H:%M'),
                    'type': appointment.appointment_type
                }, request)
                
                return redirect('patient_appointments')
    else:
        initial_data = {}
        if doctor:
            initial_data['doctor'] = doctor
        
        form = AppointmentForm(initial=initial_data)
    
    # Get available doctors
    doctors = User.objects.filter(
        role='doctor',
        status='approved',
        is_active=True
    ).order_by('specialization')
    
    # Get available time slots for next 7 days
    available_slots = get_available_time_slots(doctor)
    
    context = {
        'form': form,
        'doctor': doctor,
        'doctors': doctors,
        'available_slots': available_slots,
        'unread_notifications_count': unread_notifications_count,
    }
    
    return render(request, 'patient/book_appointment.html', context)

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_cancel_appointment(request, appointment_id):
    """Cancel an appointment"""
    try:
        appointment = get_object_or_404(
            Appointment,
            appointment_id=appointment_id,
            patient=request.user
        )
        
        if appointment.status == 'cancelled':
            return JsonResponse({
                'success': False,
                'error': 'Appointment already cancelled'
            })
        
        if not appointment.can_be_cancelled():
            return JsonResponse({
                'success': False,
                'error': 'Cannot cancel appointment less than 1 hour before'
            })
        
        old_status = appointment.status
        appointment.status = 'cancelled'
        appointment.save()
        
        # Create notification for doctor
        Notification.create_notification(
            user=appointment.doctor,
            title='Appointment Cancelled',
            message=f'Patient {request.user.get_full_name()} has cancelled their appointment',
            notification_type='warning',
            action_url=f'/doctor/appointments/{appointment_id}/'
        )
        
        # Create notification for patient
        Notification.create_notification(
            user=request.user,
            title='Appointment Cancelled',
            message=f'Your appointment with Dr. {appointment.doctor.get_full_name()} has been cancelled',
            notification_type='info',
            action_url=f'/patient/appointments/'
        )
        
        log_event('APPOINTMENT_CANCELLED', request.user, {
            'appointment_id': str(appointment_id),
            'old_status': old_status,
            'doctor': appointment.doctor.username,
            'date': appointment.appointment_date.strftime('%Y-%m-%d'),
            'time': appointment.appointment_time.strftime('%H:%M')
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': 'Appointment cancelled successfully'
        })
        
    except Exception as e:
        logger.error(f"Appointment cancellation error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_reschedule_appointment(request, appointment_id):
    """Reschedule an appointment"""
    try:
        appointment = get_object_or_404(
            Appointment,
            appointment_id=appointment_id,
            patient=request.user
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
            patient=request.user,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            status__in=['confirmed', 'pending']
        ).exclude(appointment_id=appointment_id)
        
        if conflicting_appointments.exists():
            return JsonResponse({
                'success': False,
                'error': 'You already have an appointment at this time'
            })
        
        old_date = appointment.appointment_date
        old_time = appointment.appointment_time
        
        appointment.appointment_date = appointment_date
        appointment.appointment_time = appointment_time
        appointment.status = 'pending'  # Reset to pending for doctor approval
        appointment.save()
        
        # Create notification for doctor
        Notification.create_notification(
            user=appointment.doctor,
            title='Appointment Reschedule Request',
            message=f'Patient {request.user.get_full_name()} has requested to reschedule appointment',
            notification_type='info',
            action_url=f'/doctor/appointments/{appointment_id}/'
        )
        
        # Create notification for patient
        Notification.create_notification(
            user=request.user,
            title='Appointment Rescheduled',
            message=f'Your appointment with Dr. {appointment.doctor.get_full_name()} has been rescheduled (pending approval)',
            notification_type='info',
            action_url=f'/patient/appointments/{appointment_id}/'
        )
        
        # Log the event
        log_event('APPOINTMENT_RESCHEDULED', request.user, {
            'appointment_id': str(appointment_id),
            'old_datetime': f"{old_date} {old_time}",
            'new_datetime': f"{appointment_date} {appointment_time}",
            'doctor': appointment.doctor.username
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': 'Appointment rescheduled successfully (pending doctor approval)',
            'new_date': appointment_date.strftime('%Y-%m-%d'),
            'new_time': appointment_time.strftime('%H:%M')
        })
        
    except Exception as e:
        logger.error(f"Appointment reschedule error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

def get_available_time_slots(doctor=None):
    """Get available time slots for booking"""
    # Default time slots (9 AM to 5 PM, 30-minute intervals)
    base_slots = []
    for hour in range(9, 17):
        for minute in [0, 30]:
            base_slots.append(f"{hour:02d}:{minute:02d}")
    
    # If doctor is specified, filter out booked slots
    if doctor:
        # Get appointments for next 7 days
        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=7)
        
        booked_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__range=[start_date, end_date],
            status__in=['confirmed', 'pending']
        )
        
        # Group booked slots by date
        booked_slots_by_date = {}
        for appointment in booked_appointments:
            date_str = appointment.appointment_date.strftime('%Y-%m-%d')
            time_str = appointment.appointment_time.strftime('%H:%M')
            
            if date_str not in booked_slots_by_date:
                booked_slots_by_date[date_str] = []
            
            booked_slots_by_date[date_str].append(time_str)
        
        # Generate available slots for each day
        available_slots = {}
        for i in range(7):
            current_date = start_date + timedelta(days=i)
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Filter out booked slots for this date
            booked_slots = booked_slots_by_date.get(date_str, [])
            available_for_date = [slot for slot in base_slots if slot not in booked_slots]
            
            # Only include dates with available slots
            if available_for_date:
                available_slots[date_str] = available_for_date
    
        return available_slots
    
    return {}

@login_required
@role_required('patient')
def patient_symptom_check(request):
    """Symptom checker page"""
    # Get unread notification count for badge
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    if request.method == 'GET':
        # Get common symptoms for selection
        common_symptoms = get_common_symptoms()
        
        # Get doctors for sharing results
        doctors = User.objects.filter(
            role='doctor',
            is_active=True
        ).order_by('specialization')[:10]
        
        # Get patient's recent medical records for context
        recent_records = MedicalRecord.objects.filter(
            patient=request.user
        ).order_by('-created_at')[:3]
        
        context = {
            'common_symptoms': common_symptoms,
            'doctors': doctors,
            'recent_records': recent_records,
            'symptom_form': SymptomsForm(),
            'unread_notifications_count': unread_notifications_count,
        }
        
        return render(request, 'patient/symptom_check.html', context)
    
    elif request.method == 'POST':
        # Process symptom check via AJAX/Multipart
        try:
            # Handle both JSON (legacy/if still used) and Multipart (for files)
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            symptoms_raw = data.get('symptoms', '[]')
            if isinstance(symptoms_raw, str):
                try:
                    symptoms_data = json.loads(symptoms_raw)
                except:
                    symptoms_data = []
            else:
                symptoms_data = symptoms_raw
                
            extra_symptoms = data.get('extra_symptoms', '')
            doctor_id = data.get('doctor_id')
            
            if not symptoms_data and not extra_symptoms:
                return JsonResponse({'success': False, 'error': 'Please select symptoms or provide notes'})
            
            # Extract just the symptom codes for the ML model
            symptom_codes = [s.get('code') for s in symptoms_data if s.get('code')]
            
            # Use the robust ml_predict
            patient_age = 35
            if request.user.date_of_birth:
                today = timezone.now().date()
                dob = request.user.date_of_birth
                patient_age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            
            # Get fuzzy memberships and disease predictions
            result = ml_predict(symptom_codes, patient_age=patient_age)
            
            # Update patient record metadata
            request.user.risk_level = result.get('risk_level', 'medium')
            request.user.ml_confidence_score = result.get('confidence', 0.7)
            request.user.last_analysis = timezone.now()
            request.user.save()
            
            # Handle Past History File
            past_history_file = request.FILES.get('past_history_file')
            
            # Create medical record
            medical_record = MedicalRecord.objects.create(
                patient=request.user,
                encrypted_symptoms=json.dumps(symptoms_data),
                encrypted_data=json.dumps({
                    'notes': extra_symptoms,
                    'gender': data.get('gender'),
                    'occupation': data.get('occupation'),
                    'region': data.get('region'),
                    'duration': data.get('duration'),
                    'frequency': data.get('frequency'),
                    'past_history': data.get('past_history')
                }),
                encrypted_diagnosis=json.dumps(result),
                risk_level=result.get('risk_level', 'medium'),
                confidence_score=result.get('confidence', 0.7),
                risk_score=result.get('risk_score', 0.5),
                fuzzy_membership=result.get('fuzzy_membership', {}),
                patient_age=patient_age,
                symptoms_count=len(symptoms_data),
                past_history_file=past_history_file
            )
            
            # Create notification for patient (confirming submission to doctor)
            Notification.create_notification(
                user=request.user,
                title='Symptoms Sent to Doctor',
                message=f'Your reported symptoms and notes have been sent to your primary care doctor for professional review.',
                notification_type='success',
                action_url=f'/patient/medical-history/'
            )
            
            # Notify ALL doctors or specific doctor if selected
            # For now, let's notify all approved doctors if no specific doctor is assigned
            # Or better, just any doctor who has a relationship with this patient (if we had a mapping)
            # Default: notify all doctors so they see it in their submissions queue
            doctors = User.objects.filter(role='doctor')
            if doctor_id:
                doctors = doctors.filter(id=doctor_id)
            
            for doctor in doctors:
                Notification.create_notification(
                    user=doctor,
                    title='New Patient Submission',
                    message=f'Patient {request.user.get_full_name()} has submitted new symptoms for review.',
                    notification_type='info',
                    action_url=f'/doctor/patient-submissions/'
                )
            
            log_event('SYMPTOM_SUBMISSION', request.user, {
                'symptoms_count': len(symptoms_data),
                'has_notes': bool(extra_symptoms),
                'risk_level': result.get('risk_level')
            }, request)
            
            return JsonResponse({
                'success': True,
                'message': 'Symptoms submitted successfully'
            })
            
        except Exception as e:
            logger.error(f"Symptom check error: {e}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})

def get_common_symptoms():
    """Get list of common symptoms"""
    return [
        {'name': 'Fever', 'code': 'fever', 'icon': 'fas fa-thermometer-half', 'critical': False},
        {'name': 'Cough', 'code': 'cough', 'icon': 'fas fa-lungs', 'critical': False},
        {'name': 'Headache', 'code': 'headache', 'icon': 'fas fa-head-side-virus', 'critical': False},
        {'name': 'Fatigue', 'code': 'fatigue', 'icon': 'fas fa-tired', 'critical': False},
        {'name': 'Nausea', 'code': 'nausea', 'icon': 'fas fa-stomach', 'critical': False},
        {'name': 'Shortness of Breath', 'code': 'shortness_of_breath', 'icon': 'fas fa-wind', 'critical': True},
        {'name': 'Chest Pain', 'code': 'chest_pain', 'icon': 'fas fa-heart', 'critical': True},
        {'name': 'Dizziness', 'code': 'dizziness', 'icon': 'fas fa-dizzy', 'critical': False},
        {'name': 'Sore Throat', 'code': 'sore_throat', 'icon': 'fas fa-head-side-cough', 'critical': False},
        {'name': 'Body Aches', 'code': 'body_ache', 'icon': 'fas fa-running', 'critical': False},
        {'name': 'Loss of Taste/Smell', 'code': 'loss_of_taste_smell', 'icon': 'fas fa-cookie-bite', 'critical': False},
        {'name': 'Diarrhea', 'code': 'diarrhea', 'icon': 'fas fa-toilet', 'critical': False},
        {'name': 'Runny Nose', 'code': 'runny_nose', 'icon': 'fas fa-head-side-cough', 'critical': False},
        {'name': 'Sneezing', 'code': 'sneezing', 'icon': 'fas fa-wind', 'critical': False},
        {'name': 'Muscle Pain', 'code': 'muscle_pain', 'icon': 'fas fa-running', 'critical': False},
        {'name': 'Chills', 'code': 'chills', 'icon': 'fas fa-snowflake', 'critical': False},
    ]

def get_enhanced_ml_prediction(symptoms_data):
    """Get enhanced ML prediction"""
    try:
        # Extract symptom codes
        symptom_codes = [s.get('code') for s in symptoms_data if s.get('code')]
        
        # Import ML model function
        from core.ml_model import get_ml_prediction
        ml_result = get_ml_prediction(symptom_codes)
        
        # Enhance the results
        enhanced_result = enhance_prediction(ml_result, symptoms_data)
        
        return enhanced_result
        
    except Exception as e:
        logger.warning(f"ML prediction error, using simulation: {e}")
        return simulate_enhanced_prediction(symptoms_data)

def enhance_prediction(ml_result, symptoms_data):
    """Enhance the ML prediction with additional analysis"""
    
    # Extract data
    prediction = ml_result.get('prediction', 'Unknown')
    confidence = ml_result.get('confidence', 0.5)
    
    # Count critical symptoms
    critical_count = sum(1 for s in symptoms_data if s.get('critical') == True)
    symptom_count = len(symptoms_data)
    
    # Adjust risk level based on severity
    severity_scores = {
        'low': 1,
        'medium': 2,
        'high': 3
    }
    total_severity = sum(severity_scores.get(s.get('severity', 'medium'), 1) for s in symptoms_data)
    avg_severity = total_severity / symptom_count if symptom_count > 0 else 1
    
    # Adjust confidence based on symptoms
    adjusted_confidence = confidence * (0.8 + (symptom_count * 0.05) + (critical_count * 0.1))
    adjusted_confidence = min(max(adjusted_confidence, 0.1), 0.95)
    
    # Determine risk level
    risk_score = (critical_count * 3) + (avg_severity * symptom_count * 0.5)
    
    if risk_score > 10 or critical_count >= 2:
        risk_level = 'critical'
    elif risk_score > 6 or critical_count >= 1:
        risk_level = 'high'
    elif risk_score > 3 or symptom_count >= 3:
        risk_level = 'medium'
    else:
        risk_level = 'low'
    
    # Get conditions and recommendations
    conditions_info = get_conditions_info(prediction, symptoms_data)
    recommendations = get_recommendations(risk_level, symptoms_data, prediction)
    
    # Create detailed explanation
    detailed_explanation = f"""
    Analysis Details:
    - Symptoms analyzed: {symptom_count}
    - Critical symptoms: {critical_count}
    - Average severity: {avg_severity:.1f}/3
    - Risk score: {risk_score:.1f}
    - Primary prediction: {prediction}
    - Confidence: {adjusted_confidence:.1%}
    """
    
    return {
        'prediction': prediction,
        'risk_level': risk_level,
        'confidence': adjusted_confidence,
        'possible_conditions': conditions_info,
        'recommendations': recommendations,
        'detailed_explanation': detailed_explanation,
        'symptoms_analyzed': symptom_count,
        'critical_symptoms_count': critical_count
    }

def get_conditions_info(prediction, symptoms_data):
    """Get possible conditions based on prediction and symptoms"""
    
    # Condition database
    conditions_db = {
        'Influenza': [
            {'name': 'Influenza (Flu)', 'probability': 85},
            {'name': 'Common Cold', 'probability': 45},
            {'name': 'COVID-19', 'probability': 60}
        ],
        'Common Cold': [
            {'name': 'Common Cold', 'probability': 90},
            {'name': 'Allergies', 'probability': 40},
            {'name': 'Sinus Infection', 'probability': 30}
        ],
        'COVID-19': [
            {'name': 'COVID-19', 'probability': 75},
            {'name': 'Influenza', 'probability': 50},
            {'name': 'Respiratory Infection', 'probability': 40}
        ],
        'Pneumonia': [
            {'name': 'Pneumonia', 'probability': 80},
            {'name': 'Bronchitis', 'probability': 65},
            {'name': 'Severe Flu', 'probability': 50}
        ],
        'Migraine': [
            {'name': 'Migraine', 'probability': 85},
            {'name': 'Tension Headache', 'probability': 70},
            {'name': 'Cluster Headache', 'probability': 40}
        ],
        'Gastroenteritis': [
            {'name': 'Gastroenteritis', 'probability': 80},
            {'name': 'Food Poisoning', 'probability': 60},
            {'name': 'Irritable Bowel', 'probability': 35}
        ]
    }
    
    # Check for specific symptom patterns
    symptom_names = [s.get('name', '').lower() for s in symptoms_data]
    
    # Additional conditions based on symptoms
    extra_conditions = []
    
    if any(s in symptom_names for s in ['fever', 'cough', 'shortness of breath']):
        extra_conditions.append({'name': 'Respiratory Infection', 'probability': 70})
    
    if any(s in symptom_names for s in ['headache', 'dizziness', 'fatigue']):
        extra_conditions.append({'name': 'Viral Infection', 'probability': 65})
    
    if any(s in symptom_names for s in ['nausea', 'diarrhea', 'body aches']):
        extra_conditions.append({'name': 'Gastrointestinal Issue', 'probability': 60})
    
    # Get conditions for the prediction
    conditions = conditions_db.get(prediction, [
        {'name': prediction, 'probability': 75},
        {'name': 'General Viral Infection', 'probability': 60},
        {'name': 'Bacterial Infection', 'probability': 40}
    ])
    
    # Add extra conditions
    conditions.extend(extra_conditions[:2])
    
    return conditions

def get_recommendations(risk_level, symptoms_data, prediction):
    """Get personalized recommendations"""
    
    recommendations = []
    symptom_names = [s.get('name', '').lower() for s in symptoms_data]
    
    # Base recommendations by risk level
    if risk_level == 'critical':
        recommendations = [
            '🚨 SEEK IMMEDIATE MEDICAL ATTENTION',
            'Call emergency services or go to nearest ER',
            'Do not drive yourself to hospital',
            'Inform someone about your condition'
        ]
    elif risk_level == 'high':
        recommendations = [
            'Consult with a healthcare professional within 24 hours',
            'Get plenty of rest and stay hydrated',
            'Monitor your symptoms closely',
            'Avoid contact with others to prevent spread'
        ]
    elif risk_level == 'medium':
        recommendations = [
            'Schedule a doctor appointment within 2-3 days',
            'Rest and monitor symptoms',
            'Stay hydrated and eat light meals',
            'Use over-the-counter remedies as needed'
        ]
    else:  # low
        recommendations = [
            'Monitor symptoms for 24-48 hours',
            'Get adequate rest',
            'Drink plenty of fluids',
            'Consult doctor if symptoms worsen'
        ]
    
    # Add symptom-specific recommendations
    if any(s in symptom_names for s in ['fever', 'chills']):
        recommendations.append('Monitor your temperature every 4-6 hours')
    
    if any(s in symptom_names for s in ['cough', 'shortness of breath', 'chest pain']):
        recommendations.append('Use a humidifier or steam inhalation')
    
    if any(s in symptom_names for s in ['nausea', 'diarrhea']):
        recommendations.append('Eat bland foods (BRAT diet: bananas, rice, applesauce, toast)')
    
    if any(s in symptom_names for s in ['headache', 'body aches', 'muscle pain']):
        recommendations.append('Consider over-the-counter pain relief as directed')
    
    # Add prediction-specific recommendations
    if 'flu' in prediction.lower() or 'influenza' in prediction.lower():
        recommendations.append('Antiviral medication may be effective if started early')
    
    if 'covid' in prediction.lower():
        recommendations.append('Consider COVID-19 testing')
        recommendations.append('Self-isolate to prevent spread')
    
    return recommendations

def simulate_enhanced_prediction(symptoms_data):
    """Enhanced simulation when ML model fails"""
    
    symptom_count = len(symptoms_data)
    critical_count = sum(1 for s in symptoms_data if s.get('critical') == True)
    
    # Analyze symptom patterns
    symptom_codes = [s.get('code', '').lower() for s in symptoms_data]
    symptom_names = [s.get('name', '').lower() for s in symptoms_data]
    
    # Determine prediction based on symptoms
    if any(s in symptom_codes or s in symptom_names for s in ['fever', 'cough', 'shortness_of_breath', 'shortness of breath']):
        if critical_count > 0:
            prediction = 'Pneumonia or Severe Respiratory Infection'
            confidence = 0.78
            risk_level = 'high'
        else:
            prediction = 'Influenza or Common Cold'
            confidence = 0.72
            risk_level = 'medium'
    
    elif any(s in symptom_codes or s in symptom_names for s in ['headache', 'dizziness', 'fatigue']):
        prediction = 'Migraine or Viral Infection'
        confidence = 0.65
        risk_level = 'medium'
    
    elif any(s in symptom_codes or s in symptom_names for s in ['nausea', 'diarrhea']):
        prediction = 'Gastroenteritis'
        confidence = 0.68
        risk_level = 'medium'
    
    elif any(s in symptom_codes or s in symptom_names for s in ['chest_pain', 'chest pain']):
        prediction = 'Cardiac Concern - Requires Evaluation'
        confidence = 0.82
        risk_level = 'critical' if critical_count > 0 else 'high'
    
    else:
        prediction = 'General Viral Infection'
        confidence = 0.60
        risk_level = 'low' if symptom_count < 3 else 'medium'
    
    # Get conditions and recommendations
    conditions_info = get_conditions_info(prediction, symptoms_data)
    recommendations = get_recommendations(risk_level, symptoms_data, prediction)
    
    # Create detailed explanation
    detailed_explanation = f"""
    Analysis Details:
    - Symptoms analyzed: {symptom_count}
    - Critical symptoms: {critical_count}
    - Prediction based on symptom pattern analysis
    - Primary condition: {prediction}
    - Confidence: {confidence:.1%}
    """
    
    return {
        'prediction': prediction,
        'risk_level': risk_level,
        'confidence': confidence,
        'possible_conditions': conditions_info,
        'recommendations': recommendations,
        'detailed_explanation': detailed_explanation,
        'symptoms_analyzed': symptom_count
    }

@login_required
@role_required('patient')
def patient_profile(request):
    """Patient profile"""
    # Get unread notification count for badge
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    if request.method == 'POST':
        form = PatientProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            
            # Create notification
            Notification.create_notification(
                user=request.user,
                title='Profile Updated',
                message='Your patient profile has been updated successfully.',
                notification_type='success'
            )
            
            log_event('PROFILE_UPDATE', request.user, {'role': 'patient'}, request)
            return redirect('patient_profile')
    else:
        form = PatientProfileForm(instance=request.user)
    
    context = {
        'form': form,
        'unread_notifications_count': unread_notifications_count,
    }
    
    return render(request, 'patient/profile.html', context)

@login_required
@role_required('patient')
def patient_doctors(request):
    """View available doctors"""
    doctors = User.objects.filter(
        role='doctor',
        status='approved',
        is_active=True
    ).order_by('specialization')
    
    # Get statistics
    total_doctors = doctors.count()
    
    # Get unread notification count for badge
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    context = {
        'doctors': doctors,
        'total_doctors': total_doctors,
        'unread_notifications_count': unread_notifications_count,
    }
    
    log_event('DOCTORS_VIEW', request.user, {'total_doctors': total_doctors}, request)
    
    return render(request, 'patient/doctors.html', context)

@login_required
@role_required('patient')
def patient_settings(request):
    """Patient settings page"""
    # Get unread notification count for badge
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    context = {
        'user': request.user,
        'unread_notifications_count': unread_notifications_count,
    }
    
    return render(request, 'patient/settings.html', context)

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_update_notifications(request):
    """Update notification preferences"""
    try:
        data = json.loads(request.body)
        
        # In a real implementation, you would save these preferences
        # For now, we'll just return success
        log_event('NOTIFICATION_PREFERENCES_UPDATE', request.user, {
            'preferences': data
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': 'Notification preferences updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Notification update error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@login_required
@role_required('patient')
@require_POST
def patient_clear_all_notifications(request):
    """Clear all notifications (mark all as read and archive)"""
    try:
        # Mark all as read
        updated_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        # Optional: Archive old notifications
        # You could move them to an archived table or delete them
        
        log_event('ALL_NOTIFICATIONS_CLEARED', request.user, {
            'count': updated_count
        }, request)
        
        return JsonResponse({
            'success': True,
            'message': f'Cleared {updated_count} notifications'
        })
        
    except Exception as e:
        logger.error(f"Clear all notifications error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })