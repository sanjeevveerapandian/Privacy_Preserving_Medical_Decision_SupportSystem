import re
import os

path = 'templates/core/emr_dashboard.html'
with open(path, 'r') as f:
    content = f.read()

pattern = re.compile(r'{%\s*if doc\.document_type == \'xray\'\s*%}.*?{%\s*elif doc\.document_type == \'mri\'\s*%}(.*?){%\s*else\s*%}', re.DOTALL)

def replacer(match):
    mri_block = match.group(1)
    # The MRI block has the generic logic for `doc.ai_prediction`. We can just make it apply to both mri and xray.
    # We replace `elif doc.document_type == 'mri'` with `if doc.document_type == 'mri' or doc.document_type == 'xray'`
    return "{% if doc.document_type == 'mri' or doc.document_type == 'xray' %}" + mri_block + "{% else %}"

if pattern.search(content):
    new_content = pattern.sub(replacer, content)
    with open(path, 'w') as f:
        f.write(new_content)
    print("Dashboard reverted successfully")
else:
    print("Pattern not found in dashboard")

