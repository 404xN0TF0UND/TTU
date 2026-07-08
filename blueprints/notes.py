"""notes blueprint - routes extracted verbatim from app.py (mechanical split, no behavior change)."""
from flask import Blueprint
from core import *  # shared app, helpers, constants, flask names

notes_bp = Blueprint('notes', __name__)


@notes_bp.route('/manage-templates', methods=['GET', 'POST'])
def manage_templates():
    templates = [f for f in os.listdir(GENERATED_FORMS_DIR) if f.endswith('.html')]
    templates_metadata = load_templates_metadata()
    
    if request.method == 'POST':
        if 'duplicate_template' in request.form:
            src = request.form.get('duplicate_template')
            new_name = request.form.get('new_template_name', '').strip()
            if not new_name:
                flash('New template name cannot be empty.')
            elif not new_name.lower().endswith('.html'):
                new_name += '.html'
            dest = os.path.join(GENERATED_FORMS_DIR, new_name)
            src_path = os.path.join(GENERATED_FORMS_DIR, src)
            if not os.path.exists(src_path):
                flash('Source template not found.')
            elif os.path.exists(dest):
                flash('A template with that name already exists.')
            else:
                shutil.copyfile(src_path, dest)
                flash(f'Template duplicated as {new_name}.')
            return redirect(url_for('notes.manage_templates'))
        
        elif 'update_category_template' in request.form:
            template_name = request.form.get('update_category_template')
            category = request.form.get('category', 'Other').strip()
            custom_category = request.form.get('custom_category', '').strip()
            
            # Use custom category if provided, otherwise use selected category
            if category == 'custom' and custom_category:
                category = custom_category
            elif category == 'custom':
                flash('Custom category name cannot be empty.')
                return redirect(url_for('notes.manage_templates'))
            
            if template_name not in templates_metadata:
                templates_metadata[template_name] = {}
            templates_metadata[template_name]['category'] = category
            save_templates_metadata(templates_metadata)
            flash(f'Category updated for {template_name}.')
            return redirect(url_for('notes.manage_templates'))
    
    return render_template('manage_templates.html', templates=templates, template_metadata=templates_metadata)


@notes_bp.route('/manage-templates/category/<template_name>', methods=['POST'])
def update_template_category(template_name):
    category = request.form.get('category', 'Other').strip()
    templates_metadata = load_templates_metadata()
    if template_name not in templates_metadata:
        templates_metadata[template_name] = {}
    templates_metadata[template_name]['category'] = category
    save_templates_metadata(templates_metadata)
    flash(f'Category updated for {template_name}.')
    return redirect(url_for('notes.manage_templates'))


@notes_bp.route('/manage-templates/edit/<template_name>', methods=['GET', 'POST'])
def edit_template(template_name):
    template_path = os.path.join(GENERATED_FORMS_DIR, template_name)
    if not os.path.exists(template_path):
        flash('Template not found.')
        return redirect(url_for('notes.manage_templates'))
    if request.method == 'POST':
        new_content = request.form.get('template_content', '')
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        flash(f'Template {template_name} updated.')
        return redirect(url_for('notes.manage_templates'))
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return render_template('edit_template.html', template_name=template_name, content=content)


@notes_bp.route('/manage-templates/delete/<template_name>', methods=['POST'])
def delete_template(template_name):
    template_path = os.path.join(GENERATED_FORMS_DIR, template_name)
    if os.path.exists(template_path):
        os.remove(template_path)
        flash(f'Template {template_name} deleted.')
    else:
        flash('Template not found.')
    return redirect(url_for('notes.manage_templates'))


