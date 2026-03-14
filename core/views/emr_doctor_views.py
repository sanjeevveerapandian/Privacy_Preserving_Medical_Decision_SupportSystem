# core/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_POST, require_GET, require_http_methods
import json
import os
from django.conf import settings
from django.utils import timezone
import traceback
from django.db import models
from django.db.models import Count, Avg, Q
import base64
import uuid

# Import forms and models
from core.forms import EMRFileUploadForm, MedicalDocumentForm
from core.models import MedicalDocument, EMRPrediction, EMRExtractionLog, User

# Try to import services
try:
    from core.services.emr_service import EMRProcessor
    from backend.services.audit_service import audit_service
    from core.services.crypto_service import decrypt_data
    EMR_SERVICE_AVAILABLE = True
except ImportError as e:
    EMR_SERVICE_AVAILABLE = False
    print(f"EMR Service import error: {e}")
    
    # Create a dummy processor for testing
    class DummyEMRProcessor:
        def process_document(self, *args, **kwargs):
            return {'success': False, 'error': 'EMR service not available'}
        def predict_from_emr(self, *args, **kwargs):
            return {'success': False, 'error': 'EMR service not available'}
        def save_encrypted_document(self, *args, **kwargs):
            return {'success': False, 'error': 'EMR service not available'}
        def upload_dir(self):
            return os.path.join(settings.MEDIA_ROOT, 'emr_documents')
    
    EMRProcessor = DummyEMRProcessor
    
    # Dummy functions
    def log_event(*args, **kwargs):
        pass
    
    def decrypt_data(*args, **kwargs):
        return {}


@login_required
def emr_dashboard(request):
    """EMR Dashboard"""
    if not request.user.is_patient() and not request.user.is_doctor():
        messages.error(request, "You don't have permission to access EMR.")
        return redirect('dashboard')
    
    context = {
        'active_tab': 'emr',
        'page_title': 'Electronic Medical Records',
        'EMR_SERVICE_AVAILABLE': EMR_SERVICE_AVAILABLE
    }
    
    if request.user.is_patient():
        # Patient view - their own records
        documents = MedicalDocument.objects.filter(patient=request.user).order_by('-upload_date')
        predictions = EMRPrediction.objects.filter(patient=request.user).order_by('-created_at')
        
        context.update({
            'documents': documents,
            'predictions': predictions,
            'total_documents': documents.count(),
            'processed_docs': documents.filter(is_processed=True).count(),
            'pending_docs': documents.filter(processing_status='pending').count(),
        })
    
    elif request.user.is_doctor():
        # Get patients for doctor
        patients = User.objects.filter(role='patient', is_active=True, is_superuser=False).order_by('full_name')
        context['patients'] = patients
        
        # Doctor view - patients' records they have access to
        if 'patient_id' in request.GET and request.GET['patient_id']:
            try:
                patient = get_object_or_404(User, id=request.GET['patient_id'], role='patient')
                documents = MedicalDocument.objects.filter(patient=patient).order_by('-upload_date')
                predictions = EMRPrediction.objects.filter(patient=patient).order_by('-created_at')
                
                context.update({
                    'patient': patient,
                    'documents': documents,
                    'predictions': predictions,
                    'viewing_patient': True,
                })
            except Exception as e:
                messages.error(request, f"Patient not found: {str(e)}")
                documents = MedicalDocument.objects.filter(created_by=request.user).order_by('-upload_date')
                context['documents'] = documents
        else:
            # Show doctor's uploaded documents
            documents = MedicalDocument.objects.filter(created_by=request.user).order_by('-upload_date')
            context['documents'] = documents
    
    return render(request, 'core/emr_dashboard.html', context)


