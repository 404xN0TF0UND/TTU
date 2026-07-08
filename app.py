"""TTU Notes entry point.

The former 4,300-line app.py is split mechanically:
- core.py: Flask app object, config, all shared helpers
- blueprints/: route modules with identical URLs and behavior
"""
from core import app

from blueprints.automation import automation_bp
from blueprints.devices import devices_bp
from blueprints.library import library_bp
from blueprints.logs import logs_bp
from blueprints.main import main_bp
from blueprints.notes import notes_bp
from blueprints.tools import tools_bp

app.register_blueprint(automation_bp)
app.register_blueprint(devices_bp)
app.register_blueprint(library_bp)
app.register_blueprint(logs_bp)
app.register_blueprint(main_bp)
app.register_blueprint(notes_bp)
app.register_blueprint(tools_bp)


if __name__ == '__main__':
    app.run(debug=True) 