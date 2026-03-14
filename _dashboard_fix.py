with open('templates/core/emr_dashboard.html', 'r') as f:
    content = f.read()

import re
# The broken block was around line 147. 
# The replace tool removed everything from "badge badge-danger">Failed</span>"
# to "Extracted".
# Let's just restore the whole table row logic for MRI.