@login_required
@csrf_protect
def upload_emr(request):
    """Upload EMR document"""
    if not (request.user.is_patient() or request.user.is_doctor()):
        messages.error(request, "You don't have permission to upload EMR documents.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = EMRFileUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                document_type = form.cleaned_data['document_type']
                document_date = form.cleaned_data['document_date']
                document_file = form.files['document_file']
                auto_extract = form.cleaned_data['auto_extract']
                
                # Determine patient
                if request.user.is_doctor() and 'patient_id' in request.POST:
                    try:
                        patient = User.objects.get(id=request.POST['patient_id'], role='patient', is_superuser=False)
                    except User.DoesNotExist:
                        messages.error(request, "Selected patient not found.")
                        return redirect('upload_emr')
                else:
                    patient = request.user
                
                if document_type in ['mri', 'xray']:
                    # Special handling for AI Documents: Save raw file for Celery
                    temp_raw_dir = os.path.join(settings.MEDIA_ROOT, 'temp_raw')
                    os.makedirs(temp_raw_dir, exist_ok=True)
                    
                    # Create document record
                    document = MedicalDocument.objects.create(
                        patient=patient,
                        doctor=request.user if request.user.is_doctor() else None,
                        document_type=document_type,
                        document_date=document_date,
                        original_filename=document_file.name,
                        file_size=document_file.size,
                        mime_type=document_file.content_type,
                        ai_status='Pending',
                        processing_status='processing',
                        created_by=request.user
                    )
                    
                    # Update filename to use the ACTUAL document_id from the DB
                    doc_id = str(document.document_id)
                    temp_raw_filename = f"raw_{doc_id}_{document_file.name}"
                    temp_file_path = os.path.join(settings.MEDIA_ROOT, 'temp_raw', temp_raw_filename)
                    
                    with open(temp_file_path, 'wb+') as destination:
                        for chunk in document_file.chunks():
                            destination.write(chunk)
                    
                    # Trigger respective Celery task
                    from emr.tasks import process_mri_ai, process_xray_ai
                    
                    if document_type == 'mri':
                        process_mri_ai.delay(str(document.document_id), temp_file_path)
                        messages.success(request, "MRI upload started. Brain Tumor AI is running.")
                    elif document_type == 'xray':
                        process_xray_ai.delay(str(document.document_id), temp_file_path)
                        messages.success(request, "X-Ray upload started. Smart Diagnostic AI is running.")
                    
                    return redirect('view_emr_document', document_id=document.document_id)

                # Process file upload (Normal for non-MRI)
                emr_processor = EMRProcessor()
                upload_result = emr_processor.save_encrypted_document(
                    document_file, 
                    document_type, 
                    patient.id
                )
                
                if upload_result.get('success'):
                    # Create MedicalDocument record
                    document = MedicalDocument.objects.create(
                        patient=patient,
                        doctor=request.user if request.user.is_doctor() else None,
                        document_type=document_type,
                        original_filename=upload_result['original_filename'],
                        encrypted_filename=upload_result['encrypted_filename'],
                        file_size=upload_result['file_size'],
                        mime_type=upload_result['mime_type'],
                        document_date=document_date,
                        created_by=request.user,
                        processing_status='pending'
                    )
                    
                    # Start processing if auto_extract is enabled
                    if auto_extract and EMR_SERVICE_AVAILABLE:
                        try:
                            processing_result = emr_processor.process_document(
                                document.document_id,
                                auto_extract=True
                            )
                            
                            if processing_result.get('success'):
                                messages.success(request, f"Document uploaded and processed successfully!")
                                
                                # Generate prediction
                                prediction_result = emr_processor.predict_from_emr(document.document_id)
                                if prediction_result.get('success'):
                                    confidence = prediction_result.get('confidence', 0)
                                    prediction = prediction_result.get('prediction', 'Unknown')
                                    messages.info(request, f"Prediction generated: {prediction} (Confidence: {confidence}%)")
                                else:
                                    messages.warning(request, f"Document uploaded but prediction failed: {prediction_result.get('error', 'Unknown error')}")
                            else:
                                messages.warning(request, f"Document uploaded but processing failed: {processing_result.get('error', 'Unknown error')}")
                        except Exception as e:
                            messages.warning(request, f"Document uploaded but processing error: {str(e)}")
                    else:
                        messages.success(request, "Document uploaded successfully!")
                    
                    try:
                        log_event(
                            action="EMR_UPLOAD",
                            role=request.user.role,
                            details={
                                'document_type': document_type,
                                'patient_id': str(patient.id),
                                'auto_extract': auto_extract,
                                'success': True
                            }
                        )
                    except:
                        pass
                    
                    return redirect('view_emr_document', document_id=document.document_id)
                else:
                    error_msg = upload_result.get('error', 'Unknown upload error')
                    messages.error(request, f"Upload failed: {error_msg}")
                    
            except Exception as e:
                messages.error(request, f"Error uploading document: {str(e)}")
                print(f"Upload error: {traceback.format_exc()}")
        
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    
    else:
        form = EMRFileUploadForm()
    
    # Get patients for doctor
    patients = []
    if request.user.is_doctor():
        patients = User.objects.filter(role='patient', is_active=True, is_superuser=False).order_by('full_name')
    
    context = {
        'form': form,
        'patients': patients,
        'page_title': 'Upload Medical Document',
        'EMR_SERVICE_AVAILABLE': EMR_SERVICE_AVAILABLE
    }
    return render(request, 'core/upload_emr.html', context)


@login_required
def view_emr_document(request, document_id):
    """View EMR document details"""
    try:
        document = get_object_or_404(MedicalDocument, document_id=document_id)
        
        # Check permissions
        if not (request.user == document.patient or 
                request.user == document.doctor or 
                request.user == document.created_by or
                request.user.is_admin):
            messages.error(request, "You don't have permission to view this document.")
            return redirect('emr_dashboard')
        
        # Log data access (Signed)
        audit_service.log_action(
            user=request.user,
            action='VIEW',
            resource_type='MedicalDocument',
            resource_id=document.document_id,
            request=request
        )
        
        # Get extraction logs
        extraction_logs = EMRExtractionLog.objects.filter(document=document).order_by('-created_at')
        
        # Get predictions with confidence scores
        predictions = EMRPrediction.objects.filter(document=document).order_by('-created_at')
        
        # Prepare prediction data with confidence percentages
        prediction_data = []
        for pred in predictions:
            # Extract confidence score
            confidence_score = None
            if pred.confidence_scores:
                try:
                    if isinstance(pred.confidence_scores, dict):
                        # Get the first confidence score
                        for key, value in pred.confidence_scores.items():
                            confidence_score = value
                            break
                    elif isinstance(pred.confidence_scores, (int, float)):
                        confidence_score = float(pred.confidence_scores)
                except:
                    confidence_score = None
            
            # Format confidence as percentage
            confidence_percentage = None
            if confidence_score is not None:
                try:
                    if isinstance(confidence_score, (int, float)):
                        # If confidence is already a percentage (0-100), use as is
                        if 0 <= confidence_score <= 100:
                            confidence_percentage = round(float(confidence_score), 2)
                        # If confidence is between 0-1, convert to percentage
                        elif 0 <= confidence_score <= 1:
                            confidence_percentage = round(float(confidence_score) * 100, 2)
                        else:
                            confidence_percentage = round(float(confidence_score), 2)
                except:
                    confidence_percentage = None
            
            prediction_data.append({
                'prediction': pred,
                'confidence_score': confidence_score,
                'confidence_percentage': confidence_percentage,
                'confidence_display': f"{confidence_percentage}%" if confidence_percentage is not None else "N/A",
                'has_confidence': confidence_percentage is not None
            })
        
        # Prepare context for extracted data
        extracted_data = {}
        if document.extracted_data and document.extracted_data.strip():
            try:
                # Decode base64 string back to bytes
                if isinstance(document.extracted_data, str) and document.extracted_data.strip():
                    encrypted_bytes = base64.b64decode(document.extracted_data)
                    extracted_data = decrypt_data(encrypted_bytes)
            except Exception as e:
                print(f"Error decrypting extracted data: {e}")
                extracted_data = {'error': 'Could not decrypt data'}
        
        context = {
            'document': document,
            'extraction_logs': extraction_logs,
            'predictions': prediction_data,
            'extracted_data': extracted_data,
            'page_title': f'Document: {document.get_document_type_display()}',
            'EMR_SERVICE_AVAILABLE': EMR_SERVICE_AVAILABLE
        }
        
        return render(request, 'core/view_emr_document.html', context)
    except Exception as e:
        messages.error(request, f"Error viewing document: {str(e)}")
        return redirect('emr_dashboard')


@login_required
@require_POST
@csrf_exempt
def process_emr_document(request, document_id):
    """Process EMR document (extract text and entities)"""
    try:
        document = get_object_or_404(MedicalDocument, document_id=document_id)
        
        # Check permissions
        if not (request.user.is_doctor() or request.user.is_admin() or request.user == document.patient):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        if not EMR_SERVICE_AVAILABLE:
            return JsonResponse({'success': False, 'error': 'EMR service not available'})
        
        emr_processor = EMRProcessor()
        result = emr_processor.process_document(document_id, auto_extract=True)
        
        if result.get('success'):
            try:
                log_event(
                    action="EMR_PROCESS",
                    role=request.user.role,
                    details={
                        'document_id': str(document_id),
                        'text_length': result.get('text_length', 0),
                        'success': True
                    }
                )
            except:
                pass
            
            # Create a clean JSON-serializable response
            clean_result = {
                'success': True,
                'document_id': str(result.get('document_id', '')),
                'text_length': int(result.get('text_length', 0)),
                'processing_time': float(result.get('processing_time', 0))
            }
            
            # Safely handle entities_found
            entities_found = result.get('entities_found', {})
            if entities_found:
                # Ensure all entities are JSON serializable
                serializable_entities = {}
                for key, value in entities_found.items():
                    if isinstance(value, (list, dict, str, int, float, bool, type(None))):
                        serializable_entities[key] = value
                    else:
                        # Convert non-serializable objects to string
                        serializable_entities[key] = str(value)
                clean_result['entities_found'] = serializable_entities
            
            return JsonResponse(clean_result)
        else:
            # Handle error response - ensure error is a string
            error_msg = result.get('error', 'Unknown error')
            if not isinstance(error_msg, str):
                error_msg = str(error_msg)
            
            error_data = {
                'success': False, 
                'error': error_msg
            }
            
            # Only include traceback if it's a string
            traceback_data = result.get('traceback', '')
            if isinstance(traceback_data, str):
                error_data['traceback'] = traceback_data
            
            return JsonResponse(error_data)
    
    except Exception as e:
        import traceback as tb
        return JsonResponse({
            'success': False, 
            'error': str(e),
            'traceback': str(tb.format_exc())
        })


@login_required
@require_POST
@csrf_exempt
def generate_emr_prediction(request, document_id):
    """Generate prediction from EMR data"""
    try:
        document = get_object_or_404(MedicalDocument, document_id=document_id)
        
        # Check permissions
        if not (request.user.is_doctor() or request.user == document.patient or request.user.is_admin()):
            return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        # Log AI Prediction access (Signed)
        audit_service.log_action(
            user=request.user,
            action='PREDICT',
            resource_type='MedicalDocument',
            resource_id=document.document_id,
            request=request
        )
        
        if not EMR_SERVICE_AVAILABLE:
            return JsonResponse({'success': False, 'error': 'EMR service not available'})
        
        emr_processor = EMRProcessor()
        result = emr_processor.predict_from_emr(document_id)
        
        if result.get('success'):
            try:
                log_event(
                    action="EMR_PREDICTION",
                    role=request.user.role,
                    details={
                        'document_id': str(document_id),
                        'prediction': result.get('prediction', ''),
                        'confidence': result.get('confidence', 0),
                        'success': True
                    }
                )
            except:
                pass
            
            # Ensure confidence is properly formatted
            confidence = result.get('confidence', 0)
            if isinstance(confidence, (int, float)):
                confidence_percentage = round(float(confidence), 2)
            else:
                confidence_percentage = 0
            
            # Create clean response
            clean_result = {
                'success': True,
                'prediction_id': str(result.get('prediction_id', '')),
                'prediction': str(result.get('prediction', 'Unknown')),
                'confidence': confidence_percentage,
                'confidence_display': f"{confidence_percentage}%",
                'risk_level': str(result.get('risk_level', 'Unknown')),
                'symptoms': list(result.get('symptoms', [])),
                'explanation': str(result.get('explanation', '')),
                'model_status': str(result.get('model_status', 'primary'))
            }
            
            return JsonResponse(clean_result)
        else:
            # Handle error response
            error_msg = result.get('error', 'Unknown error')
            if not isinstance(error_msg, str):
                error_msg = str(error_msg)
            
            return JsonResponse({
                'success': False, 
                'error': error_msg
            })
    
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': str(e),
            'traceback': traceback.format_exc()
        })


