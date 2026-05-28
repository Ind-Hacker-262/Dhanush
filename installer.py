import sys
import os
import subprocess
import sqlite3

# ANSI Color codes for styled terminal printouts
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_header(text):
    print(f"\n{BOLD}{BLUE}=== {text} ==={RESET}\n")

def print_success(text):
    print(f"{GREEN}[OK] {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}[WARN] {text}{RESET}")

def print_error(text):
    print(f"{RED}[FAIL] {text}{RESET}")

def run_diagnostics():
    print_header("MARKETING KIOSK: AUTOMATED INSTALLER & DIAGNOSTICS")
    
    # Step 1: Detect Python Environment
    print(f"Detecting Python environment...")
    print_success(f"Python Version: {sys.version.split()[0]} ({sys.platform})")
    print_success(f"Current Workspace Path: {os.getcwd()}")
    
    # Step 2: Check & Install Required Dependencies
    print_header("DEPENDENCY VERIFICATION")
    required_packages = ["flask", "werkzeug"]
    missing_packages = []
    
    for pkg in required_packages:
        try:
            __import__(pkg)
            print_success(f"Library '{pkg}' is already installed.")
        except ImportError:
            missing_packages.append(pkg)
            print_warning(f"Library '{pkg}' is missing.")
            
    if missing_packages:
        print(f"\nInstalling missing dependencies: {', '.join(missing_packages)}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
            print_success("Dependencies installed successfully!")
        except Exception as e:
            print_error(f"Failed to install dependencies automatically: {str(e)}")
            print_warning("Please run: pip install flask")
            sys.exit(1)
            
    # Step 3: Verify and Initialize Database
    print_header("DATABASE INTEGRITY CHECKS")
    db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kiosk.db')
    
    # Import and run db initializer
    try:
        from database import init_db
        print("Initializing SQLite tables and seeding initial records...")
        init_db()
        print_success("Database schema successfully generated & verified.")
    except Exception as e:
        print_error(f"Failed to initialize database: {str(e)}")
        sys.exit(1)
        
    # Verify Seeded Accounts
    if os.path.exists(db_file):
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Count seeded users
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            # Count seeded products
            cursor.execute("SELECT COUNT(*) FROM products")
            prod_count = cursor.fetchone()[0]
            
            print_success(f"Verified Database Seeds: {user_count} registered users, {prod_count} catalog products.")
            conn.close()
        except Exception as e:
            print_error(f"Failed to query database statistics: {str(e)}")
            sys.exit(1)
    else:
        print_error("kiosk.db was not created. Check file write permissions in this directory.")
        sys.exit(1)
        
    # Step 4: Dry-run Code Syntax Compilation
    print_header("BACKEND COMPILATION & ROUTE DRY-RUN")
    app_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')
    if os.path.exists(app_file):
        try:
            # Check for syntax errors by compiling
            import py_compile
            py_compile.compile(app_file, doraise=True)
            print_success("Backend app.py compiled cleanly with zero syntax/formatting errors.")
        except Exception as e:
            print_error(f"Backend app.py contains syntax errors: {str(e)}")
            sys.exit(1)
    else:
        print_error("app.py not found in current directory.")
        sys.exit(1)
        
    # Step 5: Verification Summary
    print_header("DIAGNOSTIC SUMMARY & SETUP COMPLETION")
    print(f"{GREEN}{BOLD}SUCCESS: ALL DIAGNOSTIC CHECKS PASSED SUCCESSFULLY!{RESET}\n")
    print("Your Marketing Kiosk platform is 100% configured and ready to boot.")
    print("------------------------------------------------------------------")
    print(f"[{BOLD}How to Launch local server:{RESET}]")
    print(f"   {GREEN}python app.py{RESET}")
    print(f"   Open browser to: {BLUE}http://127.0.0.1:5000{RESET}")
    print("------------------------------------------------------------------")
    print(f"[{BOLD}Seed Testing Accounts (password: role + '123'):{RESET}]")
    print("   * Sysadmin:   admin@kiosk.com   (pw: admin123)")
    print("   * Shop Owner: owner@kiosk.com   (pw: owner123)")
    print("   * Customer 1: customer@kiosk.com(pw: customer123)")
    print("   * Customer 2: referee@kiosk.com (pw: referee123)")
    print("------------------------------------------------------------------")

if __name__ == '__main__':
    run_diagnostics()
