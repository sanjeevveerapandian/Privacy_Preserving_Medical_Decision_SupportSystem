# core/views/researcher_views.py - Complete Updated Version
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages
from django.db.models import Count, Avg, Q
from django.core.paginator import Paginator
import json
import logging
import requests
from django.conf import settings
from datetime import datetime, timedelta

from core.decorators import role_required
from core.models import User, ResearchData, ChatSession, ChatMessage, AuditLog, MLModel, Notification
from core.forms import ResearcherProfileForm
from core.utils import log_event, query_ollama
from core.ml_model import analyze_research_data

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
@role_required('researcher')
def researcher_dashboard(request):
    """Researcher dashboard"""
    # Research statistics
    total_data = ResearchData.objects.count()
    unique_predictions = ResearchData.objects.values('prediction').distinct().count()
    
    # Get chat sessions
    chat_sessions = ChatSession.objects.filter(
        user=request.user,
        role='researcher'
    ).order_by('-updated_at')[:5]
    
    # Get notifications
    recent_notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    # Get unread count for badge
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    # Recent research data
    recent_data = ResearchData.objects.all().order_by('-created_at')[:10]
    
    # Analysis statistics
    analysis_stats = {
        'total_analyses': ResearchData.objects.count(),
        'avg_confidence': ResearchData.objects.aggregate(avg_conf=Avg('confidence'))['avg_conf'] or 0.0,
        'high_risk_data': ResearchData.objects.filter(risk_level__in=['high', 'critical']).count(),
        'recent_analyses': ResearchData.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
    }
    
    context = {
        'total_data': total_data,
        'unique_predictions': unique_predictions,
        'chat_sessions': chat_sessions,
        'recent_notifications': recent_notifications,
        'unread_notifications_count': unread_notifications_count,
        'recent_data': recent_data,
        'analysis_stats': analysis_stats,
    }
    
    log_event('DASHBOARD_ACCESS', request.user, {'dashboard': 'researcher'}, request)
    return render(request, 'researcher/dashboard.html', context)

@login_required
@role_required('researcher')
def researcher_chat(request):
    """Researcher chat interface with Ollama"""
    # Check if we need a new session
    if request.GET.get('new'):
        chat_session = ChatSession.objects.create(
            user=request.user,
            role='researcher',
            title=f'Research Chat - {timezone.now().strftime("%H:%M")}'
        )
        return redirect('researcher_chat')
    
    # Get or create active chat session
    session_id = request.GET.get('session')
    if session_id:
        try:
            chat_session = ChatSession.objects.get(
                id=session_id,
                user=request.user,
                role='researcher'
            )
        except ChatSession.DoesNotExist:
            chat_session = ChatSession.objects.create(
                user=request.user,
                role='researcher',
                title=f'Research Chat - {timezone.now().strftime("%Y-%m-%d")}'
            )
    else:
        # Get latest chat session or create new
        chat_session = ChatSession.objects.filter(
            user=request.user,
            role='researcher'
        ).order_by('-updated_at').first()
        
        if not chat_session:
            chat_session = ChatSession.objects.create(
                user=request.user,
                role='researcher',
                title=f'Research Chat - {timezone.now().strftime("%Y-%m-%d")}'
            )
    
    # Get chat messages
    messages = ChatMessage.objects.filter(session=chat_session).order_by('created_at')
    
    # Get available models
    available_models = get_available_ollama_models()
    
    # Get selected model from session
    selected_model = request.session.get('researcher_ollama_model', '')
    
    # If no model is selected or the selected model is not available, use first available
    if not selected_model or selected_model not in available_models:
        if available_models:
            selected_model = available_models[0]
            request.session['researcher_ollama_model'] = selected_model
            request.session.save()
        else:
            selected_model = 'No models available'
    
    # Get chat history
    chat_history = ChatSession.objects.filter(
        user=request.user,
        role='researcher'
    ).order_by('-updated_at')[:10]
    
    # Get researcher's info for context
    researcher_info = {
        'name': request.user.get_full_name() or request.user.username,
        'institution': request.user.institution or 'Not specified',
        'research_area': request.user.research_area or 'General Research'
    }
    
    context = {
        'chat_session': chat_session,
        'messages': messages,
        'available_models': available_models,
        'selected_model': selected_model,
        'chat_history': chat_history,
        'researcher_info': researcher_info,
    }
    return render(request, 'researcher/chat.html', context)