@login_required
def download_emr_document(request, document_id):
    """Download encrypted EMR document"""
    try:
        document = get_object_or_404(MedicalDocument, document_id=document_id)
        
        # Check permissions
        if not (request.user == document.patient or 
                request.user == document.doctor or 
                request.user == document.created_by or
                request.user.is_admin()):
            messages.error(request, "You don't have permission to download this document.")
            return redirect('emr_dashboard')
        
        # Log Document Download (Signed)
        audit_service.log_action(
            user=request.user,
            action='DOWNLOAD',
            resource_type='MedicalDocument',
            resource_id=document.document_id,
            request=request
        )
        
        emr_processor = EMRProcessor()
        file_path = os.path.join(emr_processor.upload_dir, document.encrypted_filename)
        
        if os.path.exists(file_path):
            try:
                log_event(
                    action="EMR_DOWNLOAD",
                    role=request.user.role,
                    details={
                        'document_id': str(document_id),
                        'filename': document.original_filename
                    }
                )
            except:
                pass
            
            response = FileResponse(open(file_path, 'rb'))
            response['Content-Disposition'] = f'attachment; filename="{document.original_filename}.enc"'
            return response
        else:
            messages.error(request, "File not found.")
            return redirect('view_emr_document', document_id=document_id)
    
    except Exception as e:
        messages.error(request, f"Error downloading file: {str(e)}")
        return redirect('view_emr_document', document_id=document_id)


