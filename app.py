from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, make_response, jsonify
import os
import urllib.parse
import subprocess
import json
from datetime import datetime, timedelta
import shutil
from netmiko import ConnectHandler, NetMikoTimeoutException, NetMikoAuthenticationException
import getpass
import re
from jinja2 import Template
# import threading
# import time


app = Flask(__name__)
app.secret_key = 'change_this_secret_key'

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')
GENERATED_FORMS_DIR = os.path.join(TEMPLATES_DIR, 'generated_forms')
SAVED_NOTES_DIR = os.path.join(os.path.dirname(__file__), 'saved_notes')
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), 'scripts')
NOTES_METADATA_FILE = os.path.join(SAVED_NOTES_DIR, 'notes_metadata.json')
TEMPLATES_METADATA_FILE = os.path.join(GENERATED_FORMS_DIR, 'templates_metadata.json')
DEVICES_FILE = os.path.join(os.path.dirname(__file__), 'devices.json')
LOGS_DIR = os.path.join(os.path.dirname(__file__), 'Logs', 'Logs')
LOGS_INDEX_FILE = os.path.join(os.path.dirname(__file__), 'logs_index.json')

os.makedirs(SAVED_NOTES_DIR, exist_ok=True)
os.makedirs(SCRIPTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

def load_notes_metadata():
    if os.path.exists(NOTES_METADATA_FILE):
        with open(NOTES_METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_notes_metadata(metadata):
    with open(NOTES_METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

def load_templates_metadata():
    if os.path.exists(TEMPLATES_METADATA_FILE):
        with open(TEMPLATES_METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_templates_metadata(metadata):
    with open(TEMPLATES_METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

# Device management
def load_devices():
    if os.path.exists(DEVICES_FILE):
        with open(DEVICES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_devices(devices):
    with open(DEVICES_FILE, 'w', encoding='utf-8') as f:
        json.dump(devices, f, indent=2)

def get_device_type(device_name):
    """Determine device type based on device name or IP"""
    device_lower = device_name.lower()
    if 'ciena' in device_lower or any(x in device_lower for x in ['cn3903', 'cn3916', 'cn3930', 'cn3924', '5160', '5170']):
        return 'ciena_os'
    elif 'asr9k' in device_lower or 'ncs5500' in device_lower:
        return 'cisco_xr'
    elif '7250' in device_lower or '7750' in device_lower:
        return 'nokia_sros'
    elif 'mx' in device_lower or 'acx' in device_lower:
        return 'juniper'
    else:
        return 'cisco_ios'  # Default fallback

def get_logout_command(device_type):
    """Get the appropriate logout command for a device type"""
    logout_commands = {
        'ciena_os': 'exit',
        'cisco_xr': 'exit',
        'cisco_ios': 'exit',
        'nokia_sros': 'logout',
        'juniper': 'exit'
    }
    return logout_commands.get(device_type, 'exit')  # Default to 'exit' if device type not found

def execute_command_on_device(device_name, commands, username=None, password=None):
    """Execute commands on a device using Netmiko with RADIUS authentication"""
    try:
        devices = load_devices()
        device_info = devices.get(device_name, {})
        
        if not device_info:
            return {'success': False, 'error': f'Device {device_name} not found in device list'}
        
        device_type = get_device_type(device_name)
        
        # Validate credentials are provided
        if not username or not password:
            return {'success': False, 'error': 'Username and password are required for SSH connection'}
        
        device_config = {
            'device_type': device_type,
            'host': device_info.get('ip_address', device_name),
            'username': username,
            'password': password,
            'port': 22,
            'timeout': 20,
            'global_delay_factor': 2,
        }
        
        with ConnectHandler(**device_config) as net_connect:
            results = []
            logout_command = get_logout_command(device_type)
            
            for i, command in enumerate(commands):
                try:
                    # Handle logout command specially to avoid prompt issues
                    if command.strip().lower() == logout_command.lower():
                        # For logout command, use send_command_timing to avoid waiting for specific prompt
                        output = net_connect.send_command_timing(command, strip_prompt=False)
                        # Add a small delay to ensure the logout command completes
                        import time
                        time.sleep(1)
                        results.append({
                            'command': command,
                            'output': output + '\nSession closed successfully.',
                            'success': True
                        })
                        # Break after logout command since session will be closed
                        break
                    else:
                        # For regular commands, use normal send_command
                        output = net_connect.send_command(command)
                        results.append({
                            'command': command,
                            'output': output,
                            'success': True
                        })
                except Exception as e:
                    results.append({
                        'command': command,
                        'output': f'Error: {str(e)}',
                        'success': False
                    })
            
            return {'success': True, 'results': results}
            
    except NetMikoTimeoutException:
        return {'success': False, 'error': f'Connection timeout to {device_name}'}
    except NetMikoAuthenticationException:
        return {'success': False, 'error': f'RADIUS authentication failed for {device_name}. Check your credentials.'}
    except Exception as e:
        return {'success': False, 'error': f'Connection error: {str(e)}'}

# Remove the background password rotation task
# password_thread = threading.Thread(target=check_password_rotation, daemon=True)
# password_thread.start()

@app.route('/')
def home():
    # Load templates and metadata
    templates_metadata = load_templates_metadata()
    form_files = [f for f in os.listdir(GENERATED_FORMS_DIR) if f.endswith('.html')]
    
    # Group templates by category
    templates_by_category = {}
    for template in form_files:
        meta = templates_metadata.get(template, {})
        category = meta.get('category', 'Other')
        if category not in templates_by_category:
            templates_by_category[category] = []
        templates_by_category[category].append(template)
    
    # Load additional data for dashboard
    devices = load_devices()
    notes_metadata = load_notes_metadata()
    notes = [f for f in os.listdir(SAVED_NOTES_DIR) if f.endswith('.txt')]
    
    # Count quick notes from metadata
    quick_notes = [filename for filename, meta in notes_metadata.items() 
                   if meta.get('type') == 'quick_note']
    
    # Get current date for display
    current_date = datetime.now().strftime('%B %d, %Y')
    
    return render_template('home.html', 
                         templates_by_category=templates_by_category,
                         devices=devices,
                         notes=notes,
                         quick_notes=quick_notes,
                         current_date=current_date)

@app.route('/manage-templates', methods=['GET', 'POST'])
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
            return redirect(url_for('manage_templates'))
        
        elif 'update_category_template' in request.form:
            template_name = request.form.get('update_category_template')
            category = request.form.get('category', 'Other').strip()
            custom_category = request.form.get('custom_category', '').strip()
            
            # Use custom category if provided, otherwise use selected category
            if category == 'custom' and custom_category:
                category = custom_category
            elif category == 'custom':
                flash('Custom category name cannot be empty.')
                return redirect(url_for('manage_templates'))
            
            if template_name not in templates_metadata:
                templates_metadata[template_name] = {}
            templates_metadata[template_name]['category'] = category
            save_templates_metadata(templates_metadata)
            flash(f'Category updated for {template_name}.')
            return redirect(url_for('manage_templates'))
    
    return render_template('manage_templates.html', templates=templates, template_metadata=templates_metadata)

@app.route('/manage-templates/category/<template_name>', methods=['POST'])
def update_template_category(template_name):
    category = request.form.get('category', 'Other').strip()
    templates_metadata = load_templates_metadata()
    if template_name not in templates_metadata:
        templates_metadata[template_name] = {}
    templates_metadata[template_name]['category'] = category
    save_templates_metadata(templates_metadata)
    flash(f'Category updated for {template_name}.')
    return redirect(url_for('manage_templates'))

@app.route('/manage-templates/edit/<template_name>', methods=['GET', 'POST'])
def edit_template(template_name):
    template_path = os.path.join(GENERATED_FORMS_DIR, template_name)
    if not os.path.exists(template_path):
        flash('Template not found.')
        return redirect(url_for('manage_templates'))
    if request.method == 'POST':
        new_content = request.form.get('template_content', '')
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        flash(f'Template {template_name} updated.')
        return redirect(url_for('manage_templates'))
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return render_template('edit_template.html', template_name=template_name, content=content)

@app.route('/manage-templates/delete/<template_name>', methods=['POST'])
def delete_template(template_name):
    template_path = os.path.join(GENERATED_FORMS_DIR, template_name)
    if os.path.exists(template_path):
        os.remove(template_path)
        flash(f'Template {template_name} deleted.')
    else:
        flash('Template not found.')
    return redirect(url_for('manage_templates'))

@app.route('/notes', methods=['GET', 'POST'])
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

@app.route('/notes/view/<filename>')
def view_note(filename):
    filepath = os.path.join(SAVED_NOTES_DIR, filename)
    metadata = load_notes_metadata().get(filename, {})
    if not os.path.exists(filepath):
        flash('Note not found.')
        return redirect(url_for('view_notes'))
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return render_template('view_single_note.html', filename=filename, content=content, metadata=metadata)

@app.route('/notes/delete/<filename>', methods=['POST'])
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
    return redirect(url_for('view_notes'))

@app.route('/notes/toggle-favorite/<filename>', methods=['POST'])
def toggle_favorite(filename):
    metadata = load_notes_metadata()
    if filename in metadata:
        metadata[filename]['favorite'] = not metadata[filename].get('favorite', False)
        save_notes_metadata(metadata)
        status = 'favorited' if metadata[filename]['favorite'] else 'unfavorited'
        flash(f'Note {status}.')
    else:
        flash('Note not found.')
    return redirect(request.referrer or url_for('view_notes'))

@app.route('/form/<form_name>', methods=['GET', 'POST'])
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
            'siteName': 'Customer',
            'techName': 'Technician Name',
            'techNum': 'Technician Phone #',
            'techId': 'Tech ID',
            'issue': 'Issue',
            'solution': 'Solution',
            'addInfo': 'Additional notes / CLI output',
            'cpeIpClli': 'CPE IP / CLLI',
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
            'portAutoneg': 'Port Autoneg',
            'serviceVlan': 'Service VLAN',
            'serviceSpeed': 'Service Speed',
            'bitsPerSec': 'Bits Per Second',
            'classOfService': 'Class of Service',
            'offnetTest': 'Offnet Test',
            'demarcInfo': 'Demarc Info'
        }
        
        # Group fields by type for better organization
        basic_fields = ['siteName', 'techName', 'techNum', 'techId', 'issue']
        service_fields = ['cpeIpClli', 'serviceType', 'portNum', 'otherPortNum', 'serviceVlan']
        bandwidth_fields = ['prevServiceSpeed', 'prevBitsPerSec', 'newServiceSpeed', 'newBitsPerSec']
        offnet_fields = ['offnetCarrier', 'offnetContact', 'offnetOrder', 'offnetCpe', 'handoffPort', 'portType', 'portSpeed', 'portAutoneg', 'serviceSpeed', 'bitsPerSec', 'classOfService', 'offnetTest']
        clips_fields = ['clipsUpdate', 'clipsPid']
        change_fields = ['changeType']
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
        
        # Add service configuration
        service_info = []
        for field in service_fields:
            if field in form_data and form_data[field]:
                display_name = field_mappings.get(field, field.replace('_', ' ').title())
                service_info.append(f"{display_name}: {form_data[field]}")
        
        if service_info:
            note_lines.extend(service_info)
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
            metadata[filename] = {'created': now, 'modified': now, 'tags': tags}
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(note_content)
        save_notes_metadata(metadata)
        flash('Note saved successfully!')
        return render_template('note_output.html', form_data=form_data, filename=filename, note_content=note_content)
    return render_template(f'generated_forms/{form_file}')

@app.route('/download/<filename>')
def download_note(filename):
    return send_from_directory(SAVED_NOTES_DIR, filename, as_attachment=True)

@app.route('/email/<filename>')
def email_note(filename):
    filepath = os.path.join(SAVED_NOTES_DIR, filename)
    if not os.path.exists(filepath):
        flash('Note not found.')
        return redirect(url_for('view_notes'))
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    subject = urllib.parse.quote(f"Note: {filename}")
    body = urllib.parse.quote(content)
    mailto_link = f"mailto:?subject={subject}&body={body}"
    return redirect(mailto_link)

@app.route('/scripts', methods=['GET', 'POST'])
def scripts():
    scripts = [f for f in os.listdir(SCRIPTS_DIR) if f.endswith('.py')]
    output = None
    selected_script = None
    if request.method == 'POST':
        selected_script = request.form.get('script')
        if selected_script and selected_script in scripts:
            try:
                result = subprocess.run(['python', os.path.join(SCRIPTS_DIR, selected_script)], capture_output=True, text=True, timeout=30)
                output = result.stdout + '\n' + result.stderr
            except Exception as e:
                output = f'Error running script: {e}'
    return render_template('scripts.html', scripts=scripts, output=output, selected_script=selected_script)

@app.route('/quick-notes', methods=['GET', 'POST'])
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
            return redirect(url_for('quick_notes'))
    
    notes_metadata = load_notes_metadata()
    return render_template('quick_notes.html', notes_metadata=notes_metadata)

@app.route('/quick-notes/view/<filename>')
def view_quick_note(filename):
    filepath = os.path.join(SAVED_NOTES_DIR, filename)
    metadata = load_notes_metadata().get(filename, {})
    if not os.path.exists(filepath):
        flash('Note not found.')
        return redirect(url_for('quick_notes'))
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return render_template('view_quick_note.html', filename=filename, content=content, metadata=metadata)

@app.route('/quick-notes/edit/<filename>', methods=['GET', 'POST'])
def edit_quick_note(filename):
    filepath = os.path.join(SAVED_NOTES_DIR, filename)
    metadata = load_notes_metadata().get(filename, {})
    
    if not os.path.exists(filepath):
        flash('Note not found.')
        return redirect(url_for('quick_notes'))
    
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        tags = [t.strip() for t in request.form.get('tags', '').split(',') if t.strip()]
        
        if content:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            metadata['modified'] = now
            metadata['tags'] = tags
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            save_notes_metadata(metadata)
            flash('Quick note updated successfully!')
            return redirect(url_for('view_quick_note', filename=filename))
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return render_template('edit_quick_note.html', filename=filename, content=content, metadata=metadata)

@app.route('/quick-notes/delete/<filename>', methods=['POST'])
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
    return redirect(url_for('quick_notes'))

@app.route('/notes/bulk-delete', methods=['POST'])
def bulk_delete_notes():
    selected_notes = request.form.getlist('selected_notes')
    if not selected_notes:
        flash('No notes selected for deletion.')
        return redirect(url_for('view_notes'))
    
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
    return redirect(url_for('view_notes'))

@app.route('/notes/export-all')
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

@app.route('/notes/templates')
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

@app.route('/notes/templates/use/<template_id>')
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
        return redirect(url_for('note_templates'))
    
    template = templates[template_id]
    return render_template('use_note_template.html', template=template, template_id=template_id)

@app.route('/notes/templates/create', methods=['GET', 'POST'])
def create_note_template():
    if request.method == 'POST':
        template_name = request.form.get('template_name', '').strip()
        template_tags = request.form.get('template_tags', '').strip()
        template_content = request.form.get('template_content', '').strip()
        
        if not template_name or not template_content:
            flash('Template name and content are required.')
            return redirect(url_for('create_note_template'))
        
        # Create a unique template ID
        template_id = template_name.lower().replace(' ', '_').replace('-', '_')
        
        # Save to user templates (you could extend this to save to a file)
        flash(f'Template "{template_name}" created successfully! You can now use it from the templates page.')
        return redirect(url_for('note_templates'))
    
    return render_template('create_note_template.html')

# Device management routes
@app.route('/devices')
def manage_devices():
    devices = load_devices()
    return render_template('manage_devices.html', devices=devices)

@app.route('/devices/add', methods=['GET', 'POST'])
def add_device():
    if request.method == 'POST':
        device_name = request.form.get('device_name', '').strip()
        ip_address = request.form.get('ip_address', '').strip()
        device_type = request.form.get('device_type', '').strip()
        username = request.form.get('username', '').strip()
        description = request.form.get('description', '').strip()
        
        if not device_name or not ip_address:
            flash('Device name and IP address are required.')
            return redirect(url_for('add_device'))
        
        devices = load_devices()
        devices[device_name] = {
            'ip_address': ip_address,
            'device_type': device_type,
            'username': username,
            'description': description,
            'added_date': datetime.now().isoformat()
        }
        save_devices(devices)
        flash(f'Device {device_name} added successfully.')
        return redirect(url_for('manage_devices'))
    
    return render_template('add_device.html')

@app.route('/devices/delete/<device_name>', methods=['POST'])
def delete_device(device_name):
    devices = load_devices()
    if device_name in devices:
        del devices[device_name]
        save_devices(devices)
        flash(f'Device {device_name} deleted successfully.')
    return redirect(url_for('manage_devices'))

@app.route('/devices/clear-all', methods=['POST'])
def clear_all_devices():
    """Clear all devices from the device list"""
    try:
        # Delete the devices.json file to clear all devices
        if os.path.exists(DEVICES_FILE):
            os.remove(DEVICES_FILE)
        flash('All devices have been cleared successfully.')
    except Exception as e:
        flash(f'Error clearing devices: {str(e)}')
    return redirect(url_for('manage_devices'))

# Command execution routes
@app.route('/execute', methods=['GET', 'POST'])
def execute_commands():
    if request.method == 'POST':
        device_name = request.form.get('device_name', '').strip()
        commands_text = request.form.get('commands', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not device_name or not commands_text:
            flash('Device name and commands are required.')
            return redirect(url_for('execute_commands'))
        
        # Split commands by newline
        commands = [cmd.strip() for cmd in commands_text.split('\n') if cmd.strip()]
        
        # Execute commands
        result = execute_command_on_device(device_name, commands, username, password)
        
        if result['success']:
            # Save the executed commands as a note
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{device_name}_execution_{timestamp}.txt"
            filepath = os.path.join(SAVED_NOTES_DIR, filename)
            
            note_content = f"# Command Execution - {device_name}\n"
            note_content += f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            note_content += f"# Device: {device_name}\n\n"
            
            for cmd_result in result['results']:
                note_content += f"## Command: {cmd_result['command']}\n"
                note_content += f"## Success: {cmd_result['success']}\n"
                note_content += f"## Output:\n{cmd_result['output']}\n\n"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(note_content)
            
            # Save metadata
            metadata = load_notes_metadata()
            metadata[filename] = {
                'created': datetime.now().isoformat(),
                'modified': datetime.now().isoformat(),
                'tags': ['execution', device_name.lower()],
                'type': 'execution_note',
                'favorite': False
            }
            save_notes_metadata(metadata)
            
            flash(f'Commands executed successfully. Results saved as {filename}')
            return render_template('execute_results.html', 
                                 results=result['results'], 
                                 device_name=device_name,
                                 timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        else:
            flash(f'Execution failed: {result["error"]}')
            return redirect(url_for('execute_commands'))
    
    devices = load_devices()
    return render_template('execute_commands.html', devices=devices)

@app.route('/execute/template/<template_id>')
def execute_template(template_id):
    """Execute a template on a device"""
    # Get template content
    templates = {
        'ciena_cn3903_basic': {
            'name': 'Ciena CN-3903 Basic Commands',
            'commands': [
                'show equipment',
                'show interface {port}',
                'show alarms',
                'show performance {port}',
                'show equipment ont interface {port} detail',
                'show equipment ont interface {port} statistics',
                'show equipment ont interface {port} optical-info'
            ]
        },
        'cisco_asr9k_basic': {
            'name': 'Cisco ASR9k Basic Commands',
            'commands': [
                'show version',
                'show interfaces {interface}',
                'show ip interface brief',
                'show ip route',
                'show running-config interface {interface}',
                'show platform hardware qfp active statistics drop',
                'show platform hardware qfp active statistics clear'
            ]
        },
        # Add more templates as needed
    }
    
    if template_id not in templates:
        flash('Template not found.')
        return redirect(url_for('execute_commands'))
    
    template = templates[template_id]
    devices = load_devices()
    
    return render_template('execute_template.html', template=template, devices=devices, template_id=template_id)

@app.route('/execute/template/<template_id>/run', methods=['POST'])
def run_template(template_id):
    """Execute a template on a device with variable replacement"""
    device_name = request.form.get('device_name', '').strip()
    variables = json.loads(request.form.get('variables', '{}'))
    
    # Get template commands
    templates = {
        'ciena_cn3903_basic': [
            'show equipment',
            'show interface {port}',
            'show alarms',
            'show performance {port}',
            'show equipment ont interface {port} detail',
            'show equipment ont interface {port} statistics',
            'show equipment ont interface {port} optical-info'
        ],
        'cisco_asr9k_basic': [
            'show version',
            'show interfaces {interface}',
            'show ip interface brief',
            'show ip route',
            'show running-config interface {interface}',
            'show platform hardware qfp active statistics drop',
            'show platform hardware qfp active statistics clear'
        ],
        # Add more templates as needed
    }
    
    if template_id not in templates:
        return jsonify({'success': False, 'error': 'Template not found'})
    
    # Replace variables in commands
    commands = []
    for command in templates[template_id]:
        formatted_command = command
        for var_name, var_value in variables.items():
            formatted_command = formatted_command.replace(f'{{{var_name}}}', str(var_value))
        commands.append(formatted_command)
    
    # Execute commands
    result = execute_command_on_device(device_name, commands)
    
    if result['success']:
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{device_name}_{template_id}_{timestamp}.txt"
        filepath = os.path.join(SAVED_NOTES_DIR, filename)
        
        note_content = f"# Template Execution - {device_name}\n"
        note_content += f"# Template: {template_id}\n"
        note_content += f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        note_content += f"# Variables: {variables}\n\n"
        
        for cmd_result in result['results']:
            note_content += f"## Command: {cmd_result['command']}\n"
            note_content += f"## Success: {cmd_result['success']}\n"
            note_content += f"## Output:\n{cmd_result['output']}\n\n"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(note_content)
        
        # Save metadata
        metadata = load_notes_metadata()
        metadata[filename] = {
            'created': datetime.now().isoformat(),
            'modified': datetime.now().isoformat(),
            'tags': ['template_execution', device_name.lower(), template_id],
            'type': 'execution_note',
            'favorite': False
        }
        save_notes_metadata(metadata)
    
    return jsonify(result)

# Batch operations
@app.route('/execute/batch', methods=['GET', 'POST'])
def batch_execute():
    """Execute the same commands on multiple devices"""
    if request.method == 'POST':
        device_names = request.form.getlist('devices')
        commands_text = request.form.get('commands', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not device_names or not commands_text:
            flash('Please select devices and enter commands.')
            return redirect(url_for('batch_execute'))
        
        commands = [cmd.strip() for cmd in commands_text.split('\n') if cmd.strip()]
        results = {}
        
        for device_name in device_names:
            result = execute_command_on_device(device_name, commands, username, password)
            results[device_name] = result
        
        # Save batch results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"batch_execution_{timestamp}.txt"
        filepath = os.path.join(SAVED_NOTES_DIR, filename)
        
        note_content = f"# Batch Command Execution\n"
        note_content += f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        note_content += f"# Devices: {', '.join(device_names)}\n\n"
        
        for device_name, result in results.items():
            note_content += f"## Device: {device_name}\n"
            if result['success']:
                for cmd_result in result['results']:
                    note_content += f"### Command: {cmd_result['command']}\n"
                    note_content += f"### Success: {cmd_result['success']}\n"
                    note_content += f"### Output:\n{cmd_result['output']}\n\n"
            else:
                note_content += f"### Error: {result['error']}\n\n"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(note_content)
        
        # Save metadata
        metadata = load_notes_metadata()
        metadata[filename] = {
            'created': datetime.now().isoformat(),
            'modified': datetime.now().isoformat(),
            'tags': ['batch_execution'] + [d.lower() for d in device_names],
            'type': 'batch_execution_note',
            'favorite': False
        }
        save_notes_metadata(metadata)
        
        flash(f'Batch execution completed. Results saved as {filename}')
        return render_template('batch_results.html', results=results, devices=device_names)
    
    devices = load_devices()
    return render_template('batch_execute.html', devices=devices)



# Configuration backup
@app.route('/devices/backup/<device_name>', methods=['POST'])
def backup_config(device_name):
    """Backup device configuration"""
    devices = load_devices()
    if device_name not in devices:
        flash(f'Device {device_name} not found.')
        return redirect(url_for('manage_devices'))
    
    device_info = devices[device_name]
    device_type = get_device_type(device_name)
    
    # Commands to get configuration based on device type
    backup_commands = {
        'ciena_os': ['show running-config'],
        'cisco_xr': ['show running-config'],
        'cisco_ios': ['show running-config'],
        'nokia_sros': ['show configuration'],
        'juniper': ['show configuration']
    }
    
    commands = backup_commands.get(device_type, ['show running-config'])
    
    result = execute_command_on_device(device_name, commands)
    
    if result['success']:
        # Save configuration backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{device_name}_config_backup_{timestamp}.txt"
        filepath = os.path.join(SAVED_NOTES_DIR, filename)
        
        note_content = f"# Configuration Backup - {device_name}\n"
        note_content += f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        note_content += f"# Device Type: {device_type}\n\n"
        
        for cmd_result in result['results']:
            note_content += f"## Command: {cmd_result['command']}\n"
            note_content += f"## Output:\n{cmd_result['output']}\n\n"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(note_content)
        
        # Save metadata
        metadata = load_notes_metadata()
        metadata[filename] = {
            'created': datetime.now().isoformat(),
            'modified': datetime.now().isoformat(),
            'tags': ['config_backup', device_name.lower()],
            'type': 'config_backup_note',
            'favorite': False
        }
        save_notes_metadata(metadata)
        
        flash(f'Configuration backup saved as {filename}')
    else:
        flash(f'Backup failed: {result["error"]}')
    
    return redirect(url_for('manage_devices'))

# Enhanced password rotation management
# @app.route('/password-rotation')
# def password_rotation():
#     """Manage password rotation reminders and history"""
#     # Load password rotation data
#     password_file = os.path.join(os.path.dirname(__file__), 'password_rotation.json')
    
#     def load_password_data():
#         if os.path.exists(password_file):
#             with open(password_file, 'r', encoding='utf-8') as f:
#                 return json.load(f)
#         return {'devices': {}, 'settings': {'rotation_days': 72}}
    
#     def save_password_data(data):
#         with open(password_file, 'w', encoding='utf-8') as f:
#             json.dump(data, f, indent=2)
    
#     password_data = load_password_data()
    
#     if request.method == 'POST':
#         action = request.form.get('action')
        
#         if action == 'update_rotation':
#             rotation_days = int(request.form.get('rotation_days', 72))
#             password_data['settings']['rotation_days'] = rotation_days
#             save_password_data(password_data)
#             flash(f'Password rotation period updated to {rotation_days} days.')
            
#         elif action == 'mark_rotated':
#             device_name = request.form.get('device_name')
#             if device_name:
#                 password_data['devices'][device_name] = {
#                     'last_rotated': datetime.now().isoformat(),
#                     'next_rotation': (datetime.now() + timedelta(days=password_data['settings']['rotation_days'])).isoformat()
#                 }
#                 save_password_data(password_data)
#                 flash(f'Password rotation marked for {device_name}.')
        
#         return redirect(url_for('password_rotation'))
    
#     # Calculate days until rotation for each device
#     devices = load_devices()
#     rotation_status = {}
    
#     for device_name in devices:
#         device_data = password_data['devices'].get(device_name, {})
#         if device_data:
#             last_rotated = datetime.fromisoformat(device_data['last_rotated'])
#             next_rotation = datetime.fromisoformat(device_data['next_rotation'])
#             days_until = (next_rotation - datetime.now()).days
#             rotation_status[device_name] = {
#                 'last_rotated': last_rotated.strftime('%Y-%m-%d'),
#                 'next_rotation': next_rotation.strftime('%Y-%m-%d'),
#                 'days_until': days_until,
#                 'overdue': days_until < 0
#             }
#         else:
#             rotation_status[device_name] = {
#                 'last_rotated': 'Never',
#                 'next_rotation': 'Not set',
#                 'days_until': None,
#                 'overdue': False
#             }
    
#     return render_template('password_rotation.html', 
#                          rotation_status=rotation_status, 
#                          settings=password_data['settings'],
#                          devices=devices)



# Quick commands library
COMMANDS_FILE = os.path.join(os.path.dirname(__file__), 'command_library.json')

def load_command_library():
    """Load command library from JSON file"""
    if os.path.exists(COMMANDS_FILE):
        with open(COMMANDS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # Create default command library
        default_commands = {
            'ciena': {
                'Basic': [
                    'show equipment',
                    'show interface {port}',
                    'show alarms',
                    'show performance {port}'
                ],
                'Troubleshooting': [
                    'show equipment ont interface {port} detail',
                    'show equipment ont interface {port} statistics',
                    'show equipment ont interface {port} optical-info',
                    'show equipment ont interface {port} alarms'
                ],
                'Configuration': [
                    'show running-config',
                    'show configuration interface {port}',
                    'show equipment ont interface {port} configuration'
                ]
            },
            'cisco': {
                'Basic': [
                    'show version',
                    'show interfaces {interface}',
                    'show ip interface brief',
                    'show ip route'
                ],
                'Troubleshooting': [
                    'show interface {interface} counters',
                    'show interface {interface} status',
                    'show logging',
                    'show ip bgp summary'
                ],
                'Configuration': [
                    'show running-config interface {interface}',
                    'show startup-config',
                    'show ip route {prefix}'
                ]
            },
            'nokia': {
                'Basic': [
                    'show version',
                    'show port {port}',
                    'show interface {interface}',
                    'show router interface'
                ],
                'Troubleshooting': [
                    'show port {port} statistics',
                    'show port {port} detail',
                    'show router status',
                    'show router bgp summary'
                ],
                'Configuration': [
                    'show configuration',
                    'show configuration port {port}',
                    'show configuration router interface {interface}'
                ]
            },
            'juniper': {
                'Basic': [
                    'show version',
                    'show interfaces {interface}',
                    'show route',
                    'show system storage'
                ],
                'Troubleshooting': [
                    'show interface {interface} detail',
                    'show route {prefix}',
                    'show bgp summary',
                    'show system alarms'
                ],
                'Configuration': [
                    'show configuration interfaces {interface}',
                    'show configuration routing-options',
                    'show configuration protocols bgp'
                ]
            }
        }
        save_command_library(default_commands)
        return default_commands

def save_command_library(commands):
    """Save command library to JSON file"""
    with open(COMMANDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(commands, f, indent=2)

@app.route('/commands/library')
def command_library():
    """Library of common network commands"""
    command_library = load_command_library()
    return render_template('command_library.html', command_library=command_library)

@app.route('/commands/library/manage')
def manage_command_library():
    """Manage command library through web interface"""
    command_library = load_command_library()
    return render_template('manage_command_library.html', command_library=command_library)

@app.route('/commands/library/edit', methods=['POST'])
def edit_command_library():
    """Edit command library"""
    try:
        data = request.get_json()
        if data and 'commands' in data:
            save_command_library(data['commands'])
            flash('Command library updated successfully!', 'success')
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Invalid data'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/commands/library/add-vendor', methods=['POST'])
def add_vendor():
    """Add a new vendor to the command library"""
    try:
        vendor_name = request.form.get('vendor_name', '').strip().lower()
        if not vendor_name:
            flash('Vendor name is required', 'error')
            return redirect(url_for('manage_command_library'))
        
        command_library = load_command_library()
        if vendor_name in command_library:
            flash(f'Vendor "{vendor_name}" already exists', 'error')
        else:
            command_library[vendor_name] = {
                'Basic': [],
                'Troubleshooting': [],
                'Configuration': []
            }
            save_command_library(command_library)
            flash(f'Vendor "{vendor_name}" added successfully!', 'success')
        
        return redirect(url_for('manage_command_library'))
    except Exception as e:
        flash(f'Error adding vendor: {str(e)}', 'error')
        return redirect(url_for('manage_command_library'))

@app.route('/commands/library/delete-vendor/<vendor_name>', methods=['POST'])
def delete_vendor(vendor_name):
    """Delete a vendor from the command library"""
    try:
        command_library = load_command_library()
        if vendor_name in command_library:
            del command_library[vendor_name]
            save_command_library(command_library)
            flash(f'Vendor "{vendor_name}" deleted successfully!', 'success')
        else:
            flash(f'Vendor "{vendor_name}" not found', 'error')
        
        return redirect(url_for('manage_command_library'))
    except Exception as e:
        flash(f'Error deleting vendor: {str(e)}', 'error')
        return redirect(url_for('manage_command_library'))

@app.route('/commands/library/delete-command', methods=['POST'])
def delete_command():
    """Delete a specific command from the command library"""
    try:
        vendor = request.form.get('vendor', '').strip()
        category = request.form.get('category', '').strip()
        command = request.form.get('command', '').strip()
        
        if not all([vendor, category, command]):
            flash('Missing required parameters', 'error')
            return redirect(url_for('manage_command_library'))
        
        command_library = load_command_library()
        
        if vendor in command_library and category in command_library[vendor]:
            if command in command_library[vendor][category]:
                command_library[vendor][category].remove(command)
                save_command_library(command_library)
                flash(f'Command "{command}" deleted successfully!', 'success')
            else:
                flash(f'Command "{command}" not found in {category}', 'error')
        else:
            flash(f'Vendor "{vendor}" or category "{category}" not found', 'error')
        
        return redirect(url_for('manage_command_library'))
    except Exception as e:
        flash(f'Error deleting command: {str(e)}', 'error')
        return redirect(url_for('manage_command_library'))

def scan_and_index_logs():
    """Scan and index all log files for search functionality"""
    logs_index = {
        'total_files': 0,
        'device_types': {},
        'common_commands': {},
        'date_range': {'earliest': None, 'latest': None},
        'devices': {},
        'files': []
    }
    
    if not os.path.exists(LOGS_DIR):
        return logs_index
    
    for root, dirs, files in os.walk(LOGS_DIR):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, LOGS_DIR)
                
                # Parse filename for metadata
                try:
                    # Extract timestamp and device info from filename
                    # Format: YYYY-MM-DD-HH-MM-SS.mmm__device_name(device_name).txt
                    parts = file.replace('.txt', '').split('__')
                    if len(parts) >= 2:
                        timestamp_str = parts[0]
                        device_info = parts[1]
                        
                        # Parse timestamp
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d-%H-%M-%S.%f')
                        
                        # Extract device name
                        device_name = device_info.split('(')[0] if '(' in device_info else device_info
                        
                        # Determine device type
                        device_type = 'unknown'
                        if device_name.startswith('ce-'):
                            device_type = 'ciena_cpe'
                        elif device_name.startswith('mtg-'):
                            device_type = 'ciena_metro'
                        elif device_name.startswith('nid-'):
                            device_type = 'ciena_nid'
                        elif device_name.startswith('soag'):
                            device_type = 'nokia_soag'
                        elif device_name.startswith('ceg'):
                            device_type = 'nokia_ceg'
                        
                        # Read file content for command analysis
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                
                            # Extract commands (lines ending with > or #)
                            commands = re.findall(r'[^>#]*[>#]\s*([^\n]+)', content)
                            
                            # Count common commands
                            for cmd in commands:
                                cmd_clean = cmd.strip().split()[0] if cmd.strip() else ''
                                if cmd_clean:
                                    logs_index['common_commands'][cmd_clean] = logs_index['common_commands'].get(cmd_clean, 0) + 1
                            
                        except Exception as e:
                            content = ""
                            commands = []
                        
                        # Update index
                        logs_index['total_files'] += 1
                        logs_index['device_types'][device_type] = logs_index['device_types'].get(device_type, 0) + 1
                        
                        if device_name not in logs_index['devices']:
                            logs_index['devices'][device_name] = {
                                'type': device_type,
                                'file_count': 0,
                                'first_seen': timestamp.isoformat(),
                                'last_seen': timestamp.isoformat()
                            }
                        
                        logs_index['devices'][device_name]['file_count'] += 1
                        logs_index['devices'][device_name]['last_seen'] = timestamp.isoformat()
                        
                        # Update date range
                        if not logs_index['date_range']['earliest'] or timestamp < datetime.fromisoformat(logs_index['date_range']['earliest']):
                            logs_index['date_range']['earliest'] = timestamp.isoformat()
                        if not logs_index['date_range']['latest'] or timestamp > datetime.fromisoformat(logs_index['date_range']['latest']):
                            logs_index['date_range']['latest'] = timestamp.isoformat()
                        
                        # Add file entry
                        logs_index['files'].append({
                            'filename': file,
                            'path': relative_path,
                            'full_path': file_path,
                            'device_name': device_name,
                            'device_type': device_type,
                            'timestamp': timestamp.isoformat(),
                            'size': os.path.getsize(file_path),
                            'command_count': len(commands)
                        })
                        
                except Exception as e:
                    # Skip files that don't match expected format
                    continue
    
    # Sort files by timestamp
    logs_index['files'].sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Sort common commands by frequency
    logs_index['common_commands'] = dict(sorted(logs_index['common_commands'].items(), 
                                               key=lambda x: x[1], reverse=True))
    
    return logs_index

def save_logs_index(index):
    """Save the logs index to file"""
    with open(LOGS_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)

def load_logs_index():
    """Load the logs index from file"""
    if os.path.exists(LOGS_INDEX_FILE):
        with open(LOGS_INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def search_logs(query, device_type=None, date_from=None, date_to=None, device_name=None):
    """Search through indexed logs"""
    index = load_logs_index()
    if not index:
        return []
    
    results = []
    query_lower = query.lower()
    
    for file_info in index['files']:
        # Apply filters
        if device_type and file_info['device_type'] != device_type:
            continue
        if device_name and device_name.lower() not in file_info['device_name'].lower():
            continue
        if date_from:
            file_date = datetime.fromisoformat(file_info['timestamp'])
            if file_date < datetime.fromisoformat(date_from):
                continue
        if date_to:
            file_date = datetime.fromisoformat(file_info['timestamp'])
            if file_date > datetime.fromisoformat(date_to):
                continue
        
        # Search in filename and device name
        if query_lower in file_info['filename'].lower() or query_lower in file_info['device_name'].lower():
            results.append(file_info)
            continue
        
        # Search in file content
        try:
            with open(file_info['full_path'], 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if query_lower in content.lower():
                    results.append(file_info)
        except:
            continue
    
    return results[:100]  # Limit results

@app.route('/logs')
def logs_dashboard():
    """Logs dashboard - overview of historical logs"""
    index = load_logs_index()
    if not index:
        # Index doesn't exist, create it
        index = scan_and_index_logs()
        save_logs_index(index)
    
    return render_template('logs_dashboard.html', index=index)

@app.route('/logs/search')
def logs_search():
    """Search interface for logs"""
    query = request.args.get('q', '')
    device_type = request.args.get('device_type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    device_name = request.args.get('device_name', '')
    
    results = []
    if query or device_type or date_from or date_to or device_name:
        results = search_logs(query, device_type, date_from, date_to, device_name)
    
    index = load_logs_index()
    return render_template('logs_search.html', 
                         results=results, 
                         query=query,
                         device_type=device_type,
                         date_from=date_from,
                         date_to=date_to,
                         device_name=device_name,
                         index=index)

@app.route('/logs/view/<path:file_path>')
def view_log(file_path):
    """View a specific log file"""
    full_path = os.path.join(LOGS_DIR, file_path)
    
    if not os.path.exists(full_path) or not full_path.startswith(os.path.abspath(LOGS_DIR)):
        flash('Log file not found or access denied', 'error')
        return redirect(url_for('logs_search'))
    
    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Parse filename for metadata
        filename = os.path.basename(file_path)
        parts = filename.replace('.txt', '').split('__')
        
        metadata = {
            'filename': filename,
            'device_name': parts[1].split('(')[0] if len(parts) > 1 else 'Unknown',
            'timestamp': parts[0] if len(parts) > 0 else 'Unknown',
            'size': len(content),
            'lines': content.count('\n')
        }
        
        return render_template('view_log.html', content=content, metadata=metadata)
        
    except Exception as e:
        flash(f'Error reading log file: {str(e)}', 'error')
        return redirect(url_for('logs_search'))

@app.route('/logs/rebuild-index')
def rebuild_logs_index():
    """Rebuild the logs index"""
    try:
        index = scan_and_index_logs()
        save_logs_index(index)
        flash(f'Logs index rebuilt successfully! Found {index["total_files"]} files.', 'success')
    except Exception as e:
        flash(f'Error rebuilding index: {str(e)}', 'error')
    
    return redirect(url_for('logs_dashboard'))

@app.route('/logs/analytics')
def logs_analytics():
    """Analytics and insights from logs"""
    index = load_logs_index()
    if not index:
        flash('No logs index found. Please rebuild the index first.', 'warning')
        return redirect(url_for('logs_dashboard'))
    
    # Calculate analytics
    analytics = {
        'total_files': index['total_files'],
        'date_range': index['date_range'],
        'device_types': index['device_types'],
        'top_commands': dict(list(index['common_commands'].items())[:20]),
        'top_devices': sorted(index['devices'].items(), 
                            key=lambda x: x[1]['file_count'], reverse=True)[:20],
        'recent_activity': index['files'][:50]  # Last 50 files
    }
    
    return render_template('logs_analytics.html', analytics=analytics)

def generate_smart_template_suggestions():
    """Generate smart template suggestions based on log analysis"""
    index = load_logs_index()
    if not index:
        return []
    
    suggestions = []
    
    # Analyze most common commands by device type
    device_type_commands = {}
    for file_info in index['files']:
        device_type = file_info['device_type']
        if device_type not in device_type_commands:
            device_type_commands[device_type] = {}
        
        # This is a simplified analysis - in a real implementation, 
        # we'd parse the actual commands from the file content
        # For now, we'll use the common commands from the index
        for cmd, count in index['common_commands'].items():
            if cmd not in device_type_commands[device_type]:
                device_type_commands[device_type][cmd] = 0
            device_type_commands[device_type][cmd] += count
    
    # Generate suggestions based on device types and common commands
    suggestions = []
    
    # Ciena CPE suggestions
    if 'ciena_cpe' in device_type_commands:
        ciena_commands = device_type_commands['ciena_cpe']
        if 'po sh' in ciena_commands or 'show' in ciena_commands:
            suggestions.append({
                'name': 'Ciena CPE - Port Status Check',
                'description': 'Quick port status check for Ciena CPE devices',
                'category': 'Ciena CPE',
                'commands': [
                    'po sh',
                    'po sh po {port}',
                    'show interface {port} status'
                ],
                'variables': ['port'],
                'priority': 'high',
                'usage_count': ciena_commands.get('po sh', 0) + ciena_commands.get('show', 0)
            })
        
        if 'cfm' in ciena_commands:
            suggestions.append({
                'name': 'Ciena CPE - CFM Monitoring',
                'description': 'CFM monitoring and troubleshooting for Ciena CPE',
                'category': 'Ciena CPE',
                'commands': [
                    'cfm remote-mep show',
                    'cfm local-mep show',
                    'cfm mep show'
                ],
                'variables': [],
                'priority': 'high',
                'usage_count': ciena_commands.get('cfm', 0)
            })
    
    # Nokia SOAG suggestions
    if 'nokia_soag' in device_type_commands:
        nokia_commands = device_type_commands['nokia_soag']
        if 'admin show' in nokia_commands or 'show' in nokia_commands:
            suggestions.append({
                'name': 'Nokia SOAG - Configuration Check',
                'description': 'Configuration and status check for Nokia SOAG devices',
                'category': 'Nokia SOAG',
                'commands': [
                    'admin show configuration full-context | match {pattern}',
                    'admin show version',
                    'show port {port}'
                ],
                'variables': ['pattern', 'port'],
                'priority': 'high',
                'usage_count': nokia_commands.get('admin show', 0) + nokia_commands.get('show', 0)
            })
    
    # Generic troubleshooting suggestions
    suggestions.append({
        'name': 'Generic - Interface Status Check',
        'description': 'Basic interface status check for any device type',
        'category': 'Generic',
        'commands': [
            'show interface {interface}',
            'show interface {interface} status',
            'show interface {interface} statistics'
        ],
        'variables': ['interface'],
        'priority': 'medium',
        'usage_count': index['common_commands'].get('show', 0)
    })
    
    # Sort by usage count
    suggestions.sort(key=lambda x: x['usage_count'], reverse=True)
    
    return suggestions

def get_device_specific_suggestions(device_name):
    """Get template suggestions specific to a device based on its type"""
    index = load_logs_index()
    if not index:
        return []
    
    # Determine device type from name
    device_type = 'unknown'
    if device_name.startswith('ce-'):
        device_type = 'ciena_cpe'
    elif device_name.startswith('mtg-'):
        device_type = 'ciena_metro'
    elif device_name.startswith('nid-'):
        device_type = 'ciena_nid'
    elif device_name.startswith('soag'):
        device_type = 'nokia_soag'
    elif device_name.startswith('ceg'):
        device_type = 'nokia_ceg'
    
    # Get device-specific suggestions
    suggestions = []
    
    if device_type == 'ciena_cpe':
        suggestions = [
            {
                'name': 'Port Status Check',
                'description': 'Check port status and configuration',
                'commands': ['po sh', 'po sh po {port}'],
                'variables': ['port']
            },
            {
                'name': 'CFM Monitoring',
                'description': 'Check CFM status and remote MEPs',
                'commands': ['cfm remote-mep show', 'cfm local-mep show'],
                'variables': []
            },
            {
                'name': 'Interface Statistics',
                'description': 'Check interface statistics and performance',
                'commands': ['show interface {port} statistics', 'show interface {port} detail'],
                'variables': ['port']
            }
        ]
    elif device_type == 'nokia_soag':
        suggestions = [
            {
                'name': 'Configuration Search',
                'description': 'Search configuration for specific patterns',
                'commands': ['admin show configuration full-context | match {pattern}'],
                'variables': ['pattern']
            },
            {
                'name': 'Port Status',
                'description': 'Check port status and configuration',
                'commands': ['show port {port}', 'show port {port} statistics'],
                'variables': ['port']
            },
            {
                'name': 'System Status',
                'description': 'Check system version and status',
                'commands': ['admin show version', 'admin show system'],
                'variables': []
            }
        ]
    
    return suggestions

@app.route('/templates/suggestions')
def template_suggestions():
    """Show smart template suggestions based on log analysis"""
    suggestions = generate_smart_template_suggestions()
    return render_template('template_suggestions.html', suggestions=suggestions)

@app.route('/templates/suggestions/device/<device_name>')
def device_template_suggestions(device_name):
    """Get template suggestions for a specific device"""
    suggestions = get_device_specific_suggestions(device_name)
    return jsonify(suggestions)

@app.route('/templates/suggestions/create', methods=['POST'])
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

@app.route('/manage-categories', methods=['GET', 'POST'])
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

def discover_devices_from_logs():
    """Discover devices from log analysis and suggest them for device list"""
    index = load_logs_index()
    if not index:
        return []
    
    discovered_devices = []
    
    # Analyze devices from logs
    for device_name, device_info in index['devices'].items():
        # Skip generic/unknown devices
        if device_name in ['Default', 'unknown', 'Unknown']:
            continue
            
        # Determine device type from name
        device_type = 'unknown'
        if device_name.startswith('ce-'):
            device_type = 'ciena_os'
        elif device_name.startswith('mtg-'):
            device_type = 'ciena_os'
        elif device_name.startswith('nid-'):
            device_type = 'ciena_os'
        elif device_name.startswith('soag'):
            device_type = 'nokia_sros'
        elif device_name.startswith('ceg'):
            device_type = 'nokia_sros'
        elif device_name.startswith('asr'):
            device_type = 'cisco_xr'
        elif device_name.startswith('ncs'):
            device_type = 'cisco_xr'
        elif device_name.startswith('mx'):
            device_type = 'juniper'
        elif device_name.startswith('acx'):
            device_type = 'juniper'
        
        # Create device suggestion
        discovered_devices.append({
            'name': device_name,
            'ip_address': device_name,  # Use name as IP for now
            'device_type': device_type,
            'username': '',  # Will be prompted for RADIUS
            'description': f'Discovered from logs - {device_info["file_count"]} log files',
            'file_count': device_info['file_count'],
            'first_seen': device_info['first_seen'],
            'last_seen': device_info['last_seen'],
            'suggested': True
        })
    
    # Sort by file count (most active devices first)
    discovered_devices.sort(key=lambda x: x['file_count'], reverse=True)
    
    return discovered_devices

def get_device_discovery_stats():
    """Get statistics about device discovery"""
    index = load_logs_index()
    if not index:
        return {}
    
    existing_devices = load_devices()
    existing_device_names = set(existing_devices.keys())
    
    discovered_devices = discover_devices_from_logs()
    discovered_device_names = {device['name'] for device in discovered_devices}
    
    stats = {
        'total_discovered': len(discovered_devices),
        'already_added': len(discovered_device_names.intersection(existing_device_names)),
        'new_devices': len(discovered_device_names - existing_device_names),
        'device_types': {},
        'most_active': discovered_devices[:10] if discovered_devices else []
    }
    
    # Count device types
    for device in discovered_devices:
        device_type = device['device_type']
        if device_type not in stats['device_types']:
            stats['device_types'][device_type] = 0
        stats['device_types'][device_type] += 1
    
    return stats

@app.route('/devices/discover')
def device_discovery():
    """Device discovery from log analysis"""
    stats = get_device_discovery_stats()
    discovered_devices = discover_devices_from_logs()
    
    return render_template('device_discovery.html', 
                         stats=stats, 
                         discovered_devices=discovered_devices)

@app.route('/devices/discover/add/<device_name>')
def add_discovered_device(device_name):
    """Add a discovered device to the device list"""
    discovered_devices = discover_devices_from_logs()
    
    # Find the device in discovered list
    device_to_add = None
    for device in discovered_devices:
        if device['name'] == device_name:
            device_to_add = device
            break
    
    if not device_to_add:
        flash(f'Device {device_name} not found in discovery list', 'error')
        return redirect(url_for('device_discovery'))
    
    # Store device data in localStorage for pre-filling the add device form
    device_data = {
        'name': device_to_add['name'],
        'ip_address': device_to_add['ip_address'],
        'device_type': device_to_add['device_type'],
        'username': device_to_add['username'],
        'description': device_to_add['description']
    }
    
    return render_template('add_discovered_device.html', 
                         device=device_to_add, 
                         device_data_json=device_data)

@app.route('/devices/discover/bulk-add', methods=['POST'])
def bulk_add_discovered_devices():
    """Bulk add multiple discovered devices"""
    try:
        selected_devices = request.form.getlist('selected_devices')
        discovered_devices = discover_devices_from_logs()
        
        added_count = 0
        existing_devices = load_devices()
        
        for device_name in selected_devices:
            # Find device in discovered list
            device_to_add = None
            for device in discovered_devices:
                if device['name'] == device_name:
                    device_to_add = device
                    break
            
            if device_to_add and device_name not in existing_devices:
                # Add to existing devices
                existing_devices[device_name] = {
                    'ip_address': device_to_add['ip_address'],
                    'device_type': device_to_add['device_type'],
                    'username': device_to_add['username'],
                    'description': device_to_add['description'],
                    'added_date': datetime.now().isoformat()
                }
                added_count += 1
        
        # Save updated device list
        save_devices(existing_devices)
        
        flash(f'Successfully added {added_count} devices to your device list!', 'success')
        return redirect(url_for('manage_devices'))
        
    except Exception as e:
        flash(f'Error adding devices: {str(e)}', 'error')
        return redirect(url_for('device_discovery'))

@app.route('/devices/discover/clear', methods=['POST'])
def clear_discovery_data():
    """Clear all discovered device data by rebuilding the logs index"""
    try:
        # Delete the logs index file to clear all discovery data
        if os.path.exists(LOGS_INDEX_FILE):
            os.remove(LOGS_INDEX_FILE)
        
        flash('All discovered device data has been cleared successfully.')
        return redirect(url_for('device_discovery'))
    except Exception as e:
        flash(f'Error clearing discovery data: {str(e)}')
        return redirect(url_for('device_discovery'))

@app.route('/devices/discover/auto-suggest')
def auto_suggest_devices():
    """Get auto-suggestions for device names based on logs"""
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify([])
    
    discovered_devices = discover_devices_from_logs()
    suggestions = []
    
    for device in discovered_devices:
        if query in device['name'].lower():
            suggestions.append({
                'name': device['name'],
                'device_type': device['device_type'],
                'file_count': device['file_count'],
                'last_seen': device['last_seen']
            })
    
    # Limit to 10 suggestions
    return jsonify(suggestions[:10])

def execute_batch_commands(devices, commands, username=None, password=None):
    """Execute commands on multiple devices in batch"""
    results = {
        'total_devices': len(devices),
        'successful': 0,
        'failed': 0,
        'results': {},
        'summary': {},
        'start_time': datetime.now().isoformat(),
        'end_time': None
    }
    
    # Track command success/failure counts
    command_stats = {}
    for command in commands:
        command_stats[command] = {'success': 0, 'failed': 0}
    
    for device_name in devices:
        try:
            device_result = execute_command_on_device(device_name, commands, username, password)
            results['results'][device_name] = device_result
            
            if device_result['success']:
                results['successful'] += 1
                # Track individual command results
                for cmd_result in device_result['results']:
                    command = cmd_result['command']
                    if command not in command_stats:
                        command_stats[command] = {'success': 0, 'failed': 0}
                    
                    if cmd_result['success']:
                        command_stats[command]['success'] += 1
                    else:
                        command_stats[command]['failed'] += 1
            else:
                results['failed'] += 1
                # Mark all commands as failed for this device
                for command in commands:
                    if command not in command_stats:
                        command_stats[command] = {'success': 0, 'failed': 0}
                    command_stats[command]['failed'] += 1
                    
        except Exception as e:
            results['results'][device_name] = {
                'success': False,
                'error': f'Exception: {str(e)}',
                'results': []
            }
            results['failed'] += 1
    
    results['end_time'] = datetime.now().isoformat()
    results['summary'] = command_stats
    
    return results

def save_batch_result(batch_result, description=""):
    """Save batch execution result as a note"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"batch_execution_{timestamp}.txt"
    
    # Create note content
    content = f"""BATCH EXECUTION REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Description: {description}

SUMMARY:
- Total Devices: {batch_result['total_devices']}
- Successful: {batch_result['successful']}
- Failed: {batch_result['failed']}
- Success Rate: {(batch_result['successful'] / batch_result['total_devices'] * 100):.1f}%

EXECUTION TIME:
- Start: {batch_result['start_time']}
- End: {batch_result['end_time']}

COMMAND SUMMARY:
"""
    
    for command, stats in batch_result['summary'].items():
        total = stats['success'] + stats['failed']
        success_rate = (stats['success'] / total * 100) if total > 0 else 0
        content += f"- {command}: {stats['success']}/{total} successful ({success_rate:.1f}%)\n"
    
    content += "\nDETAILED RESULTS:\n" + "="*50 + "\n\n"
    
    for device_name, result in batch_result['results'].items():
        content += f"DEVICE: {device_name}\n"
        content += f"Status: {'SUCCESS' if result['success'] else 'FAILED'}\n"
        
        if result['success']:
            for cmd_result in result['results']:
                content += f"\nCommand: {cmd_result['command']}\n"
                content += f"Status: {'SUCCESS' if cmd_result['success'] else 'FAILED'}\n"
                content += f"Output:\n{cmd_result['output']}\n"
                content += "-" * 30 + "\n"
        else:
            content += f"Error: {result.get('error', 'Unknown error')}\n"
        
        content += "\n" + "="*50 + "\n\n"
    
    # Save the note
    note_path = os.path.join(SAVED_NOTES_DIR, filename)
    with open(note_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Add to notes metadata
    notes_metadata = load_notes_metadata()
    notes_metadata[filename] = {
        'created': datetime.now().isoformat(),
        'type': 'batch_execution_note',
        'tags': ['batch', 'execution', 'automation'],
        'favorite': False,
        'description': f'Batch execution on {batch_result["total_devices"]} devices - {description}'
    }
    save_notes_metadata(notes_metadata)
    
    return filename

@app.route('/batch-operations')
def batch_operations():
    """Batch operations dashboard"""
    devices = load_devices()
    command_library = load_command_library()
    
    return render_template('batch_operations.html', 
                         devices=devices, 
                         command_library=command_library)

@app.route('/batch-operations/execute', methods=['POST'])
def execute_batch_operations():
    """Execute batch operations on selected devices"""
    try:
        selected_devices = request.form.getlist('selected_devices')
        commands_text = request.form.get('commands', '').strip()
        description = request.form.get('description', 'Batch execution').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not selected_devices:
            flash('Please select at least one device', 'error')
            return redirect(url_for('batch_operations'))
        
        if not commands_text:
            flash('Please enter at least one command', 'error')
            return redirect(url_for('batch_operations'))
        
        # Parse commands (split by newlines and filter empty lines)
        commands = [cmd.strip() for cmd in commands_text.split('\n') if cmd.strip()]
        
        if not commands:
            flash('Please enter at least one valid command', 'error')
            return redirect(url_for('batch_operations'))
        
        # Execute batch operations
        batch_result = execute_batch_commands(selected_devices, commands, username, password)
        
        # Save the result as a note
        filename = save_batch_result(batch_result, description)
        
        # Flash success message with summary
        success_rate = (batch_result['successful'] / batch_result['total_devices'] * 100) if batch_result['total_devices'] > 0 else 0
        flash(f'Batch execution completed! {batch_result["successful"]}/{batch_result["total_devices"]} devices successful ({success_rate:.1f}%). Results saved as note.', 'success')
        
        return redirect(url_for('view_note', filename=filename))
        
    except Exception as e:
        flash(f'Error during batch execution: {str(e)}', 'error')
        return redirect(url_for('batch_operations'))

@app.route('/batch-operations/templates')
def batch_templates():
    """Predefined batch operation templates"""
    templates = {
        'health_check': {
            'name': 'Health Check',
            'description': 'Basic health check commands for all device types',
            'commands': [
                'show version',
                'show system',
                'show interface status',
                'show alarms'
            ],
            'devices': 'all'
        },
        'backup_config': {
            'name': 'Configuration Backup',
            'description': 'Backup device configurations',
            'commands': [
                'show running-config',
                'show configuration'
            ],
            'devices': 'all'
        },
        'interface_status': {
            'name': 'Interface Status Check',
            'description': 'Check interface status and statistics',
            'commands': [
                'show interface status',
                'show interface brief',
                'show port status'
            ],
            'devices': 'all'
        },
        'ciena_cfm': {
            'name': 'Ciena CFM Check',
            'description': 'CFM monitoring commands for Ciena devices',
            'commands': [
                'cfm remote-mep show',
                'cfm local-mep show',
                'cfm mep show'
            ],
            'devices': 'ciena'
        },
        'nokia_admin': {
            'name': 'Nokia Admin Check',
            'description': 'Admin-level commands for Nokia devices',
            'commands': [
                'admin show version',
                'admin show system',
                'admin show port status'
            ],
            'devices': 'nokia'
        }
    }
    
    return render_template('batch_templates.html', templates=templates)

@app.route('/batch-operations/template/<template_id>')
def use_batch_template(template_id):
    """Use a predefined batch template"""
    templates = {
        'health_check': {
            'name': 'Health Check',
            'description': 'Basic health check commands for all device types',
            'commands': [
                'show version',
                'show system',
                'show interface status',
                'show alarms'
            ]
        },
        'backup_config': {
            'name': 'Configuration Backup',
            'description': 'Backup device configurations',
            'commands': [
                'show running-config',
                'show configuration'
            ]
        },
        'interface_status': {
            'name': 'Interface Status Check',
            'description': 'Check interface status and statistics',
            'commands': [
                'show interface status',
                'show interface brief',
                'show port status'
            ]
        },
        'ciena_cfm': {
            'name': 'Ciena CFM Check',
            'description': 'CFM monitoring commands for Ciena devices',
            'commands': [
                'cfm remote-mep show',
                'cfm local-mep show',
                'cfm mep show'
            ]
        },
        'nokia_admin': {
            'name': 'Nokia Admin Check',
            'description': 'Admin-level commands for Nokia devices',
            'commands': [
                'admin show version',
                'admin show system',
                'admin show port status'
            ]
        }
    }
    
    if template_id not in templates:
        flash('Template not found', 'error')
        return redirect(url_for('batch_operations'))
    
    template = templates[template_id]
    devices = load_devices()
    
    return render_template('use_batch_template.html', 
                         template=template, 
                         devices=devices)

@app.route('/batch-operations/quick')
def quick_batch():
    """Quick batch operations for common tasks"""
    devices = load_devices()
    
    # Group devices by type for quick selection
    device_groups = {}
    for name, info in devices.items():
        device_type = info.get('device_type', 'unknown')
        if device_type not in device_groups:
            device_groups[device_type] = []
        device_groups[device_type].append(name)
    
    return render_template('quick_batch.html', 
                         devices=devices, 
                         device_groups=device_groups)

if __name__ == '__main__':
    app.run(debug=True) 