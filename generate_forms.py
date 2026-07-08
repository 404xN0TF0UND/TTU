import os
import re

TEMPLATES_DIR = 'templates'
OUTPUT_DIR = os.path.join(TEMPLATES_DIR, 'generated_forms')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Regex patterns for parsing
FIELD_LINE = re.compile(r'Gui, Add, (Edit|DropDownList|Radio),[^v]*v([a-zA-Z0-9_]+),\s*(.*)')
TEXT_LINE = re.compile(r'Gui, Add, Text, [^,]*, (.*)')
DROPDOWN_OPTIONS = re.compile(r'\|(.*?)\s*(?=\||$)')

for filename in os.listdir(TEMPLATES_DIR):
    if not filename.endswith('.ahk'):
        continue
    fields = []
    labels = {}
    with open(os.path.join(TEMPLATES_DIR, filename), encoding='utf-8') as f:
        lines = f.readlines()
    last_label = None
    for line in lines:
        text_match = TEXT_LINE.search(line)
        if text_match:
            last_label = text_match.group(1).strip()
        field_match = FIELD_LINE.search(line)
        if field_match:
            field_type, var_name, extra = field_match.groups()
            label = last_label or var_name
            field = {'type': field_type, 'name': var_name, 'label': label}
            if field_type == 'DropDownList':
                # Extract options
                options = [opt for opt in extra.split('|') if opt]
                field['options'] = options
            fields.append(field)
            last_label = None
    # Generate Jinja form
    form_name = filename.replace('.ahk', '.html')
    with open(os.path.join(OUTPUT_DIR, form_name), 'w', encoding='utf-8') as out:
        out.write('{% extends "base.html" %}\n')
        out.write('{% block content %}\n')
        out.write(f'<h2>{filename.replace("_", " ").replace(".ahk", "")}</h2>\n')
        out.write('<form method="post">\n')
        for field in fields:
            out.write(f'  <div class="mb-3">\n')
            out.write(f'    <label class="form-label">{field["label"]}</label>\n')
            if field['type'] == 'Edit':
                # Use textarea for long fields
                if 'solution' in field['name'].lower() or 'addinfo' in field['name'].lower():
                    out.write(f'    <textarea class="form-control" name="{field["name"]}" rows="4"></textarea>\n')
                else:
                    out.write(f'    <input class="form-control" type="text" name="{field["name"]}">\n')
            elif field['type'] == 'DropDownList':
                out.write(f'    <select class="form-select" name="{field["name"]}">\n')
                for opt in field.get('options', []):
                    out.write(f'      <option value="{opt}">{opt}</option>\n')
                out.write('    </select>\n')
            elif field['type'] == 'Radio':
                # Assume two options: Yes/No or On/Off
                for opt in ['Yes', 'No']:
                    out.write(f'    <input type="radio" name="{field["name"]}" value="{opt}"> {opt}\n')
            out.write('  </div>\n')
        out.write('  <button type="submit" class="btn btn-primary">Generate Note</button>\n')
        out.write('</form>\n')
        out.write('{% endblock %}\n')
print(f"Generated forms for all .ahk templates in {OUTPUT_DIR}") 