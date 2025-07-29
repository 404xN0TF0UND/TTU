# Create a virtual environment named 'venv'
python -m venv venv

# Activate the virtual environment
.\venv\Scripts\activate

# Upgrade pip (optional but recommended)
python -m pip install --upgrade pip

# Install dependencies from requirements.txt
pip install -r requirements.txt

# Print success message
Write-Host "Virtual environment created and dependencies installed. Ready to run the app!"