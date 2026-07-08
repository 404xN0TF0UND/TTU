"""main blueprint - routes extracted verbatim from app.py (mechanical split, no behavior change)."""
from flask import Blueprint
from core import *  # shared app, helpers, constants, flask names

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def home():
    # Fix existing notes metadata to include type field
    fix_notes_metadata()
    
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
                   if isinstance(meta, dict) and meta.get('type') == 'quick_note']
    
    # Get current date for display
    current_date = datetime.now().strftime('%B %d, %Y')
    
    return render_template('home.html', 
                         templates_by_category=templates_by_category,
                         devices=devices,
                         notes=notes,
                         quick_notes=quick_notes,
                         current_date=current_date)
