"""PHMS Application Startup Script.

Automated setup and launcher for the Personal Health Monitoring System (PHMS).
This script handles the complete application bootstrap process including:
- Python version validation (requires Python 3.8+)
- Virtual environment creation
- Dependency installation from requirements.txt
- Application launch

Usage:
    python start.py

Requirements:
    - Python 3.8 or higher
    - pip (Python package installer)
    - requirements.txt in the same directory
    - app.py (main Flask application file)

Features:
    - Automatic virtual environment setup
    - Cross-platform compatibility (Windows, Linux, macOS)
    - Dependency version management
    - Error handling with informative messages
    - Progress indicators for each setup step

Directory Structure:
    PHMS/
    ├── start.py (this file)
    ├── app.py (Flask application)
    ├── requirements.txt (Python dependencies)
    └── venv/ (created automatically)

Note:
    - Virtual environment is created only if it doesn't exist
    - Dependencies are reinstalled on each run to ensure updates
    - Script exits with status code 1 on any errors
"""

import os
import sys
import subprocess
import platform

PROJECT_NAME = "PHMS - Personal Health Management System"
VENV_DIR = "venv"
REQUIREMENTS_FILE = "requirements.txt"
APP_FILE = "app.py"


def run_command(command, shell=False):
    """Execute a shell command and handle errors.
    
    Runs a subprocess command and exits the script if the command fails.
    Provides error feedback with the failed command for debugging.
    
    Args:
        command (list | str): Command to execute
            - list: Command with arguments (e.g., ['python', '-m', 'pip', 'install', 'flask'])
            - str: Shell command (only when shell=True)
        shell (bool, optional): Whether to execute command through shell (default: False)
    
    Raises:
        SystemExit: Exits with code 1 if command fails
    
    Example:
        >>> run_command(['pip', 'install', 'flask'])
        >>> run_command('echo "Hello World"', shell=True)
    
    Note:
        - Uses subprocess.check_call for execution
        - Prints error message with ❌ emoji on failure
        - Automatically terminates script on command failure
    """
    try:
        subprocess.check_call(command, shell=shell)
    except subprocess.CalledProcessError:
        print("❌ Command failed:", command)
        sys.exit(1)


def check_python_version():
    """Validate Python version meets minimum requirements.
    
    Checks if the current Python interpreter is version 3.8 or higher.
    This is required for modern Flask features and type hints.
    
    Requirements:
        - Python >= 3.8.0
    
    Raises:
        SystemExit: Exits with code 1 if Python version is below 3.8
    
    Example:
        >>> check_python_version()
        🔍 Checking Python version...
        ✅ Python 3.11.0 detected
    
    Note:
        - Uses sys.version_info for accurate version checking
        - Displays detected version on success
        - Critical check that must pass before proceeding
    """
    print("🔍 Checking Python version...")
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]} detected")


def create_venv():
    """Create Python virtual environment if it doesn't exist.
    
    Checks for existing virtual environment in venv/ directory and creates
    one if not found. Uses the current Python interpreter to create the venv.
    
    Directory Created:
        venv/
        ├── Scripts/ (Windows) or bin/ (Unix)
        ├── Lib/ (Windows) or lib/ (Unix)
        ├── Include/
        └── pyvenv.cfg
    
    Behavior:
        - Skips creation if venv/ directory already exists
        - Creates new isolated Python environment
        - Uses same Python version as current interpreter
    
    Example:
        >>> create_venv()
        📦 Creating virtual environment...
        ✅ Virtual environment created
    
    Note:
        - Virtual environment isolates project dependencies
        - Prevents conflicts with system Python packages
        - Uses Python's built-in venv module
        - Idempotent operation (safe to call multiple times)
    """
    if not os.path.exists(VENV_DIR):
        print("📦 Creating virtual environment...")
        run_command([sys.executable, "-m", "venv", VENV_DIR])
        print("✅ Virtual environment created")
    else:
        print("✅ Virtual environment already exists")


def get_venv_python():
    """Get the path to the virtual environment Python interpreter.
    
    Returns the platform-specific path to the Python executable inside
    the virtual environment directory.
    
    Platform Paths:
        - Windows: venv/Scripts/python.exe
        - Unix/Linux/macOS: venv/bin/python
    
    Returns:
        str: Absolute or relative path to virtual environment Python executable
    
    Example:
        >>> get_venv_python()
        'venv\\Scripts\\python.exe'  # On Windows
        'venv/bin/python'  # On Unix/Linux/macOS
    
    Note:
        - Path returned may not exist if venv not created yet
        - Use os.path.exists() to verify before using
        - Cross-platform compatible using platform.system()
    """
    if platform.system() == "Windows":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        return os.path.join(VENV_DIR, "bin", "python")


