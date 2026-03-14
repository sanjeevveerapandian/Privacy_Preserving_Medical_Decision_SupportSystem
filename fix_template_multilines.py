import os
file_path = '/Users/pyt/Downloads/1CP25-754 2/templates/doctor/appointment_detail.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: patient full name mapping (lines 31-32)
target1 = """                                    <div class="fw-bold fs-5">{{
                                        appointment.patient.get_full_name|default:appointment.patient.username }}</div>"""
repl1 = '                                    <div class="fw-bold fs-5">{{ appointment.patient.get_full_name|default:appointment.patient.username }}</div>'

# Fix 2: meeting link (lines 152-153)
target2 = """                                <a href="{{ appointment.meeting_link }}" target="_blank" class="text-break">{{
                                    appointment.meeting_link }}</a>"""
repl2 = '                                <a href="{{ appointment.meeting_link }}" target="_blank" class="text-break">{{ appointment.meeting_link }}</a>'

content = content.replace(target1, repl1)
content = content.replace(target2, repl2)

# Fix 3: replace encrypted_diagnosis display if it's not fixed
target3 = """                                    <div class="small text-muted">
                                        {{ record.encrypted_diagnosis|default:"No diagnosis"|truncatechars:40 }}
                                    </div>"""
repl3 = """                                    <div class="small text-muted">
                                        {{ record.get_diagnosis_summary|truncatechars:40 }}
                                    </div>"""
content = content.replace(target3, repl3)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Template fixed.")