@notes_bp.route('/notes', methods=['GET', 'POST'])
def view_notes():
    metadata = load_notes_metadata()
    notes = [f for f in os.listdir(SAVED_NOTES_DIR) if f.endswith('.txt')]
    # Enhanced search/filter
    search = request.args.get('search', '').strip().lower()
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    tag_filter = request.args.get('tag', '').strip().lower()
    content_search = request.args.get('content_search', '').strip().lower()
    note_type_filter = request.args.get('type', '').strip()
    show_favorites = request.args.get('favorites', '').strip() == 'true'
    
    filtered_notes = []
    all_tags = set()
    for note in notes:
        meta = metadata.get(note, {})
        tags = meta.get('tags', [])
        note_type = meta.get('type', 'template_note')
        is_favorite = meta.get('favorite', False)
        all_tags.update(tags)
        
        # Search in filename
        if search and search not in note.lower():
            continue
            
        # Search in note content
        if content_search:
            try:
                with open(os.path.join(SAVED_NOTES_DIR, note), 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                if content_search not in content:
                    continue
            except:
                continue
                
        # Filter by tag
        if tag_filter and tag_filter not in [t.lower() for t in tags]:
            continue
            
        # Filter by note type
        if note_type_filter and note_type != note_type_filter:
            continue
            
        # Filter by favorites
        if show_favorites and not is_favorite:
            continue
            
        # Date filtering
        if date_from:
            try:
                dt_from = datetime.strptime(date_from, '%Y-%m-%d')
                created = datetime.strptime(meta.get('created', ''), '%Y-%m-%d %H:%M:%S')
                if created < dt_from:
                    continue
            except Exception:
                pass
        if date_to:
            try:
                dt_to = datetime.strptime(date_to, '%Y-%m-%d')
                created = datetime.strptime(meta.get('created', ''), '%Y-%m-%d %H:%M:%S')
                if created > dt_to:
                    continue
            except Exception:
                pass
        filtered_notes.append({
            'filename': note, 
            'created': meta.get('created'), 
            'modified': meta.get('modified'), 
            'tags': tags,
            'type': note_type,
            'favorite': is_favorite
        })
    filtered_notes.sort(key=lambda n: n['created'] or '', reverse=True)
    return render_template('view_notes.html', 
                         notes=filtered_notes, 
                         search=search, 
                         date_from=date_from, 
                         date_to=date_to, 
                         tag_filter=tag_filter, 
                         content_search=content_search,
                         note_type_filter=note_type_filter,
                         show_favorites=show_favorites,
                         all_tags=sorted(all_tags))


@notes_bp.route('/notes/view/<filename>')
def view_note(filename):
    filepath = os.path.join(SAVED_NOTES_DIR, filename)
    metadata = load_notes_metadata().get(filename, {})
    if not os.path.exists(filepath):
        flash('Note not found.')
        return redirect(url_for('notes.view_notes'))
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return render_template('view_single_note.html', filename=filename, content=content, metadata=metadata)


@notes_bp.route('/notes/delete/<filename>', methods=['POST'])
def delete_note(filename):
    filepath = os.path.join(SAVED_NOTES_DIR, filename)
    metadata = load_notes_metadata()
    if os.path.exists(filepath):
        os.remove(filepath)
        if filename in metadata:
            del metadata[filename]
            save_notes_metadata(metadata)
        flash(f'Note {filename} deleted.')
    else:
        flash('Note not found.')
    return redirect(url_for('notes.view_notes'))


@notes_bp.route('/notes/toggle-favorite/<filename>', methods=['POST'])
def toggle_favorite(filename):
    metadata = load_notes_metadata()
    if filename in metadata:
        metadata[filename]['favorite'] = not metadata[filename].get('favorite', False)
        save_notes_metadata(metadata)
        status = 'favorited' if metadata[filename]['favorite'] else 'unfavorited'
        flash(f'Note {status}.')
    else:
        flash('Note not found.')
    return redirect(request.referrer or url_for('notes.view_notes'))


@notes_bp.route('/form/<form_name>', methods=['GET', 'POST'])
def show_form(form_name):
    form_file = f'{form_name}.html' if not form_name.endswith('.html') else form_name
    form_path = os.path.join(GENERATED_FORMS_DIR, form_file)
    if not os.path.exists(form_path):
        return f"Form '{form_name}' not found.", 404
    if request.method == 'POST':
        form_data = request.form.to_dict()
        tags = [t.strip() for t in form_data.pop('tags', '').split(',') if t.strip()]
        if form_data:
            first_field = next(iter(form_data.values()))
            safe_name = ''.join(c for c in first_field if c.isalnum() or c in (' ', '_', '-')).rstrip()
            if not safe_name:
                safe_name = 'note'
        else:
            safe_name = 'note'
        filename = f"{safe_name}.txt"
        filepath = os.path.join(SAVED_NOTES_DIR, filename)
        # Create properly formatted note content
        note_lines = []
        
        # Define field groupings and their display names
        field_mappings = {
            'tags': 'Tags',
            'siteName': 'Customer',
            'techName': 'Technician Name',
            'techNum': 'Technician Phone #',
            'techId': 'Tech ID',
            'issue': 'Issue',
            'solution': 'Solution',
            'addInfo': 'Additional notes / CLI output',
            'cpeIpClli': 'CPE IP / CLLI',
            'cpeIpOrEoHFCMacs': 'CPE IP/CLLI or Modem/NID MAC',
            'serviceType': 'Service Type',
            'portNum': 'UNI Port',
            'otherPortNum': 'Other Port Number',
            'prevServiceSpeed': 'Previous Bandwidth',
            'prevBitsPerSec': 'Previous Bits Per Second',
            'newServiceSpeed': 'New Bandwidth',
            'newBitsPerSec': 'New Bits Per Second',
            'clipsUpdate': 'Update CLIPs',
            'clipsPid': 'CLIPs Project ID',
            'changeType': 'Change Type',
            'offnetCarrier': 'Offnet Carrier',
            'offnetContact': 'Offnet Contact',
            'offnetOrder': 'Offnet Order',
            'offnetCpe': 'Offnet CPE',
            'handoffPort': 'Handoff Port',
            'portType': 'Port Type',
            'portSpeed': 'Port Speed',
            'portDuplex': 'Port Duplex',
            'portAutoNeg': 'Port Auto-Neg',
            'portAutoneg': 'Port Autoneg',
            'serviceVlan': 'Service VLAN',
            'serviceSpeed': 'Service Speed',
            'bitsPerSec': 'Bits Per Second',
            'classOfService': 'Class of Service',
            'offnetTest': 'Offnet Test',
            'demarcInfo': 'Demarc Info',
            'customerAccepting': 'Customer Accepting Service',
            'pocName': 'POC Name',
            'pocPhone': 'POC Phone',
            'pocNumber': 'POC Number',
            'custName': 'Customer Name',
            'custNum': 'Customer Phone #',
            'modemClli': 'Modem CLLI',
            'modemMac': 'Modem MAC',
            'nidClli': 'NID CLLI',
            'nidMac': 'NID MAC',
            'nidIP': 'NID IP',
            'ontClli': 'CLLI',
            'ontMac': 'MAC',
            'rxPower': 'Downstream Rx Power',
            'txPower': 'Upstream Tx Power',
            'cmts': 'CMTS',
            'firmwareVersion': 'Firmware Version',
            'enniPort': 'ENNI Port',
            'bandwidth': 'Bandwidth',
            'surSubInterface': 'SUR Sub-interface'
        }
        
        # Group fields by type for better organization
        basic_fields = ['tags', 'siteName', 'techName', 'techNum', 'techId', 'issue']
        equipment_fields = ['modemClli', 'modemMac', 'nidClli', 'nidMac', 'nidIP', 'ontClli', 'ontMac']
        service_fields = ['cpeIpClli', 'cpeIpOrEoHFCMacs', 'serviceType', 'portNum', 'otherPortNum', 'serviceVlan']
        port_fields = ['portSpeed', 'portDuplex', 'portAutoNeg', 'portAutoneg', 'enniPort']
        bandwidth_fields = ['prevServiceSpeed', 'prevBitsPerSec', 'newServiceSpeed', 'newBitsPerSec', 'serviceSpeed', 'bandwidth']
        offnet_fields = ['offnetCarrier', 'offnetContact', 'offnetOrder', 'offnetCpe', 'handoffPort', 'portType', 'portSpeed', 'portAutoneg', 'serviceSpeed', 'bitsPerSec', 'classOfService', 'offnetTest']
        clips_fields = ['clipsUpdate', 'clipsPid']
        change_fields = ['changeType']
        customer_fields = ['customerAccepting', 'pocName', 'pocPhone', 'pocNumber', 'custName', 'custNum']
        power_fields = ['rxPower', 'txPower']
        system_fields = ['cmts', 'firmwareVersion']
        disconnect_fields = ['surSubInterface']
        text_fields = ['solution', 'addInfo', 'demarcInfo']
        
        # Add basic information
        basic_info = []
        for field in basic_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                basic_info.append(f"{display_name}: {form_data[field]}")
        
        if basic_info:
            note_lines.extend(basic_info)
            note_lines.append("")  # Empty line for spacing
        
        # Add equipment information
        equipment_info = []
        for field in equipment_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                equipment_info.append(f"{display_name}: {form_data[field]}")
        
        if equipment_info:
            note_lines.extend(equipment_info)
            note_lines.append("")
        
        # Add service configuration
        service_info = []
        for field in service_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                service_info.append(f"{display_name}: {form_data[field]}")
        
        if service_info:
            note_lines.extend(service_info)
            note_lines.append("")
        
        # Add port configuration
        port_info = []
        for field in port_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                port_info.append(f"{display_name}: {form_data[field]}")
        
        if port_info:
            note_lines.extend(port_info)
            note_lines.append("")
        
        # Add bandwidth configuration
        bandwidth_info = []
        for field in bandwidth_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                bandwidth_info.append(f"{display_name}: {form_data[field]}")
        
        if bandwidth_info:
            note_lines.extend(bandwidth_info)
            note_lines.append("")
        
        # Add offnet configuration
        offnet_info = []
        for field in offnet_fields:
            if field in form_data and form_data[field]:
                # Special handling for service speed and bits per second combination
                if field == 'serviceSpeed' and 'bitsPerSec' in form_data and form_data['bitsPerSec']:
                    # Skip this field as it will be combined with bitsPerSec
                    continue
                elif field == 'bitsPerSec' and 'serviceSpeed' in form_data and form_data['serviceSpeed']:
                    # Combine service speed and bits per second
                    service_speed = form_data['serviceSpeed']
                    bits_per_sec = form_data['bitsPerSec']
                    offnet_info.append(f"Service Speed: {service_speed} {bits_per_sec}")
                else:
                    # Handle individual fields normally
                    display_name = field_mappings.get(field, field.replace('_', ' ').title())
                    offnet_info.append(f"{display_name}: {form_data[field]}")
        
        if offnet_info:
            note_lines.extend(offnet_info)
            note_lines.append("")
        
        # Add CLIPs configuration
        clips_info = []
        for field in clips_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                clips_info.append(f"{display_name}: {form_data[field]}")
        
        if clips_info:
            note_lines.extend(clips_info)
            note_lines.append("")
        
        # Add change type
        for field in change_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                note_lines.append(f"{display_name}: {form_data[field]}")
                note_lines.append("")
        
        # Add customer acceptance information
        customer_info = []
        for field in customer_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                customer_info.append(f"{display_name}: {form_data[field]}")
        
        if customer_info:
            note_lines.extend(customer_info)
            note_lines.append("")
        
        # Add power levels
        power_info = []
        for field in power_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                power_info.append(f"{display_name}: {form_data[field]}")
        
        if power_info:
            note_lines.extend(power_info)
            note_lines.append("")
        
        # Add system information
        system_info = []
        for field in system_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                system_info.append(f"{display_name}: {form_data[field]}")
        
        if system_info:
            note_lines.extend(system_info)
            note_lines.append("")
        
        # Add disconnect information
        disconnect_info = []
        for field in disconnect_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                disconnect_info.append(f"{display_name}: {form_data[field]}")
        
        if disconnect_info:
            note_lines.extend(disconnect_info)
            note_lines.append("")
        
        # Add text fields with proper formatting
        for field in text_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                note_lines.append(f"{display_name}:")
                note_lines.append(form_data[field])
                note_lines.append("")
        
        # Remove trailing empty lines
        while note_lines and note_lines[-1] == "":
            note_lines.pop()
        
        note_content = '\n'.join(note_lines)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        metadata = load_notes_metadata()
        if filename in metadata:
            metadata[filename]['modified'] = now
            metadata[filename]['tags'] = tags
        else:
            metadata[filename] = {'created': now, 'modified': now, 'tags': tags, 'type': 'template_note'}
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(note_content)
        save_notes_metadata(metadata)
        flash('Note saved successfully!')
        return render_template('note_output.html', form_data=form_data, filename=filename, note_content=note_content)
    return render_template(f'generated_forms/{form_file}')


@notes_bp.route('/download/<filename>')
def download_note(filename):
    return send_from_directory(SAVED_NOTES_DIR, filename, as_attachment=True)


@notes_bp.route('/email/<filename>')
def email_note(filename):
    filepath = os.path.join(SAVED_NOTES_DIR, filename)
    if not os.path.exists(filepath):
        flash('Note not found.')
        return redirect(url_for('notes.view_notes'))
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    subject = urllib.parse.quote(f"Note: {filename}")
    body = urllib.parse.quote(content)
    mailto_link = f"mailto:?subject={subject}&body={body}"
    return redirect(mailto_link)


@notes_bp.route('/quick-notes', methods=['GET', 'POST'])
def quick_notes():
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        tags = [t.strip() for t in request.form.get('tags', '').split(',') if t.strip()]
        
        if content:
            # Generate filename from first line or timestamp
            first_line = content.split('\n')[0][:50] if content else 'quick_note'
            safe_name = ''.join(c for c in first_line if c.isalnum() or c in (' ', '_', '-')).rstrip()
            if not safe_name:
                safe_name = 'quick_note'
            
            filename = f"{safe_name}.txt"
            filepath = os.path.join(SAVED_NOTES_DIR, filename)
            
            # Handle duplicate filenames
            counter = 1
            original_filename = filename
            while os.path.exists(filepath):
                name_part = original_filename.replace('.txt', '')
                filename = f"{name_part}_{counter}.txt"
                filepath = os.path.join(SAVED_NOTES_DIR, filename)
                counter += 1
            
            # Save the note
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            metadata = load_notes_metadata()
            metadata[filename] = {'created': now, 'modified': now, 'tags': tags, 'type': 'quick_note'}
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            save_notes_metadata(metadata)
            flash('Quick note saved successfully!')
            return redirect(url_for('notes.quick_notes'))
    
    notes_metadata = load_notes_metadata()
    # Filter out any non-dictionary entries to prevent template errors
    filtered_metadata = {filename: meta for filename, meta in notes_metadata.items() 
                        if isinstance(meta, dict)}
    return render_template('quick_notes.html', notes_metadata=filtered_metadata)


@notes_bp.route('/quick-notes/view/<filename>')
def view_quick_note(filename):
    filepath = os.path.join(SAVED_NOTES_DIR, filename)
    metadata = load_notes_metadata().get(filename, {})
    if not os.path.exists(filepath):
        flash('Note not found.')
        return redirect(url_for('notes.quick_notes'))
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return render_template('view_quick_note.html', filename=filename, content=content, metadata=metadata)


@notes_bp.route('/quick-notes/edit/<filename>', methods=['GET', 'POST'])
def edit_quick_note(filename):
    filepath = os.path.join(SAVED_NOTES_DIR, filename)
    metadata = load_notes_metadata().get(filename, {})
    
    if not os.path.exists(filepath):
        flash('Note not found.')
        return redirect(url_for('notes.quick_notes'))
    
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        tags = [t.strip() for t in request.form.get('tags', '').split(',') if t.strip()]
        
        if content:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            metadata['modified'] = now
            metadata['tags'] = tags
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Update the full metadata dictionary
            all_metadata = load_notes_metadata()
            all_metadata[filename] = metadata
            save_notes_metadata(all_metadata)
            flash('Quick note updated successfully!')
            return redirect(url_for('notes.view_quick_note', filename=filename))
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return render_template('edit_quick_note.html', filename=filename, content=content, metadata=metadata)


@notes_bp.route('/quick-notes/delete/<filename>', methods=['POST'])
def delete_quick_note(filename):
    filepath = os.path.join(SAVED_NOTES_DIR, filename)
    metadata = load_notes_metadata()
    if os.path.exists(filepath):
        os.remove(filepath)
        if filename in metadata:
            del metadata[filename]
            save_notes_metadata(metadata)
        flash(f'Quick note {filename} deleted.')
    else:
        flash('Note not found.')
    return redirect(url_for('notes.quick_notes'))


@notes_bp.route('/notes/bulk-delete', methods=['POST'])
def bulk_delete_notes():
    selected_notes = request.form.getlist('selected_notes')
    if not selected_notes:
        flash('No notes selected for deletion.')
        return redirect(url_for('notes.view_notes'))
    
    metadata = load_notes_metadata()
    deleted_count = 0
    
    for filename in selected_notes:
        filepath = os.path.join(SAVED_NOTES_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            if filename in metadata:
                del metadata[filename]
            deleted_count += 1
    
    save_notes_metadata(metadata)
    flash(f'{deleted_count} notes deleted successfully.')
    return redirect(url_for('notes.view_notes'))


@notes_bp.route('/notes/export-all')
def export_all_notes():
    metadata = load_notes_metadata()
    notes = [f for f in os.listdir(SAVED_NOTES_DIR) if f.endswith('.txt')]
    
    export_data = []
    for note in notes:
        filepath = os.path.join(SAVED_NOTES_DIR, note)
        meta = metadata.get(note, {})
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            export_data.append({
                'filename': note,
                'content': content,
                'metadata': meta
            })
        except:
            continue
    
    # Create JSON export
    export_json = json.dumps(export_data, indent=2)
    
    response = make_response(export_json)
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = 'attachment; filename=ttu_notes_export.json'
    return response


@notes_bp.route('/notes/import', methods=['GET', 'POST'])
def import_notes():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if not file.filename.endswith('.json'):
            flash('Please select a JSON file', 'error')
            return redirect(request.url)
        
        try:
            # Read and parse the JSON file
            import_data = json.loads(file.read().decode('utf-8'))
            
            if not isinstance(import_data, list):
                flash('Invalid import file format', 'error')
                return redirect(request.url)
            
            # Load existing metadata
            metadata = load_notes_metadata()
            imported_count = 0
            skipped_count = 0
            
            for note_data in import_data:
                if not isinstance(note_data, dict) or 'filename' not in note_data or 'content' not in note_data:
                    continue
                
                filename = note_data['filename']
                content = note_data['content']
                note_metadata = note_data.get('metadata', {})
                
                # Check if file already exists
                filepath = os.path.join(SAVED_NOTES_DIR, filename)
                if os.path.exists(filepath):
                    # Add timestamp to filename to avoid conflicts
                    name, ext = os.path.splitext(filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{name}_{timestamp}{ext}"
                    filepath = os.path.join(SAVED_NOTES_DIR, filename)
                    note_metadata['filename'] = filename
                
                # Save the note file
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    # Update metadata
                    metadata[filename] = note_metadata
                    imported_count += 1
                    
                except Exception as e:
                    skipped_count += 1
                    continue
            
            # Save updated metadata
            save_notes_metadata(metadata)
            
            if imported_count > 0:
                flash(f'Successfully imported {imported_count} notes!', 'success')
                if skipped_count > 0:
                    flash(f'Skipped {skipped_count} notes due to errors', 'warning')
            else:
                flash('No notes were imported', 'warning')
                
        except json.JSONDecodeError:
            flash('Invalid JSON file format', 'error')
        except Exception as e:
            flash(f'Error importing notes: {str(e)}', 'error')
        
        return redirect(url_for('notes.view_notes'))
    
    return render_template('import_notes.html')


@notes_bp.route('/notes/templates')
def note_templates():
    templates = {
        # Ciena CN Series Templates
        'ciena_cn3903_basic': {
            'name': 'Ciena CN-3903 Basic Commands',
            'tags': 'ciena, cn3903, basic, commands',
            'content': '''# Ciena CN-3903 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment
show interface {port}
show alarms
show performance {port}
show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info'''
        },
        'ciena_cn3916_basic': {
            'name': 'Ciena CN-3916 Basic Commands',
            'tags': 'ciena, cn3916, basic, commands',
            'content': '''# Ciena CN-3916 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment
show interface {port}
show alarms
show performance {port}
show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info'''
        },
        'ciena_cn3930_basic': {
            'name': 'Ciena CN-3930 Basic Commands',
            'tags': 'ciena, cn3930, basic, commands',
            'content': '''# Ciena CN-3930 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment
show interface {port}
show alarms
show performance {port}
show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info'''
        },
        'ciena_cn3924_basic': {
            'name': 'Ciena CN-3924 Basic Commands',
            'tags': 'ciena, cn3924, basic, commands',
            'content': '''# Ciena CN-3924 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment
show interface {port}
show alarms
show performance {port}
show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info'''
        },
        'ciena_5160_basic': {
            'name': 'Ciena 5160 Basic Commands',
            'tags': 'ciena, 5160, basic, commands',
            'content': '''# Ciena 5160 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment
show interface {port}
show alarms
show performance {port}
show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info'''
        },
        'ciena_5170_basic': {
            'name': 'Ciena 5170 Basic Commands',
            'tags': 'ciena, 5170, basic, commands',
            'content': '''# Ciena 5170 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment
show interface {port}
show alarms
show performance {port}
show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info'''
        },
        'ciena_light_levels_extended': {
            'name': 'Ciena Light Level Check (Extended)',
            'tags': 'ciena, light, levels, fiber, troubleshooting',
            'content': '''# Ciena Light Level Check - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info
show equipment ont interface {port} alarms
show equipment ont interface {port} performance
show equipment ont interface {port} configuration

# Expected light levels: -8 to -25 dBm
# Check for any alarms or errors'''
        },
        
        # Cisco ASR9k Templates
        'cisco_asr9k_basic': {
            'name': 'Cisco ASR9k Basic Commands',
            'tags': 'cisco, asr9k, basic, commands',
            'content': '''# Cisco ASR9k Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show version
show interfaces {interface}
show ip interface brief
show ip route
show running-config interface {interface}
show platform hardware qfp active statistics drop
show platform hardware qfp active statistics clear'''
        },
        'cisco_asr9k_bgp': {
            'name': 'Cisco ASR9k BGP Commands',
            'tags': 'cisco, asr9k, bgp, routing',
            'content': '''# Cisco ASR9k BGP Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show ip bgp summary
show ip bgp neighbors {neighbor_ip}
show ip bgp neighbors {neighbor_ip} advertised-routes
show ip bgp neighbors {neighbor_ip} received-routes
show ip bgp {prefix}
show ip route bgp
show bgp all summary'''
        },
        'cisco_asr9k_interface_troubleshooting': {
            'name': 'Cisco ASR9k Interface Troubleshooting',
            'tags': 'cisco, asr9k, interface, troubleshooting',
            'content': '''# Cisco ASR9k Interface Troubleshooting - {interface}
# Date: {date}
# Engineer: {engineer}

show interface {interface}
show interface {interface} counters
show interface {interface} status
show interface {interface} description
show interface {interface} switchport
show platform hardware qfp active statistics drop interface {interface}
show platform hardware qfp active statistics clear interface {interface}'''
        },
        
        # Cisco NCS5500 Templates
        'cisco_ncs5500_basic': {
            'name': 'Cisco NCS5500 Basic Commands',
            'tags': 'cisco, ncs5500, basic, commands',
            'content': '''# Cisco NCS5500 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show version
show interfaces {interface}
show ip interface brief
show ip route
show running-config interface {interface}
show platform hardware qfp active statistics drop
show platform hardware qfp active statistics clear'''
        },
        'cisco_ncs5500_bgp': {
            'name': 'Cisco NCS5500 BGP Commands',
            'tags': 'cisco, ncs5500, bgp, routing',
            'content': '''# Cisco NCS5500 BGP Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show ip bgp summary
show ip bgp neighbors {neighbor_ip}
show ip bgp neighbors {neighbor_ip} advertised-routes
show ip bgp neighbors {neighbor_ip} received-routes
show ip bgp {prefix}
show ip route bgp
show bgp all summary'''
        },
        
        # Nokia 7250 IXR Templates
        'nokia_7250_basic': {
            'name': 'Nokia 7250 IXR Basic Commands',
            'tags': 'nokia, 7250, ixr, basic, commands',
            'content': '''# Nokia 7250 IXR Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show version
show port {port}
show port {port} statistics
show port {port} detail
show interface {interface}
show router interface
show router status'''
        },
        'nokia_7250_bgp': {
            'name': 'Nokia 7250 IXR BGP Commands',
            'tags': 'nokia, 7250, ixr, bgp, routing',
            'content': '''# Nokia 7250 IXR BGP Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show router bgp summary
show router bgp neighbor {neighbor_ip}
show router bgp routes
show router bgp routes {prefix}
show router bgp neighbor {neighbor_ip} received-routes
show router bgp neighbor {neighbor_ip} advertised-routes'''
        },
        
        # Nokia 7750 Templates
        'nokia_7750_basic': {
            'name': 'Nokia 7750 Basic Commands',
            'tags': 'nokia, 7750, basic, commands',
            'content': '''# Nokia 7750 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show version
show port {port}
show port {port} statistics
show port {port} detail
show interface {interface}
show router interface
show router status'''
        },
        'nokia_7750_bgp': {
            'name': 'Nokia 7750 BGP Commands',
            'tags': 'nokia, 7750, bgp, routing',
            'content': '''# Nokia 7750 BGP Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show router bgp summary
show router bgp neighbor {neighbor_ip}
show router bgp routes
show router bgp routes {prefix}
show router bgp neighbor {neighbor_ip} received-routes
show router bgp neighbor {neighbor_ip} advertised-routes'''
        },
        
        # Juniper MX Series Templates
        'juniper_mx_basic': {
            'name': 'Juniper MX Basic Commands',
            'tags': 'juniper, mx, basic, commands',
            'content': '''# Juniper MX Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show version
show interfaces {interface}
show route
show configuration interfaces {interface}
show chassis hardware
show system storage'''
        },
        'juniper_mx_bgp': {
            'name': 'Juniper MX BGP Commands',
            'tags': 'juniper, mx, bgp, routing',
            'content': '''# Juniper MX BGP Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show bgp summary
show bgp neighbor {neighbor_ip}
show bgp neighbor {neighbor_ip} advertised-routes
show bgp neighbor {neighbor_ip} received-routes
show route protocol bgp
show route {prefix}'''
        },
        
        # Juniper ACX Series Templates
        'juniper_acx_basic': {
            'name': 'Juniper ACX Basic Commands',
            'tags': 'juniper, acx, basic, commands',
            'content': '''# Juniper ACX Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show version
show interfaces {interface}
show route
show configuration interfaces {interface}
show chassis hardware
show system storage'''
        },
        'juniper_acx_bgp': {
            'name': 'Juniper ACX BGP Commands',
            'tags': 'juniper, acx, bgp, routing',
            'content': '''# Juniper ACX BGP Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show bgp summary
show bgp neighbor {neighbor_ip}
show bgp neighbor {neighbor_ip} advertised-routes
show bgp neighbor {neighbor_ip} received-routes
show route protocol bgp
show route {prefix}'''
        },
        
        # Generic Troubleshooting Templates
        'fiber_troubleshooting': {
            'name': 'Fiber Troubleshooting Workflow',
            'tags': 'fiber, troubleshooting, light, levels',
            'content': '''# Fiber Troubleshooting - {issue_type}
# Date: {date}
# Engineer: {engineer}
# Issue: {issue_description}

# 1. Check light levels
show equipment ont interface {port} optical-info

# 2. Check interface status
show interface {interface}

# 3. Check alarms
show alarms

# 4. Check performance
show performance {port}

# 5. Expected values
# Light levels: -8 to -25 dBm
# Check for any alarms or errors

# 6. Next steps
# {next_steps}'''
        },
        'routing_troubleshooting': {
            'name': 'Routing Troubleshooting Workflow',
            'tags': 'routing, troubleshooting, bgp, ospf',
            'content': '''# Routing Troubleshooting - {protocol}
# Date: {date}
# Engineer: {engineer}
# Issue: {issue_description}

# 1. Check routing table
show ip route
show route

# 2. Check protocol status
show ip {protocol} neighbor
show {protocol} neighbor

# 3. Check specific routes
show ip route {prefix}
show route {prefix}

# 4. Check BGP (if applicable)
show ip bgp summary
show bgp summary

# 5. Next steps
# {next_steps}'''
        },
        'interface_troubleshooting': {
            'name': 'Interface Troubleshooting Workflow',
            'tags': 'interface, troubleshooting, port, status',
            'content': '''# Interface Troubleshooting - {interface}
# Date: {date}
# Engineer: {engineer}
# Issue: {issue_description}

# 1. Check interface status
show interface {interface}
show port {port}

# 2. Check interface statistics
show interface {interface} counters
show port {port} statistics

# 3. Check interface configuration
show running-config interface {interface}
show configuration interfaces {interface}

# 4. Check for errors
show interface {interface} errors
show port {port} detail

# 5. Next steps
# {next_steps}'''
        }
    }
    
    return render_template('note_templates.html', templates=templates)


@notes_bp.route('/notes/templates/use/<template_id>')
def use_note_template(template_id):
    templates = {
        # Ciena CN Series Templates
        'ciena_cn3903_basic': {
            'name': 'Ciena CN-3903 Basic Commands',
            'tags': 'ciena, cn3903, basic, commands',
            'content': '''# Ciena CN-3903 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment
show interface {port}
show alarms
show performance {port}
show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info'''
        },
        'ciena_cn3916_basic': {
            'name': 'Ciena CN-3916 Basic Commands',
            'tags': 'ciena, cn3916, basic, commands',
            'content': '''# Ciena CN-3916 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment
show interface {port}
show alarms
show performance {port}
show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info'''
        },
        'ciena_cn3930_basic': {
            'name': 'Ciena CN-3930 Basic Commands',
            'tags': 'ciena, cn3930, basic, commands',
            'content': '''# Ciena CN-3930 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment
show interface {port}
show alarms
show performance {port}
show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info'''
        },
        'ciena_cn3924_basic': {
            'name': 'Ciena CN-3924 Basic Commands',
            'tags': 'ciena, cn3924, basic, commands',
            'content': '''# Ciena CN-3924 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment
show interface {port}
show alarms
show performance {port}
show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info'''
        },
        'ciena_5160_basic': {
            'name': 'Ciena 5160 Basic Commands',
            'tags': 'ciena, 5160, basic, commands',
            'content': '''# Ciena 5160 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment
show interface {port}
show alarms
show performance {port}
show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info'''
        },
        'ciena_5170_basic': {
            'name': 'Ciena 5170 Basic Commands',
            'tags': 'ciena, 5170, basic, commands',
            'content': '''# Ciena 5170 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment
show interface {port}
show alarms
show performance {port}
show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info'''
        },
        'ciena_light_levels_extended': {
            'name': 'Ciena Light Level Check (Extended)',
            'tags': 'ciena, light, levels, fiber, troubleshooting',
            'content': '''# Ciena Light Level Check - {device_name}
# Date: {date}
# Engineer: {engineer}

show equipment ont interface {port} detail
show equipment ont interface {port} statistics
show equipment ont interface {port} optical-info
show equipment ont interface {port} alarms
show equipment ont interface {port} performance
show equipment ont interface {port} configuration

# Expected light levels: -8 to -25 dBm
# Check for any alarms or errors'''
        },
        
        # Cisco ASR9k Templates
        'cisco_asr9k_basic': {
            'name': 'Cisco ASR9k Basic Commands',
            'tags': 'cisco, asr9k, basic, commands',
            'content': '''# Cisco ASR9k Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show version
show interfaces {interface}
show ip interface brief
show ip route
show running-config interface {interface}
show platform hardware qfp active statistics drop
show platform hardware qfp active statistics clear'''
        },
        'cisco_asr9k_bgp': {
            'name': 'Cisco ASR9k BGP Commands',
            'tags': 'cisco, asr9k, bgp, routing',
            'content': '''# Cisco ASR9k BGP Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show ip bgp summary
show ip bgp neighbors {neighbor_ip}
show ip bgp neighbors {neighbor_ip} advertised-routes
show ip bgp neighbors {neighbor_ip} received-routes
show ip bgp {prefix}
show ip route bgp
show bgp all summary'''
        },
        'cisco_asr9k_interface_troubleshooting': {
            'name': 'Cisco ASR9k Interface Troubleshooting',
            'tags': 'cisco, asr9k, interface, troubleshooting',
            'content': '''# Cisco ASR9k Interface Troubleshooting - {interface}
# Date: {date}
# Engineer: {engineer}

show interface {interface}
show interface {interface} counters
show interface {interface} status
show interface {interface} description
show interface {interface} switchport
show platform hardware qfp active statistics drop interface {interface}
show platform hardware qfp active statistics clear interface {interface}'''
        },
        
        # Cisco NCS5500 Templates
        'cisco_ncs5500_basic': {
            'name': 'Cisco NCS5500 Basic Commands',
            'tags': 'cisco, ncs5500, basic, commands',
            'content': '''# Cisco NCS5500 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show version
show interfaces {interface}
show ip interface brief
show ip route
show running-config interface {interface}
show platform hardware qfp active statistics drop
show platform hardware qfp active statistics clear'''
        },
        'cisco_ncs5500_bgp': {
            'name': 'Cisco NCS5500 BGP Commands',
            'tags': 'cisco, ncs5500, bgp, routing',
            'content': '''# Cisco NCS5500 BGP Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show ip bgp summary
show ip bgp neighbors {neighbor_ip}
show ip bgp neighbors {neighbor_ip} advertised-routes
show ip bgp neighbors {neighbor_ip} received-routes
show ip bgp {prefix}
show ip route bgp
show bgp all summary'''
        },
        
        # Nokia 7250 IXR Templates
        'nokia_7250_basic': {
            'name': 'Nokia 7250 IXR Basic Commands',
            'tags': 'nokia, 7250, ixr, basic, commands',
            'content': '''# Nokia 7250 IXR Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show version
show port {port}
show port {port} statistics
show port {port} detail
show interface {interface}
show router interface
show router status'''
        },
        'nokia_7250_bgp': {
            'name': 'Nokia 7250 IXR BGP Commands',
            'tags': 'nokia, 7250, ixr, bgp, routing',
            'content': '''# Nokia 7250 IXR BGP Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show router bgp summary
show router bgp neighbor {neighbor_ip}
show router bgp routes
show router bgp routes {prefix}
show router bgp neighbor {neighbor_ip} received-routes
show router bgp neighbor {neighbor_ip} advertised-routes'''
        },
        
        # Nokia 7750 Templates
        'nokia_7750_basic': {
            'name': 'Nokia 7750 Basic Commands',
            'tags': 'nokia, 7750, basic, commands',
            'content': '''# Nokia 7750 Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show version
show port {port}
show port {port} statistics
show port {port} detail
show interface {interface}
show router interface
show router status'''
        },
        'nokia_7750_bgp': {
            'name': 'Nokia 7750 BGP Commands',
            'tags': 'nokia, 7750, bgp, routing',
            'content': '''# Nokia 7750 BGP Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show router bgp summary
show router bgp neighbor {neighbor_ip}
show router bgp routes
show router bgp routes {prefix}
show router bgp neighbor {neighbor_ip} received-routes
show router bgp neighbor {neighbor_ip} advertised-routes'''
        },
        
        # Juniper MX Series Templates
        'juniper_mx_basic': {
            'name': 'Juniper MX Basic Commands',
            'tags': 'juniper, mx, basic, commands',
            'content': '''# Juniper MX Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show version
show interfaces {interface}
show route
show configuration interfaces {interface}
show chassis hardware
show system storage'''
        },
        'juniper_mx_bgp': {
            'name': 'Juniper MX BGP Commands',
            'tags': 'juniper, mx, bgp, routing',
            'content': '''# Juniper MX BGP Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show bgp summary
show bgp neighbor {neighbor_ip}
show bgp neighbor {neighbor_ip} advertised-routes
show bgp neighbor {neighbor_ip} received-routes
show route protocol bgp
show route {prefix}'''
        },
        
        # Juniper ACX Series Templates
        'juniper_acx_basic': {
            'name': 'Juniper ACX Basic Commands',
            'tags': 'juniper, acx, basic, commands',
            'content': '''# Juniper ACX Basic Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show version
show interfaces {interface}
show route
show configuration interfaces {interface}
show chassis hardware
show system storage'''
        },
        'juniper_acx_bgp': {
            'name': 'Juniper ACX BGP Commands',
            'tags': 'juniper, acx, bgp, routing',
            'content': '''# Juniper ACX BGP Commands - {device_name}
# Date: {date}
# Engineer: {engineer}

show bgp summary
show bgp neighbor {neighbor_ip}
show bgp neighbor {neighbor_ip} advertised-routes
show bgp neighbor {neighbor_ip} received-routes
show route protocol bgp
show route {prefix}'''
        },
        
        # Generic Troubleshooting Templates
        'fiber_troubleshooting': {
            'name': 'Fiber Troubleshooting Workflow',
            'tags': 'fiber, troubleshooting, light, levels',
            'content': '''# Fiber Troubleshooting - {issue_type}
# Date: {date}
# Engineer: {engineer}
# Issue: {issue_description}

# 1. Check light levels
show equipment ont interface {port} optical-info

# 2. Check interface status
show interface {interface}

# 3. Check alarms
show alarms

# 4. Check performance
show performance {port}

# 5. Expected values
# Light levels: -8 to -25 dBm
# Check for any alarms or errors

# 6. Next steps
# {next_steps}'''
        },
        'routing_troubleshooting': {
            'name': 'Routing Troubleshooting Workflow',
            'tags': 'routing, troubleshooting, bgp, ospf',
            'content': '''# Routing Troubleshooting - {protocol}
# Date: {date}
# Engineer: {engineer}
# Issue: {issue_description}

# 1. Check routing table
show ip route
show route

# 2. Check protocol status
show ip {protocol} neighbor
show {protocol} neighbor

# 3. Check specific routes
show ip route {prefix}
show route {prefix}

# 4. Check BGP (if applicable)
show ip bgp summary
show bgp summary

# 5. Next steps
# {next_steps}'''
        },
        'interface_troubleshooting': {
            'name': 'Interface Troubleshooting Workflow',
            'tags': 'interface, troubleshooting, port, status',
            'content': '''# Interface Troubleshooting - {interface}
# Date: {date}
# Engineer: {engineer}
# Issue: {issue_description}

# 1. Check interface status
show interface {interface}
show port {port}

# 2. Check interface statistics
show interface {interface} counters
show port {port} statistics

# 3. Check interface configuration
show running-config interface {interface}
show configuration interfaces {interface}

# 4. Check for errors
show interface {interface} errors
show port {port} detail

# 5. Next steps
# {next_steps}'''
        }
    }
    
    if template_id not in templates:
        flash('Template not found.')
        return redirect(url_for('notes.note_templates'))
    
    template = templates[template_id]
    return render_template('use_note_template.html', template=template, template_id=template_id)


@notes_bp.route('/notes/templates/create', methods=['GET', 'POST'])
def create_note_template():
    if request.method == 'POST':
        template_name = request.form.get('template_name', '').strip()
        template_tags = request.form.get('template_tags', '').strip()
        template_content = request.form.get('template_content', '').strip()
        
        if not template_name or not template_content:
            flash('Template name and content are required.')
            return redirect(url_for('notes.create_note_template'))
        
        # Create a unique template ID
        template_id = template_name.lower().replace(' ', '_').replace('-', '_')
        
        # Save to user templates (you could extend this to save to a file)
        flash(f'Template "{template_name}" created successfully! You can now use it from the templates page.')
        return redirect(url_for('notes.note_templates'))
    
    return render_template('create_note_template.html')


@notes_bp.route('/templates/suggestions')
def template_suggestions():
    """Show smart template suggestions based on log analysis"""
    suggestions = generate_smart_template_suggestions()
    return render_template('template_suggestions.html', suggestions=suggestions)


@notes_bp.route('/templates/suggestions/device/<device_name>')
def device_template_suggestions(device_name):
    """Get template suggestions for a specific device"""
    suggestions = get_device_specific_suggestions(device_name)
    return jsonify(suggestions)


@notes_bp.route('/templates/suggestions/create', methods=['POST'])
def create_suggestion_template():
    """Create a new template from a suggestion"""
    try:
        data = request.get_json()
        
        # Generate a unique template name
        base_name = data.get('name', 'Suggested Template')
        template_name = f"{base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create the template content
        template_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{data.get('name', 'Template')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .command {{ background: #f4f4f4; padding: 10px; margin: 5px 0; border-left: 3px solid #007bff; }}
        .variable {{ color: #007bff; font-weight: bold; }}
    </style>
</head>
<body>
    <h2>{data.get('name', 'Template')}</h2>
    <p><em>{data.get('description', 'Generated from log analysis')}</em></p>
    
    <h3>Commands:</h3>
    {{% for command in commands %}}
    <div class="command">{{{{ command }}}}</div>
    {{% endfor %}}
    
    {{% if variables %}}
    <h3>Variables:</h3>
    <ul>
    {{% for var in variables %}}
        <li><span class="variable">{{{{ var }}}}</span></li>
    {{% endfor %}}
    </ul>
    {{% endif %}}
    
    <h3>Results:</h3>
    <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; min-height: 200px;">
        <p><em>Command results will appear here...</em></p>
    </div>
</body>
</html>"""
        
        # Save the template
        template_path = os.path.join(TEMPLATES_DIR, f"{template_name}.html")
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        # Add to templates metadata
        templates_metadata = load_templates_metadata()
        templates_metadata[template_name] = {
            'name': data.get('name', 'Template'),
            'description': data.get('description', 'Generated from log analysis'),
            'category': data.get('category', 'Generated'),
            'created': datetime.now().isoformat(),
            'variables': data.get('variables', [])
        }
        save_templates_metadata(templates_metadata)
        
        flash(f'Template "{data.get("name")}" created successfully!', 'success')
        return jsonify({'success': True, 'template_name': template_name})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@notes_bp.route('/manage-categories', methods=['GET', 'POST'])
def manage_categories():
    """Manage template categories"""
    if request.method == 'POST':
        # Handle category management (add, edit, delete)
        action = request.form.get('action')
        category_name = request.form.get('category_name', '').strip()
        
        if action == 'add' and category_name:
            templates_metadata = load_templates_metadata()
            # Add new category logic here if needed
            flash(f'Category "{category_name}" added successfully!', 'success')
        elif action == 'delete' and category_name:
            # Delete category logic here if needed
            flash(f'Category "{category_name}" deleted successfully!', 'success')
    
    # Get all unique categories from templates
    templates_metadata = load_templates_metadata()
    categories = set()
    for template_info in templates_metadata.values():
        if 'category' in template_info:
            categories.add(template_info['category'])
    
    return render_template('manage_categories.html', categories=sorted(categories))
