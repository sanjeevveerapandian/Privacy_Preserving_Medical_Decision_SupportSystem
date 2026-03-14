with open('templates/core/emr_dashboard.html', 'r') as f:
    text = f.read()

import re

# Find the entire table cell starting from btn-group
match = re.search(r'<div class="btn-group" role="group">.*?</td>', text, re.DOTALL)
if match:
    old_cell = match.group(0)
    
    new_cell = '''<div class="btn-group" role="group">
                                            <a href="{% url 'view_emr_document' doc.document_id %}"
                                                class="btn btn-sm btn-outline-primary" title="View Details">
                                                <i class="fas fa-eye"></i>
                                            </a>
                                            <a href="{% url 'download_emr_document' doc.document_id %}"
                                                class="btn btn-sm btn-outline-info" title="Download">
                                                <i class="fas fa-download"></i>
                                            </a>
                                            {% if not doc.is_processed and EMR_SERVICE_AVAILABLE %}
                                            <button class="btn btn-sm btn-outline-warning"
                                                onclick="processSingleDocument('{{ doc.document_id }}')"
                                                title="Process Document">
                                                <i class="fas fa-cogs"></i>
                                            </button>
                                            {% endif %}
                                            {% with u=request.user p=doc.patient c=doc.created_by %}
                                            {% if u == p or request.user.is_superuser or request.user.role == 'admin' or u == c %}
                                            <a href="{% url 'delete_emr_document' doc.document_id %}"
                                                class="btn btn-sm btn-outline-danger" title="Delete"
                                                onclick="return confirm('Are you sure you want to delete this document?');">
                                                <i class="fas fa-trash"></i>
                                            </a>
                                            {% endif %}
                                            {% endwith %}
                                        </div>
                                    </td>'''
    
    new_text = text.replace(old_cell, new_cell)
    with open('templates/core/emr_dashboard.html', 'w') as f:
        f.write(new_text)
    print("Fixed!")
else:
    print("Match not found")
