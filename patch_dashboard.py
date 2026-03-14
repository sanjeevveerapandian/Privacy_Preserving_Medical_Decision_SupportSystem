import re
import os

path = 'templates/core/emr_dashboard.html'
with open(path, 'r') as f:
    content = f.read()

pattern = re.compile(r'<td>\s*{%\s*if doc\.document_type == \'mri\' or doc\.document_type == \'xray\'\s*%}.*?{% else %}\s*<span class="badge badge-secondary">Pending</span>\s*{%\s*endif\s*%}\s*</td>', re.DOTALL)

replacement = """<td>
                                        {% if doc.document_type == 'xray' %}
                                        <a href="#" class="text-decoration-none" data-bs-toggle="modal"
                                            data-bs-target="#aiResultModal"
                                            data-frac-pred="{{ doc.extracted_data.fracture.prediction|default:''|escape }}"
                                            data-frac-conf="{{ doc.extracted_data.fracture.confidence|default:0|floatformat:2 }}"
                                            data-pneu-pred="{{ doc.extracted_data.pneumonia.prediction|default:''|escape }}"
                                            data-pneu-conf="{{ doc.extracted_data.pneumonia.confidence|default:0|floatformat:2 }}"
                                            data-prediction="{{ doc.ai_prediction|default:''|escape }}"
                                            data-confidence="{% if doc.ai_confidence %}{{ doc.ai_confidence|floatformat:2 }}{% endif %}"
                                            data-summary="{{ doc.ai_summary|default:''|escape }}"
                                            data-heatmap="{% if doc.ai_heatmap %}{{ doc.ai_heatmap.url }}{% endif %}"
                                            data-type="{{ doc.document_type }}" onclick="showDualAIModal(this)">
                                            
                                            {% if doc.ai_status == 'Completed' %}
                                                <div class="d-flex flex-column gap-1">
                                                    {% with fp=doc.extracted_data.fracture.prediction|lower %}
                                                    <span class="badge {% if 'no fracture' in fp %}bg-success{% elif 'fracture' in fp %}bg-danger{% else %}bg-secondary{% endif %}">
                                                        <i class="fas fa-bone me-1"></i>Bone: {{ doc.extracted_data.fracture.prediction|title|default:'N/A' }}
                                                    </span>
                                                    {% endwith %}
                                                    {% with pp=doc.extracted_data.pneumonia.prediction|lower %}
                                                    <span class="badge {% if 'normal' in pp %}bg-success{% elif 'pneumonia' in pp %}bg-warning text-dark{% else %}bg-secondary{% endif %}">
                                                        <i class="fas fa-lungs me-1"></i>Chest: {{ doc.extracted_data.pneumonia.prediction|title|default:'N/A' }}
                                                    </span>
                                                    {% endwith %}
                                                </div>
                                            {% elif doc.ai_status == 'Processing' %}
                                                <span class="badge bg-warning text-dark"><i class="fas fa-spinner fa-spin me-1"></i>Analyzing</span>
                                            {% elif doc.ai_status == 'Failed' %}
                                                <span class="badge bg-danger"><i class="fas fa-times-circle me-1"></i>Failed</span>
                                            {% else %}
                                                <span class="badge bg-info"><i class="fas fa-clock me-1"></i>Queued</span>
                                            {% endif %}
                                        </a>

                                        {% elif doc.document_type == 'mri' %}
                                        <a href="#" class="text-decoration-none" data-bs-toggle="modal"
                                            data-bs-target="#aiResultModal"
                                            data-prediction="{{ doc.ai_prediction|default:''|escape }}"
                                            data-confidence="{% if doc.ai_confidence %}{{ doc.ai_confidence|floatformat:2 }}{% endif %}"
                                            data-summary="{{ doc.ai_summary|default:''|escape }}"
                                            data-heatmap="{% if doc.ai_heatmap %}{{ doc.ai_heatmap.url }}{% endif %}"
                                            data-type="{{ doc.document_type }}" onclick="showAIModal(this)">
                                            {% if doc.ai_status == 'Completed' %}
                                            {% with p=doc.ai_prediction|lower %}
                                            <span class="badge {% if 'notumor' in p %}bg-success{% elif 'meningioma' in p or 'pituitary' in p %}bg-warning text-dark{% else %}bg-danger{% endif %}">
                                                <i class="fas fa-check-circle me-1"></i>{{ doc.ai_prediction|title }}
                                            </span>
                                            {% endwith %}
                                            {% elif doc.ai_status == 'Processing' %}
                                            <span class="badge bg-warning text-dark"><i class="fas fa-spinner fa-spin me-1"></i>Analyzing</span>
                                            {% elif doc.ai_status == 'Failed' %}
                                            <span class="badge bg-danger"><i class="fas fa-times-circle me-1"></i>Failed</span>
                                            {% else %}
                                            <span class="badge bg-info"><i class="fas fa-clock me-1"></i>Queued</span>
                                            {% endif %}
                                        </a>
                                        {% else %}
                                        <span class="badge badge-secondary">Pending</span>
                                        {% endif %}
                                    </td>"""

if pattern.search(content):
    new_content = pattern.sub(replacement, content)
    with open(path, 'w') as f:
        f.write(new_content)
    print("Dashboard patched successfully")
else:
    print("Pattern not found in dashboard")