def install_dependencies(venv_python):
    """Install Python package dependencies from requirements.txt.
    
    Upgrades pip to the latest version and installs all packages listed
    in requirements.txt using the virtual environment's Python interpreter.
    
    Args:
        venv_python (str): Path to the virtual environment Python executable
    
    Installation Steps:
        1. Upgrade pip to latest version (ensures compatibility)
        2. Install all packages from requirements.txt
    
    Dependencies Installed (from requirements.txt):
        - Flask: Web framework
        - Flask-SQLAlchemy: Database ORM
        - Flask-Login: Authentication
        - Flask-Mail: Email service
        - APScheduler: Task scheduling
        - pandas, scikit-learn: ML/data analysis
        - And others as specified in requirements.txt
    
    Example:
        >>> venv_python = get_venv_python()
        >>> install_dependencies(venv_python)
        📥 Installing dependencies...
        ✅ Dependencies installed
    
    Note:
        - Runs every time script executes (ensures updates)
        - Uses --upgrade flag for pip
        - May take several minutes on first run
        - Requires internet connection for package download
    """
    print("📥 Installing dependencies...")
    run_command([venv_python, "-m", "pip", "install", "--upgrade", "pip"])
    run_command([venv_python, "-m", "pip", "install", "-r", REQUIREMENTS_FILE])
    print("✅ Dependencies installed")


def run_app(venv_python):
    """Launch the PHMS Flask application.
    
    Starts the Flask development server using the virtual environment's
    Python interpreter. This is a blocking call that runs until server stops.
    
    Args:
        venv_python (str): Path to the virtual environment Python executable
    
    Server Configuration:
        - Default host: 127.0.0.1 (localhost)
        - Default port: 5000
        - Debug mode: Controlled by FLASK_DEBUG environment variable
        - Auto-reload: Enabled in debug mode
    
    Example:
        >>> venv_python = get_venv_python()
        >>> run_app(venv_python)
        🚀 Starting PHMS Application...
        
        * Running on http://127.0.0.1:5000
        * Restarting with stat
    
    Note:
        - This is a blocking call (doesn't return until app stops)
        - Press Ctrl+C to stop the server
        - Server configuration defined in app.py
        - Database migrations are not executed by start.py
        - Apply migrations manually with: flask db upgrade
        - Scheduler starts automatically
    """
    print("\n🚀 Starting PHMS Application...\n")
    run_command([venv_python, APP_FILE])


def main():
    """Main entry point for the PHMS startup script.
    
    Orchestrates the complete application setup and launch sequence:
    1. Display welcome banner
    2. Validate Python version (>= 3.8)
    3. Create virtual environment (if needed)
    4. Verify virtual environment Python executable exists
    5. Install/update dependencies from requirements.txt
    6. Launch Flask application server
    
    Exit Codes:
        0: Successful execution (not reached as app runs indefinitely)
        1: Error occurred (Python version, venv creation, dependencies, etc.)
    
    Workflow:
        ┌─────────────────────────────┐
        │   Display Project Banner    │
        └──────────────┬──────────────┘
                       ↓
        ┌─────────────────────────────┐
        │  Check Python Version       │
        │  (Must be >= 3.8)           │
        └──────────────┬──────────────┘
                       ↓
        ┌─────────────────────────────┐
        │  Create Virtual Environment │
        │  (Skip if exists)           │
        └──────────────┬──────────────┘
                       ↓
        ┌─────────────────────────────┐
        │  Verify venv Python         │
        │  (Must exist)               │
        └──────────────┬──────────────┘
                       ↓
        ┌─────────────────────────────┐
        │  Install Dependencies       │
        │  (pip + requirements.txt)   │
        └──────────────┬──────────────┘
                       ↓
        ┌─────────────────────────────┐
        │  Launch Flask Application   │
        │  (Blocking - runs forever)  │
        └─────────────────────────────┘
    
    Example:
        $ python start.py
        ======================================================================
         PHMS - Personal Health Management System
        ======================================================================
        🔍 Checking Python version...
        ✅ Python 3.11.0 detected
        ✅ Virtual environment already exists
        📥 Installing dependencies...
        ✅ Dependencies installed
        🚀 Starting PHMS Application...
    
    Note:
        - Designed to be run from command line
        - All errors result in script termination with exit code 1
        - Application runs until manually stopped (Ctrl+C)
        - Progress indicators show each step status
    """
    print("=" * 70)
    print(f" {PROJECT_NAME}")
    print("=" * 70)

    check_python_version()
    create_venv()

    venv_python = get_venv_python()

    if not os.path.exists(venv_python):
        print("❌ Virtual environment python not found")
        sys.exit(1)

    install_dependencies(venv_python)
    run_app(venv_python)


if __name__ == "__main__":
    main()
