import re
import os

path = 'templates/core/emr_dashboard.html'
with open(path, 'r') as f:
    content = f.read()

pattern = re.compile(r'function showDualAIModal\(element\) \{.*?^\s*function showAIModal\(element\) \{', re.MULTILINE | re.DOTALL)

if pattern.search(content):
    new_content = pattern.sub('function showAIModal(element) {', content)
    with open(path, 'w') as f:
        f.write(new_content)
    print("Modal reverted successfully")
else:
    print("Pattern not found in modal")

