# ⚽ Lamine Yamal's Euro 2024 Performance Analyzer

This project uses Python, Streamlit, and `statsbombpy` (StatsBomb Open Data) to analyze the in-tournament performance of Lamine Yamal during Euro 2024. The application generates key statistics, shot maps, pass maps (highlighting assists), and a positional heatmap of player touches.

## 🚀 Deployment and Usage Guide

The following steps outline how to set up the environment, deploy the code to GitHub, and launch the application on Streamlit Community Cloud.

---

## 1. Local Setup and Execution

To run the application locally and ensure all dependencies are met:

### Prerequisites

You need **Python 3** and **pip** installed.

### Step-by-Step

1.  **Clone the Repository (Optional, if starting fresh):**
    ```bash
    git clone [YOUR_REPO_URL]
    cd [YOUR_REPO_NAME]
    ```

2.  **Install Dependencies:**
    The application relies on the libraries listed in `requirements.txt`. Install them using pip:
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: If you are missing the `requirements.txt` file, its contents are listed in Section 3.)*

3.  **Run the App Locally:**
    Launch the Streamlit application from your terminal:
    ```bash
    streamlit run Euro_yamal.py
    ```
    Your application will automatically open in your web browser.

---

## 2. GitHub Setup (If you haven't pushed the code yet)

If you are setting up the repository for the first time or making changes:

1.  **Initialize Git:**
    ```bash
    git init
    ```

2.  **Add all files and Commit:**
    ```bash
    git add .
    git commit -m "Initial commit: Add Streamlit app code and requirements"
    ```

3.  **Connect to Remote Repository:**
    Replace the URL below with the HTTPS URL of your GitHub repository.
    ```bash
    git remote add origin [YOUR_GITHUB_REPO_URL]
    git branch -M main
    ```

4.  **Push the Code:**
    ```bash
    git push -u origin main
    ```

---

## 3. Deploy to Streamlit Community Cloud

The easiest way to make the application publicly available is through Streamlit's official cloud service.

### Prerequisites: `requirements.txt`

Ensure this file is in the root of your repository and contains all necessary packages:

```text
streamlit
pandas
statsbombpy
mplsoccer
matplotlib
numpy
scipy 
Pillow
