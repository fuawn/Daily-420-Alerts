# --- Imports ---
import tkinter as tk
from tkinter import messagebox, font
import subprocess
import sys
import os
import pygame # Handles the sound playback
import time

# --- Configuration ---
APP_NAME = "Daily420"
# IMPORTANT: Make sure this audio file is in the same folder as the script/exe
MP3_FILENAME = "420audio.mp3"
TASK_NAME_BASE = "Daily420Task"
TASK_NAME_AM = f"{TASK_NAME_BASE}_AM"
TASK_NAME_PM = f"{TASK_NAME_BASE}_PM"

# --- Helper Functions ---

def get_resource_path(relative_path):
    """ Finds files (like the MP3) whether running as script or bundled .exe """
    try:
        base_path = sys._MEIPASS # PyInstaller temporary path
    except Exception:
        try: base_path = os.path.abspath(os.path.dirname(__file__))
        except NameError: base_path = os.getcwd() # Fallback if run interactively

    resource_path = os.path.join(base_path, relative_path)
    return resource_path

def is_admin():
    """ Checks if the script has Administrator rights (Windows only) """
    if os.name == 'nt':
        try:
            os.listdir(os.path.join(os.environ.get('SystemRoot','C:\\Windows'),'temp'))
            return True
        except PermissionError: return False
        except Exception: return False
    else: return False

def get_command_to_schedule():
    """ Figures out the command needed to run this app via Task Scheduler """
    try:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Bundled .exe
            app_path = os.path.abspath(sys.executable)
            run_command_for_tr = f'\\"{app_path}\\" --play'
        else:
            # Running as .py script
            python_executable = os.path.abspath(sys.executable)
            script_path = os.path.abspath(__file__)

            python_dir = os.path.dirname(python_executable)
            pythonw_path = os.path.join(python_dir, "pythonw.exe")
            scheduled_interpreter = python_executable
            if not python_executable.lower().endswith("pythonw.exe") and os.path.exists(pythonw_path):
                scheduled_interpreter = pythonw_path # Use pythonw to hide console

            run_command_for_tr = f'\\"{scheduled_interpreter}\\" \\"{script_path}\\" --play'

        return run_command_for_tr
    except Exception as e:
        print(f"Error: Could not determine command to schedule: {e}", file=sys.stderr)
        return None

def run_schtasks_command(command_args):
    """ Runs the schtasks command to manage scheduled tasks. Needs Admin rights for changes. """
    if not is_admin() and ('/create' in command_args or '/delete' in command_args):
        messagebox.showerror("Admin Rights Needed",
                             "This action requires Administrator privileges.\nPlease run 'As Administrator'.")
        return False, "Requires Admin"

    full_command = f'schtasks {command_args}'
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW; startupinfo.wShowWindow = subprocess.SW_HIDE
        result = subprocess.run(full_command, shell=False, check=True, capture_output=True,
                                text=True, errors='ignore', startupinfo=startupinfo)
        return True, result.stdout
    except FileNotFoundError:
        messagebox.showerror("Error", "'schtasks' command not found. Is Windows setup correctly?")
        return False, "'schtasks' not found"
    except subprocess.CalledProcessError as e:
        stderr = str(e.stderr or "").strip(); stdout = str(e.stdout or "").strip()
        error_detail = stderr or stdout or 'Unknown schtasks error'
        if "access is denied" in error_detail.lower(): user_message = "Access Denied. Please run 'As Administrator'."
        elif "invalid argument/option" in error_detail.lower(): user_message = f"Invalid argument passed to schtasks.\nDetails: {error_detail}"
        else: user_message = f"Scheduling command failed.\nError: {error_detail}"
        messagebox.showerror("Scheduling Error", user_message)
        return False, error_detail
    except Exception as e:
        messagebox.showerror("Error", f"An unexpected error occurred:\n{e}")
        return False, str(e)

# --- Playback Function ---

