import re

file_path = '/Users/pyt/Downloads/1CP25-754 2/templates/doctor/appointment_detail.html'

with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Let's see how many times get_full_name appears
print("Occurrences of get_full_name:")
for i, line in enumerate(text.splitlines()):
    if 'get_full_name' in line:
        print(f"Line {i+1}: {repr(line)}")
        