@csrf_exempt
@login_required
@role_required('researcher')
@require_POST
def researcher_chat_send(request):
    """Send message in researcher chat using Ollama"""
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        # Get available models
        available_models = get_available_ollama_models()
        
        # Get model name from session
        model_name = data.get('model', request.session.get('researcher_ollama_model', ''))
        
        # If no model is set or model not available, use first available model
        if not model_name or model_name not in available_models:
            if available_models:
                model_name = available_models[0]
                request.session['researcher_ollama_model'] = model_name
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
            role='researcher'
        )
        
        # Save user message
        user_message = ChatMessage.objects.create(
            session=chat_session,
            message_type='user',
            content=message
        )
        
        # Construct prompt with researcher context
        researcher_context = f"""
        Researcher Context:
        - Name: {request.user.get_full_name() or request.user.username}
        - Institution: {request.user.institution or 'Not specified'}
        - Research Area: {request.user.research_area or 'General Research'}
        """
        
        # Get recent research data for context
        recent_data = ResearchData.objects.order_by('-created_at')[:5]
        if recent_data.exists():
            researcher_context += f"\n\nRecent Research Data Overview:"
            for i, data in enumerate(recent_data, 1):
                researcher_context += f"\n{i}. Prediction: {data.prediction}, Confidence: {data.confidence:.2f}, Risk: {data.risk_level}"
        
        # Create the prompt for Ollama
        prompt = f"""{researcher_context}

        You are an advanced AI research assistant for medical researchers. The researcher has asked:
        "{message}"

        IMPORTANT GUIDELINES:
        1. Provide scientifically accurate, evidence-based information
        2. Include citations or references when appropriate
        3. Focus on research methodologies and statistical analysis
        4. Discuss data interpretation and implications
        5. Suggest potential research directions
        6. Explain complex concepts in clear terms
        7. Consider ethical implications of research
        8. Stay within the bounds of current scientific knowledge

        Provide a comprehensive, well-structured response that follows these guidelines.
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
            chat_session.title = f"Research Chat: {short_message}"
            chat_session.save()
        
        # Update last updated time
        chat_session.updated_at = timezone.now()
        chat_session.save()
        
        log_event('CHAT_INTERACTION', request.user, {
            'role': 'researcher',
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
        logger.error(f"Researcher chat error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@login_required
@role_required('researcher')
@require_POST
def researcher_change_model(request):
    """Change Ollama model for researcher chat"""
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
        request.session['researcher_ollama_model'] = model_name
        request.session.save()
        
        log_event('MODEL_CHANGE', request.user, {
            'old_model': request.session.get('researcher_ollama_model'),
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
@role_required('researcher')
@require_POST
def test_researcher_ollama_connection(request):
    """Test Ollama connection for researcher"""
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
                current_model = request.session.get('researcher_ollama_model', '')
                
                # If no current model or it's not available, use first available
                if not current_model or current_model not in models:
                    current_model = models[0]
                    request.session['researcher_ollama_model'] = current_model
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
                    test_prompt = "Hello, I'm a medical researcher. Can you help me with research methodology?"
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

@csrf_exempt
@login_required
@role_required('researcher')
@require_POST
def researcher_new_chat_session(request):
    """Create a new chat session"""
    try:
        chat_session = ChatSession.objects.create(
            user=request.user,
            role='researcher',
            title=f'Research Chat - {timezone.now().strftime("%H:%M")}'
        )
        
        log_event('NEW_CHAT_SESSION', request.user, {
            'session_id': str(chat_session.session_id),
            'role': 'researcher'
        }, request)
        
        return JsonResponse({
            'success': True,
            'session_id': chat_session.id,
            'session_uuid': str(chat_session.session_id),
            'title': chat_session.title,
            'redirect_url': f'/researcher/chat/?session={chat_session.id}'
        })
        
    except Exception as e:
        logger.error(f"New chat session error: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@csrf_exempt
@login_required
@role_required('researcher')
@require_POST
def researcher_delete_chat_session(request, session_id):
    """Delete a chat session"""
    try:
        chat_session = ChatSession.objects.get(
            id=session_id,
            user=request.user,
            role='researcher'
        )
        
        session_uuid = str(chat_session.session_id)
        chat_session.delete()
        
        log_event('DELETE_CHAT_SESSION', request.user, {
            'session_id': session_uuid,
            'role': 'researcher'
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
@role_required('researcher')
def researcher_profile(request):
    """Researcher profile"""
    # Get unread notification count for badge
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    if request.method == 'POST':
        form = ResearcherProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            
            # Create notification
            Notification.create_notification(
                user=request.user,
                title='Profile Updated',
                message='Your researcher profile has been updated successfully.',
                notification_type='success'
            )
            
            log_event('PROFILE_UPDATE', request.user, {'role': 'researcher'}, request)
            return redirect('researcher_profile')
    else:
        form = ResearcherProfileForm(instance=request.user)
    
    context = {
        'form': form,
        'unread_notifications_count': unread_notifications_count,
    }
    
    return render(request, 'researcher/profile.html', context)