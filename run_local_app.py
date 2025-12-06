import subprocess
import sys

# --- Instructions for Local Use ---
# 1. Ensure you have Streamlit installed: pip install streamlit
# 2. Make sure the file 'euro2024_yamal_analysis.py' is in the same directory.
# 3. Run this script directly from your terminal: python run_local_app.py
# ----------------------------------

def start_streamlit_app():
    """
    Runs the Streamlit application using the subprocess module.
    
    In a local environment, you typically just need the 'streamlit run' command.
    No need for ngrok, token authentication, or headless settings.
    """
    app_file = "euro2024_yamal_analysis.py"
    
    print(f"Attempting to start Streamlit app: {app_file}")
    print("If this is your first time, Streamlit may take a few seconds to load.")
    print("It should automatically open your browser to http://localhost:8502p")
    
    try:
        # Use subprocess.run for a blocking execution, which is typical for a terminal application
        # When you close the terminal, the Streamlit app will stop.
        subprocess.run([sys.executable, "-m", "streamlit", "run", app_file], check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"\nError starting Streamlit: The command failed with return code {e.returncode}.")
        print("Please ensure Streamlit is installed (pip install streamlit) and the app file exists.")
    except FileNotFoundError:
        print("\nError: Could not find the 'streamlit' executable.")
        print("Please check your Python environment.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    start_streamlit_app()