# Academic Paper PDF Renamer & Auto-Scanner

Automatically renames academic PDFs in this folder and all subfolders into standard academic format:
```
Year_Journal Acronym_Paper Title.pdf
```
Examples:
- `2024_NatComm_Virtual-freezing fluorescence imaging flow cytometry.pdf`
- `2018_JBO_Raman biophysical markers in skin cancer diagnosis.pdf`
- `2021_ACSNano_Ultrasound-triggered bioluminescence immunotherapy.pdf`

---

## Moving to Another Computer

### Step 1: Files to Copy
Copy this entire folder (or sync it via Box, Dropbox, OneDrive, or USB). The essential script files are:
- `rename_papers.py` (Core script)
- `requirements.txt` (Dependencies list)
- `install_requirements.bat` (1-click installer for Windows)
- `start_autoscan_watcher.bat` (1-click live watcher)
- `start_autoscan_background.vbs` (Silent background launcher)
- `stop_autoscan_background.bat` (Stops background watcher)
- `.doi_cache.json` (Optional metadata cache; speeds up renames)

### Step 2: Install Python (if not already installed)
1. Download Python 3 from [python.org/downloads](https://www.python.org/downloads/).
2. **Important**: During installation on Windows, check the box:  
   **☑ "Add Python to PATH"**.

### Step 3: Install Required Packages
Double-click:
- **`install_requirements.bat`**  
*(or open terminal in this folder and run: `pip install -r requirements.txt`)*

Only two lightweight packages are needed:
- `PyMuPDF` (for reading PDF metadata and text)
- `watchdog` (for monitoring newly added files in real time)

---

## How to Use

### 1. Auto-Scan & Rename Newly Added PDFs
- **Visible Window**: Double-click **`start_autoscan_watcher.bat`** (or run `python rename_papers.py --watch`).
- **Silent Background**: Double-click **`start_autoscan_background.vbs`** (to stop, double-click **`stop_autoscan_background.bat`**).

### 2. Manual Batch Renaming Existing PDFs
- **Dry Run (Preview without changing files)**:
  ```powershell
  python rename_papers.py
  ```
- **Apply Renaming**:
  ```powershell
  python rename_papers.py --apply
  ```
- **Specific Directory**:
  ```powershell
  python rename_papers.py --dir "C:\Path\To\Papers"
  ```
- **Audit Log**:
  Check `renaming_report.csv` to review all files renamed.
