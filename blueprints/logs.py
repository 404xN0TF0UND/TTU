"""logs blueprint - routes extracted verbatim from app.py (mechanical split, no behavior change)."""
from flask import Blueprint
from core import *  # shared app, helpers, constants, flask names

logs_bp = Blueprint('logs', __name__)


@logs_bp.route('/logs')
def logs_dashboard():
    """Logs dashboard - overview of historical logs"""
    index = load_logs_index()
    if not index:
        # Index doesn't exist, create it
        index = scan_and_index_logs()
        save_logs_index(index)
    
    return render_template('logs_dashboard.html', index=index)


@logs_bp.route('/logs/search')
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


@logs_bp.route('/logs/view/<path:file_path>')
def view_log(file_path):
    """View a specific log file"""
    full_path = os.path.join(LOGS_DIR, file_path)
    
    if not os.path.exists(full_path) or not full_path.startswith(os.path.abspath(LOGS_DIR)):
        flash('Log file not found or access denied', 'error')
        return redirect(url_for('logs.logs_search'))
    
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
        return redirect(url_for('logs.logs_search'))


@logs_bp.route('/logs/rebuild-index')
def rebuild_logs_index():
    """Rebuild the logs index"""
    try:
        index = scan_and_index_logs()
        save_logs_index(index)
        flash(f'Logs index rebuilt successfully! Found {index["total_files"]} files.', 'success')
    except Exception as e:
        flash(f'Error rebuilding index: {str(e)}', 'error')
    
    return redirect(url_for('logs.logs_dashboard'))


@logs_bp.route('/logs/analytics')
def logs_analytics():
    """Analytics and insights from logs"""
    index = load_logs_index()
    if not index:
        flash('No logs index found. Please rebuild the index first.', 'warning')
        return redirect(url_for('logs.logs_dashboard'))
    
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


@logs_bp.route('/logs/config', methods=['GET', 'POST'])
def logs_config():
    """Manage logs configuration including external folders"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_folder':
            folder_path = request.form.get('folder_path', '').strip()
            folder_name = request.form.get('folder_name', '').strip()
            
            if not folder_path or not folder_name:
                flash('Both folder path and name are required', 'error')
                return redirect(url_for('logs.logs_config'))
            
            if not os.path.exists(folder_path):
                flash('Folder path does not exist', 'error')
                return redirect(url_for('logs.logs_config'))
            
            config = load_logs_config()
            
            # Check if folder already exists
            for folder in config['external_folders']:
                if folder['path'] == folder_path:
                    flash('Folder already exists in configuration', 'error')
                    return redirect(url_for('logs.logs_config'))
            
            config['external_folders'].append({
                'name': folder_name,
                'path': folder_path,
                'enabled': True
            })
            
            save_logs_config(config)
            flash(f'External folder "{folder_name}" added successfully!', 'success')
            
        elif action == 'remove_folder':
            folder_path = request.form.get('folder_path', '').strip()
            
            config = load_logs_config()
            config['external_folders'] = [f for f in config['external_folders'] if f['path'] != folder_path]
            save_logs_config(config)
            
            flash('External folder removed successfully!', 'success')
            
        elif action == 'toggle_monitoring':
            config = load_logs_config()
            config['monitoring_enabled'] = not config.get('monitoring_enabled', False)
            save_logs_config(config)
            
            status = 'enabled' if config['monitoring_enabled'] else 'disabled'
            flash(f'Folder monitoring {status}!', 'success')
            
        elif action == 'rebuild_index':
            try:
                index = scan_and_index_logs()
                save_logs_index(index)
                flash(f'Logs index rebuilt successfully! Found {index["total_files"]} files.', 'success')
            except Exception as e:
                flash(f'Error rebuilding index: {str(e)}', 'error')
    
    config = load_logs_config()
    for folder in config.get('external_folders', []):
        folder['exists'] = os.path.exists(folder.get('path', ''))
    return render_template('logs_config.html', config=config)


@logs_bp.route('/logs/check-new')
def check_new_logs():
    """Manually check for new log files in external folders"""
    try:
        if check_for_new_logs():
            flash('New log files detected and index updated!', 'success')
        else:
            flash('No new log files found.', 'info')
    except Exception as e:
        flash(f'Error checking for new logs: {str(e)}', 'error')
    
    return redirect(url_for('logs.logs_config'))


@logs_bp.route('/logs/check-new-ajax')
def check_new_logs_ajax():
    """AJAX endpoint to check for new logs without page redirect"""
    try:
        if check_for_new_logs():
            return {'success': True, 'message': 'New log files detected and index updated!'}
        else:
            return {'success': True, 'message': 'No new log files found.'}
    except Exception as e:
        return {'success': False, 'message': f'Error checking for new logs: {str(e)}'}
