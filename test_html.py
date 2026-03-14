from medical_assistant.wsgi import application
from django.test import Client
import django
django.setup()
from core.models import User, Appointment

user = User.objects.filter(role='doctor').first()
appt = Appointment.objects.get(appointment_id='83268f13-f331-4cca-8330-ea11b89e3746')
c = Client()
c.force_login(user)
resp = c.get(f'/doctor/appointments/{appt.appointment_id}/')
output = resp.content.decode('utf-8')

start = output.find('Secure Video Consultation')
end = output.find('Recent Medical Records')
print("EXACT HTML FROM DJANGO:")
print(output[start:end])
