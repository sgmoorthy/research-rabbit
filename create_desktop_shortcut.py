import os
import sys
import subprocess

def get_desktop_path():
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, 
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        )
        path, _ = winreg.QueryValueEx(key, "Desktop")
        # Expand environment variables like %USERPROFILE%
        return os.path.expandvars(path)
    except Exception:
        # Fallback to standard path
        return os.path.join(os.path.expanduser('~'), 'Desktop')

def create_shortcut():
    print("Creating Windows Desktop Shortcut for Research Rabbit...")
    
    # 1. Determine paths
    desktop_path = get_desktop_path()
    shortcut_path = os.path.join(desktop_path, "Research Rabbit.lnk")

    
    # Use absolute path of workspace
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_path = os.path.join(current_dir, "run.bat")
    
    if not os.path.exists(target_path):
        print(f"Error: Target launcher file '{target_path}' not found!")
        sys.exit(1)
        
    print(f"Desktop Path: {desktop_path}")
    print(f"Target Launcher: {target_path}")
    print(f"Working Directory: {current_dir}")
    
    # 2. PowerShell script to create COM WScript.Shell shortcut
    # IconLocation shell32.dll,43 represents a document with a magnifying glass
    ps_command = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
    $Shortcut.TargetPath = "{target_path}"
    $Shortcut.WorkingDirectory = "{current_dir}"
    $Shortcut.IconLocation = "shell32.dll,43"
    $Shortcut.Description = "Launch Research Rabbit Web UI"
    $Shortcut.Save()
    """
    
    try:
        # Run PowerShell command
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True,
            text=True,
            check=True
        )
        print("Success! Desktop shortcut created.")
        print(f"Shortcut Path: {shortcut_path}")
    except subprocess.CalledProcessError as e:
        print("Error: Failed to create shortcut using PowerShell.")
        print(f"Details: {e.stderr}")
        sys.exit(1)

if __name__ == "__main__":
    if sys.platform != "win32":
        print("Shortcut creation is only supported on Windows systems.")
        sys.exit(1)
    create_shortcut()