def play_audio_alert():
    """ Handles the actual sound playback using Pygame """
    mp3_path = "[Not Found]"
    mixer_initialized = False
    try:
        mp3_path = get_resource_path(MP3_FILENAME)
        if not os.path.exists(mp3_path):
            print(f"Error: MP3 file not found at '{mp3_path}'. Cannot play.", file=sys.stderr)
            return

        pygame.mixer.init()
        mixer_initialized = True
        if not pygame.mixer.get_init():
             print("Error: Audio mixer failed to initialize.", file=sys.stderr)
             return

        pygame.mixer.music.load(mp3_path)
        pygame.mixer.music.play()
        time.sleep(0.2) # Allow playback to start

        while pygame.mixer.music.get_busy():
            time.sleep(0.2)

    except Exception as e:
        print(f"Error during sound playback: {e}", file=sys.stderr)
    finally:
        if mixer_initialized and pygame.mixer.get_init():
            try:
                pygame.mixer.quit()
            except Exception as quit_err:
                print(f"Error shutting down mixer: {quit_err}", file=sys.stderr)


# --- GUI Application ---

class AlertApp:
    def __init__(self, root_window):
        self.root = root_window
        root_window.title(APP_NAME)
        root_window.geometry("350x200")
        root_window.resizable(False, False)

        label_font = font.Font(family="Segoe UI", size=10)
        button_font = font.Font(family="Segoe UI", size=10, weight="bold")
        status_font = font.Font(family="Segoe UI", size=11, weight="bold")

        self.status_label = tk.Label(root_window, text="Status: Checking...", font=status_font, pady=10)
        self.status_label.pack()

        self.admin_note_label = tk.Label(root_window, text="", font=label_font, fg="darkblue", pady=2)
        self.admin_note_label.pack()

        button_frame = tk.Frame(root_window)
        button_frame.pack(pady=5)

        self.enable_button = tk.Button(button_frame, text="Enable 4:20 Alerts", command=self.enable_alerts,
                                      font=button_font, width=18, height=2, bg="#4CAF50", fg="white",
                                      relief=tk.FLAT, activebackground="#45a049")
        self.enable_button.pack(side=tk.LEFT, padx=10)

        self.disable_button = tk.Button(button_frame, text="Disable 4:20 Alerts", command=self.disable_alerts,
                                       font=button_font, width=18, height=2, bg="#f44336", fg="white",
                                       relief=tk.FLAT, activebackground="#da190b")
        self.disable_button.pack(side=tk.LEFT, padx=10)

        self.check_admin_and_update_note()
        self.check_schedule_status()

    def check_admin_and_update_note(self):
        if not is_admin(): self.admin_note_label.config(text="(Run as Admin to Enable/Disable)")
        else: self.admin_note_label.config(text="(Running as Administrator)")

    def check_schedule_status(self):
        """ Checks Windows Task Scheduler to see if alerts are currently on or off """
        command_args = f'/query /TN "{TASK_NAME_AM}" /FO LIST'
        status_text = "Unknown"; enabled = False
        try:
            startupinfo = subprocess.STARTUPINFO(); startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW; startupinfo.wShowWindow = subprocess.SW_HIDE
            result = subprocess.run(f'schtasks {command_args}', shell=False, capture_output=True,
                                    text=True, errors='ignore', check=False, startupinfo=startupinfo)

            if result.returncode == 0 and "TaskName:" in result.stdout:
                status_line = next((line.lower() for line in result.stdout.splitlines()
                                    if line.strip().lower().startswith("status:")), "")
                if "disabled" in status_line: status_text, enabled = "Disabled", False
                elif "ready" in status_line or "running" in status_line: status_text, enabled = "Enabled", True
                else: status_text, enabled = "Unknown State", False
            else:
                 stderr_lower = (result.stderr or "").lower()
                 if "cannot find the file specified" in stderr_lower: status_text, enabled = "Disabled", False
                 else: status_text, enabled = "Error Checking", False
        except Exception as e:
             print(f"Error checking schedule status: {e}", file=sys.stderr)
             status_text, enabled = "Error Checking Status", False
        self.update_status_display(status_text, enabled)
        return enabled

    def update_status_display(self, status_text, is_enabled):
        self.status_label.config(text=f"Status: {status_text}",
                                 fg="green" if is_enabled else ("#e67e22" if "Error" in status_text else "red"))
        self.enable_button.config(state=tk.NORMAL if not is_enabled else tk.DISABLED)
        self.disable_button.config(state=tk.NORMAL if is_enabled else tk.DISABLED)

    def enable_alerts(self):
        """ Sets up the scheduled tasks in Windows. Requires Admin. """
        command_to_run = get_command_to_schedule()
        if not command_to_run: messagebox.showerror("Error", "Could not determine command."); return
        try: run_as_user = os.getlogin()
        except Exception: run_as_user = "SYSTEM"
        common_create_args = ( f'/SC DAILY /F /RL HIGHEST /TR "{command_to_run}" /RU "{run_as_user}" /IT ')

        command_args_am = f'/create /TN "{TASK_NAME_AM}" {common_create_args} /ST 04:20'
        success_am, _ = run_schtasks_command(command_args_am)
        if not success_am: self.check_schedule_status(); return

        command_args_pm = f'/create /TN "{TASK_NAME_PM}" {common_create_args} /ST 16:20'
        success_pm, _ = run_schtasks_command(command_args_pm)
        if not success_pm: self.check_schedule_status(); return

        messagebox.showinfo("Success!", "Daily 4:20 alerts are now ON!\n"
"You can now close the window!\n\n"
                                      "Note: If your PC might be asleep at 4:20,\n"
                                      "and you would still like it to play the sound,\n"
                                      "you can manually check 'Wake the computer' in\n"
                                      "Task Properties -> Conditions (via Task Scheduler).")
        self.update_status_display("Enabled", True)


    def disable_alerts(self):
        """ Removes the scheduled tasks from Windows. Requires Admin. """
        deleted_any = False; failed_any = False

        for task_name in [TASK_NAME_AM, TASK_NAME_PM]:
            command_args = f'/delete /TN "{task_name}" /F'
            success, output = run_schtasks_command(command_args)
            if success: deleted_any = True
            elif "could not find the task" not in str(output).lower() and \
                 "cannot find the file specified" not in str(output).lower():
                failed_any = True

        if not failed_any:
             msg = "Alerts are now OFF." if deleted_any else "Alerts already seemed to be off."
             messagebox.showinfo("Done" if deleted_any else "Info", msg)
             self.update_status_display("Disabled", False)
        else:
             self.check_schedule_status() # Update status after potential partial failure


# --- Main Program Start ---

if __name__ == "__main__":

    if "--play" in sys.argv:
        try: play_audio_alert()
        except Exception as play_err:
            print(f"FATAL: Unhandled error during playback: {play_err}", file=sys.stderr)
        sys.exit()

    else: # Launch GUI
        try:
             if 'tk' not in sys.modules: # Ensure tkinter is available
                import tkinter as tk; from tkinter import messagebox, font

             root = tk.Tk()
             app = AlertApp(root)
             root.mainloop()

        except ImportError as import_err:
             print(f"FATAL ERROR: Cannot load GUI (Tkinter missing?). Error: {import_err}", file=sys.stderr)
             # Attempt to show a simple message box if possible, otherwise just exit
             try: messagebox.showerror("Fatal Error", "Required library (Tkinter) is missing.\nPlease ensure Python's Tk/Tcl support is installed.")
             except Exception: pass
             sys.exit(1)
        except Exception as gui_err:
            print(f"FATAL ERROR: Unexpected GUI error: {gui_err}", file=sys.stderr)
            try: messagebox.showerror("Fatal Error", f"Whoa! An unexpected error occurred:\n{gui_err}")
            except Exception: pass
            sys.exit(1)