@login_required
@require_http_methods(["GET", "POST"])
def delete_emr_document(request, document_id):
    """Delete EMR document"""
    try:
        document = get_object_or_404(MedicalDocument, document_id=document_id)
        
        # Check permissions
        if not (request.user == document.patient or 
                (request.user.is_doctor() and request.user == document.created_by) or
                request.user.is_admin()):
            messages.error(request, "You don't have permission to delete this document.")
            return redirect('emr_dashboard')
        
        if request.method == 'POST':
            # Delete file from storage
            emr_processor = EMRProcessor()
            file_path = os.path.join(emr_processor.upload_dir, document.encrypted_filename)
            
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error deleting file: {e}")
            
            # Delete database record
            document_title = document.get_document_type_display()
            document.delete()
            
            try:
                log_event(
                    action="EMR_DELETE",
                    role=request.user.role,
                    details={
                        'document_id': str(document_id),
                        'document_type': document_title
                    }
                )
            except:
                pass
            
            messages.success(request, f"Document '{document_title}' deleted successfully.")
            return redirect('emr_dashboard')
        
        context = {
            'document': document,
            'page_title': 'Delete Document'
        }
        return render(request, 'core/delete_emr_document.html', context)
    
    except Exception as e:
        messages.error(request, f"Error deleting document: {str(e)}")
        return redirect('emr_dashboard')


