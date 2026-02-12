import os
import sys
import subprocess
import platform

PROJECT_NAME = "PHMS - Personal Health Management System"
VENV_DIR = "venv"
REQUIREMENTS_FILE = "requirements.txt"
APP_FILE = "app.py"


def run_command(command, shell=False):
    try:
        subprocess.check_call(command, shell=shell)
    except subprocess.CalledProcessError:
        print("❌ Command failed:", command)
        sys.exit(1)


def check_python_version():
    print("🔍 Checking Python version...")
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]} detected")


def create_venv():
    if not os.path.exists(VENV_DIR):
        print("📦 Creating virtual environment...")
        run_command([sys.executable, "-m", "venv", VENV_DIR])
        print("✅ Virtual environment created")
    else:
        print("✅ Virtual environment already exists")


def get_venv_python():
    if platform.system() == "Windows":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        return os.path.join(VENV_DIR, "bin", "python")


def install_dependencies(venv_python):
    print("📥 Installing dependencies...")
    run_command([venv_python, "-m", "pip", "install", "--upgrade", "pip"])
    run_command([venv_python, "-m", "pip", "install", "-r", REQUIREMENTS_FILE])
    print("✅ Dependencies installed")


def run_app(venv_python):
    print("\n🚀 Starting PHMS Application...\n")
    run_command([venv_python, APP_FILE])


def main():
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
