from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import MLModel, Notification
import os

class Command(BaseCommand):
    help = 'Setup initial system data'
    
    def handle(self, *args, **kwargs):
        User = get_user_model()
        
        # Create admin user if not exists
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@medical.com',
                password='admin123',
                role='admin',
                status='approved',
                full_name='System Administrator'
            )
            self.stdout.write(self.style.SUCCESS('Admin user created'))
        
        # Create sample ML model entry
        if not MLModel.objects.exists():
            MLModel.objects.create(
                name='Disease Predictor',
                version='1.0',
                model_file='ml_models/disease_predictor.joblib',
                features=['itching', 'fever', 'cough'],  # Sample
                accuracy=0.85,
                is_active=True
            )
            self.stdout.write(self.style.SUCCESS('ML model entry created'))
        
        # Create media directories
        os.makedirs('media/profile_pics', exist_ok=True)
        os.makedirs('media/ml_models', exist_ok=True)
        
        self.stdout.write(self.style.SUCCESS('System setup completed'))