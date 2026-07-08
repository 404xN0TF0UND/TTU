"""automation blueprint - routes extracted verbatim from app.py (mechanical split, no behavior change)."""
from flask import Blueprint
from core import *  # shared app, helpers, constants, flask names

automation_bp = Blueprint('automation', __name__)


@automation_bp.route('/execute', methods=['GET', 'POST'])
def execute_commands():
    if request.method == 'POST':
        device_name = request.form.get('device_name', '').strip()
        commands_text = request.form.get('commands', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not device_name or not commands_text:
            flash('Device name and commands are required.')
            return redirect(url_for('automation.execute_commands'))
        
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
            return redirect(url_for('automation.execute_commands'))
    
    devices = load_devices()
    return render_template('execute_commands.html', devices=devices)


@automation_bp.route('/execute/template/<template_id>')
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
        return redirect(url_for('automation.execute_commands'))
    
    template = templates[template_id]
    devices = load_devices()
    
    return render_template('execute_template.html', template=template, devices=devices, template_id=template_id)


@automation_bp.route('/execute/template/<template_id>/run', methods=['POST'])
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


@automation_bp.route('/execute/batch', methods=['GET', 'POST'])
def batch_execute():
    """Execute the same commands on multiple devices"""
    if request.method == 'POST':
        device_names = request.form.getlist('devices')
        commands_text = request.form.get('commands', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not device_names or not commands_text:
            flash('Please select devices and enter commands.')
            return redirect(url_for('automation.batch_execute'))
        
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


@automation_bp.route('/batch-operations')
def batch_operations():
    """Batch operations dashboard"""
    devices = load_devices()
    command_library = load_command_library()
    
    return render_template('batch_operations.html', 
                         devices=devices, 
                         command_library=command_library)


@automation_bp.route('/batch-operations/execute', methods=['POST'])
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
            return redirect(url_for('automation.batch_operations'))
        
        if not commands_text:
            flash('Please enter at least one command', 'error')
            return redirect(url_for('automation.batch_operations'))
        
        # Parse commands (split by newlines and filter empty lines)
        commands = [cmd.strip() for cmd in commands_text.split('\n') if cmd.strip()]
        
        if not commands:
            flash('Please enter at least one valid command', 'error')
            return redirect(url_for('automation.batch_operations'))
        
        # Execute batch operations
        batch_result = execute_batch_commands(selected_devices, commands, username, password)
        
        # Save the result as a note
        filename = save_batch_result(batch_result, description)
        
        # Flash success message with summary
        success_rate = (batch_result['successful'] / batch_result['total_devices'] * 100) if batch_result['total_devices'] > 0 else 0
        flash(f'Batch execution completed! {batch_result["successful"]}/{batch_result["total_devices"]} devices successful ({success_rate:.1f}%). Results saved as note.', 'success')
        
        return redirect(url_for('notes.view_note', filename=filename))
        
    except Exception as e:
        flash(f'Error during batch execution: {str(e)}', 'error')
        return redirect(url_for('automation.batch_operations'))


@automation_bp.route('/batch-operations/templates')
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


@automation_bp.route('/batch-operations/template/<template_id>')
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
        return redirect(url_for('automation.batch_operations'))
    
    template = templates[template_id]
    devices = load_devices()
    
    return render_template('use_batch_template.html', 
                         template=template, 
                         devices=devices)


@automation_bp.route('/batch-operations/quick')
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