@login_required
def emr_analytics(request):
    """EMR Analytics Dashboard"""
    if not (request.user.is_doctor() or request.user.is_admin()):
        messages.error(request, "You don't have permission to view analytics.")
        return redirect('dashboard')
    
    try:
        # Get statistics
        total_docs = MedicalDocument.objects.count()
        processed_docs = MedicalDocument.objects.filter(is_processed=True).count()
        pending_docs = MedicalDocument.objects.filter(processing_status='pending').count()
        
        # Document type distribution
        doc_types = MedicalDocument.objects.values('document_type').annotate(count=models.Count('id'))
        
        # Recent predictions
        recent_predictions_query = EMRPrediction.objects.select_related('patient', 'document').order_by('-created_at')[:10]
        
        # Process predictions for display
        recent_predictions = []
        for pred in recent_predictions_query:
            # Extract confidence
            confidence = None
            if pred.confidence_scores:
                try:
                    if isinstance(pred.confidence_scores, dict):
                        for key, value in pred.confidence_scores.items():
                            confidence = value
                            break
                    elif isinstance(pred.confidence_scores, (int, float)):
                        confidence = float(pred.confidence_scores)
                except:
                    confidence = None
            
            # Format confidence
            confidence_display = "N/A"
            if confidence is not None:
                if 0 <= confidence <= 1:
                    confidence_display = f"{round(confidence * 100, 1)}%"
                elif 0 <= confidence <= 100:
                    confidence_display = f"{round(confidence, 1)}%"
                else:
                    confidence_display = f"{round(confidence, 1)}"
            
            recent_predictions.append({
                'prediction': pred,
                'confidence': confidence,
                'confidence_display': confidence_display
            })
        
        # Risk level distribution
        risk_levels = EMRPrediction.objects.values('risk_level').annotate(count=models.Count('id'))
        
        # Average confidence by risk level
        avg_confidence_by_risk = []
        risk_categories = ['Low', 'Medium', 'High', 'Critical']
        
        for risk in risk_categories:
            preds = EMRPrediction.objects.filter(risk_level=risk)
            if preds.exists():
                total_conf = 0
                count = 0
                for pred in preds:
                    if pred.confidence_scores:
                        try:
                            if isinstance(pred.confidence_scores, dict):
                                for key, value in pred.confidence_scores.items():
                                    if isinstance(value, (int, float)):
                                        total_conf += float(value)
                                        count += 1
                                        break
                            elif isinstance(pred.confidence_scores, (int, float)):
                                total_conf += float(pred.confidence_scores)
                                count += 1
                        except:
                            pass
                
                if count > 0:
                    avg_conf = total_conf / count
                    # Convert to percentage if needed
                    if avg_conf <= 1:
                        avg_conf = avg_conf * 100
                    
                    avg_confidence_by_risk.append({
                        'risk_level': risk,
                        'avg_confidence': round(avg_conf, 2),
                        'count': count
                    })
        
        context = {
            'total_docs': total_docs,
            'processed_docs': processed_docs,
            'pending_docs': pending_docs,
            'doc_types': list(doc_types),
            'recent_predictions': recent_predictions,
            'risk_levels': list(risk_levels),
            'avg_confidence_by_risk': avg_confidence_by_risk,
            'page_title': 'EMR Analytics',
            'EMR_SERVICE_AVAILABLE': EMR_SERVICE_AVAILABLE
        }
        
        return render(request, 'core/emr_analytics.html', context)
    except Exception as e:
        messages.error(request, f"Error loading analytics: {str(e)}")
        return redirect('emr_dashboard')


@login_required
def ml_model_status(request):
    """Check ML model status"""
    try:
        from backend.services.ml_service import get_model_status
        
        status = get_model_status()
        
        context = {
            'page_title': 'ML Model Status',
            'status': status,
            'EMR_SERVICE_AVAILABLE': EMR_SERVICE_AVAILABLE
        }
        
        return render(request, 'core/ml_model_status.html', context)
    except Exception as e:
        messages.error(request, f"Error checking model status: {str(e)}")
        return redirect('emr_dashboard')


@login_required
@require_POST
@csrf_exempt
def test_prediction(request):
    """Test prediction endpoint"""
    try:
        import json
        data = json.loads(request.body)
        symptoms = data.get('symptoms', [])
        
        from backend.services.ml_service import predict
        
        ml_input = {symptom: 1 for symptom in symptoms if symptom}
        result = predict(ml_input)
        
        return JsonResponse({
            'success': True,
            'prediction': result.get('prediction', 'Test'),
            'confidence': result.get('confidence', 0),
            'model_status': result.get('model_status', 'unknown')
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })