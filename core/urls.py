
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

    # core/urls.py - Alternative simplified version
from django.urls import path
from django.contrib.auth import views as auth_views

# Use explicit imports to avoid circular dependencies
from .views import login_views
from .views import admin_views
from .views import doctor_views
from .views import researcher_views
from .views import patient_views
from .views import common_views
from .views import emr_doctor_views
from .views import emr_certificate_views

urlpatterns = [
    # Authentication
    path('', login_views.login_view, name='login'),
    path('logout/', login_views.logout_view, name='logout'),
    
    # API Authentication
    path('api/login/', login_views.api_login, name='api_login'),
    path('api/register/<str:role>/', login_views.api_register, name='api_register'),
    path('api/check-username/', login_views.check_username, name='check_username'),
    path('api/check-email/', login_views.check_email, name='check_email'),
    
    # Registration views (keeping existing)
    path('register/doctor/', login_views.register_doctor_view, name='register_doctor'),
    path('register/researcher/', login_views.register_researcher_view, name='register_researcher'),
    path('register/patient/', login_views.register_patient_view, name='register_patient'),
    # Add this to urls.py
    path('pending-approval/', login_views.pending_approval, name='pending_approval'),
    
    # Admin API endpoints (add these)
    path('api/admin/pending-count/', login_views.admin_pending_count, name='admin_pending_count'),    
    
    # Dashboard redirects
    path('dashboard/', login_views.dashboard_redirect, name='dashboard_redirect'),
    





    
    # Admin URLs
    path('admin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('admin/user-approval/', admin_views.admin_user_approval, name='admin_user_approval'),
    path('admin/user-management/', admin_views.admin_user_management, name='admin_user_management'),
    path('admin/audit-logs/', admin_views.admin_audit_logs, name='admin_audit_logs'),
    path('admin/user/<int:user_id>/', admin_views.admin_user_detail, name='admin_user_detail'),
    path('admin/system-monitoring/', admin_views.admin_system_monitoring, name='admin_system_monitoring'),

    path('api/users/<int:user_id>/approve/', admin_views.approve_user_api, name='approve_user_api'),
    path('api/users/<int:user_id>/reject/', admin_views.reject_user_api, name='reject_user_api'),
    path('api/users/approve-all/', admin_views.approve_all_users_api, name='approve_all_users_api'),
    

    
    
    # Doctor URLs
    path('doctor/dashboard/', doctor_views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/chat/', doctor_views.doctor_chat, name='doctor_chat'),
    path('doctor/chat/send/', doctor_views.doctor_chat_send, name='doctor_chat_send'),
    path('doctor/patients/', doctor_views.doctor_patients, name='doctor_patients'),
    path('doctor/patients/<int:patient_id>/', doctor_views.doctor_patient_detail, name='doctor_patient_detail'),
    path('doctor/patients/<int:patient_id>/analyze/', doctor_views.doctor_patient_analysis, name='doctor_patient_analysis'),
    path('doctor/patients/<int:patient_id>/add-record/', doctor_views.doctor_add_medical_record, name='doctor_add_medical_record'),
    path('doctor/patient-submissions/', doctor_views.doctor_patient_submissions, name='doctor_patient_submissions'),
    path('doctor/accept-appointment/', doctor_views.doctor_accept_appointment, name='doctor_accept_appointment'),

    
    path('doctor/ml-analysis/', doctor_views.doctor_ml_analysis, name='doctor_ml_analysis'),
    path('doctor/symptom-analyzer/', doctor_views.doctor_symptom_analyzer, name='doctor_symptom_analyzer'),


    path('doctor/medical-history/', doctor_views.doctor_medical_history, name='doctor_medical_history'),
    path('doctor/profile/', doctor_views.doctor_profile, name='doctor_profile'),
    path('doctor/medical-tools/', doctor_views.doctor_medical_tools, name='doctor_medical_tools'),

    path('doctor/chat/change-model/', doctor_views.doctor_change_model, name='doctor_change_model'),
    path('doctor/chat/test-ollama/', doctor_views.test_ollama_connection, name='doctor_test_ollama'),

    path('doctor/appointments/', doctor_views.doctor_appointments, name='doctor_appointments'),
    path('doctor/appointments/<uuid:appointment_id>/', doctor_views.doctor_appointment_detail, name='doctor_appointment_detail'),
    path('doctor/appointments/<uuid:appointment_id>/update-status/', doctor_views.doctor_update_appointment_status, name='doctor_update_appointment_status'),
    path('doctor/appointments/<uuid:appointment_id>/update-time/', doctor_views.doctor_update_appointment_time, name='doctor_update_appointment_time'),
    path('doctor/schedule/', doctor_views.doctor_schedule, name='doctor_schedule'),
    path('doctor/availability/', doctor_views.doctor_availability, name='doctor_availability'),
    path('doctor/appointments/<uuid:appointment_id>/create-meeting/', doctor_views.doctor_create_video_meeting, name='doctor_create_video_meeting'),
    path('doctor/appointments/<uuid:appointment_id>/process-summary/', doctor_views.doctor_process_meeting_summary, name='doctor_process_meeting_summary'),
    path('doctor/appointments/<uuid:appointment_id>/view-summary/', doctor_views.doctor_view_meeting_details, name='doctor_view_meeting_summary'),

    path('chat/new-session/', doctor_views.doctor_new_chat_session, name='doctor_new_chat_session'),  # NEW
    path('chat/session/<int:session_id>/delete/', doctor_views.doctor_delete_chat_session, name='doctor_delete_chat_session'),





    path('doctor/emr/', emr_doctor_views.emr_dashboard, name='emr_dashboard'),
    path('doctor/emr/upload/', emr_doctor_views.upload_emr, name='upload_emr'),
    path('doctor/emr/document/<uuid:document_id>/', emr_doctor_views.view_emr_document, name='view_emr_document'),
    path('doctor/emr/document/<uuid:document_id>/process/', emr_doctor_views.process_emr_document, name='process_emr_document'),
    path('doctor/emr/document/<uuid:document_id>/predict/', emr_doctor_views.generate_emr_prediction, name='generate_emr_prediction'),
    path('doctor/emr/document/<uuid:document_id>/download/', emr_doctor_views.download_emr_document, name='download_emr_document'),
    path('doctor/emr/document/<uuid:document_id>/delete/', emr_doctor_views.delete_emr_document, name='delete_emr_document'),
    path('doctor/emr/analytics/', emr_doctor_views.emr_analytics, name='emr_analytics'),

    # Medical Certificate URLs
    path('certificates/issue/<int:patient_id>/', emr_certificate_views.issue_certificate, name='issue_certificate'),
    path('certificates/view/<uuid:certificate_id>/', emr_certificate_views.view_certificate, name='view_certificate'),
    path('certificates/list/', emr_certificate_views.list_certificates, name='list_certificates'),
























    # Researcher URLs
    path('researcher/dashboard/', researcher_views.researcher_dashboard, name='researcher_dashboard'),
    path('researcher/chat/', researcher_views.researcher_chat, name='researcher_chat'),
    path('researcher/chat/send/', researcher_views.researcher_chat_send, name='researcher_chat_send'),
    path('researcher/chat/change-model/', researcher_views.researcher_change_model, name='researcher_change_model'),
    path('researcher/chat/test-connection/', researcher_views.test_researcher_ollama_connection, name='test_researcher_ollama_connection'),
    path('researcher/chat/new-session/', researcher_views.researcher_new_chat_session, name='researcher_new_chat_session'),
    path('researcher/chat/delete-session/<int:session_id>/', researcher_views.researcher_delete_chat_session, name='researcher_delete_chat_session'),
    

    
    path('researcher/profile/', researcher_views.researcher_profile, name='researcher_profile'),




    # Patient URLs
    path('patient/dashboard/', patient_views.patient_dashboard, name='patient_dashboard'),
    
    # Patient Chat URLs
    path('patient/chat/', patient_views.patient_chat, name='patient_chat'),
    path('patient/chat/send/', patient_views.patient_chat_send, name='patient_chat_send'),
    path('patient/chat/change-model/', patient_views.patient_change_model, name='patient_change_model'),
    path('patient/chat/test-connection/', patient_views.test_patient_ollama_connection, name='test_patient_ollama_connection'),
    path('patient/chat/new-session/', patient_views.patient_new_chat_session, name='patient_new_chat_session'),
    path('patient/chat/delete-session/<int:session_id>/', patient_views.patient_delete_chat_session, name='patient_delete_chat_session'),
    
    # Patient Notifications URLs
    path('patient/notifications/', patient_views.patient_notifications, name='patient_notifications'),
    path('patient/notifications/<int:notification_id>/read/', patient_views.patient_mark_notification_read, name='patient_mark_notification_read'),
    path('patient/notifications/mark-all-read/', patient_views.patient_mark_all_read, name='patient_mark_all_read'),
    path('patient/notifications/<int:notification_id>/delete/', patient_views.patient_delete_notification, name='patient_delete_notification'),
    path('patient/notifications/delete-all-read/', patient_views.patient_delete_all_read, name='patient_delete_all_read'),
    path('patient/notifications/clear-all/', patient_views.patient_clear_all_notifications, name='patient_clear_all_notifications'),
    
    # Patient Medical URLs
    path('patient/medical-history/', patient_views.patient_medical_history, name='patient_medical_history'),
    path('patient/symptom-check/', patient_views.patient_symptom_check, name='patient_symptom_check'),
    
    # Patient Appointment URLs
    path('patient/appointments/', patient_views.patient_appointments, name='patient_appointments'),
    path('patient/appointments/<uuid:appointment_id>/', patient_views.patient_appointment_detail, name='patient_appointment_detail'),
    path('patient/book-appointment/', patient_views.patient_book_appointment, name='patient_book_appointment'),
    path('patient/book-appointment/<int:doctor_id>/', patient_views.patient_book_appointment, name='patient_book_appointment_with_doctor'),
    path('patient/appointments/<uuid:appointment_id>/cancel/', patient_views.patient_cancel_appointment, name='patient_cancel_appointment'),
    path('patient/appointments/<uuid:appointment_id>/reschedule/', patient_views.patient_reschedule_appointment, name='patient_reschedule_appointment'),
    
    # Patient Profile & Settings URLs
    path('patient/profile/', patient_views.patient_profile, name='patient_profile'),
    path('patient/doctors/', patient_views.patient_doctors, name='patient_doctors'),
    path('patient/settings/', patient_views.patient_settings, name='patient_settings'),
    path('patient/settings/update-notifications/', patient_views.patient_update_notifications, name='patient_update_notifications'),




    
    # Common URLs
    path('notifications/', common_views.notifications_view, name='notifications_view'),
    path('activity-log/', common_views.activity_log, name='activity_log'),
    
    # Password reset
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='auth/password_reset.html'
         ), 
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='auth/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='auth/password_reset_confirm.html'
         ), 
         name='password_reset_confirm'),
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='auth/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
]


# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)