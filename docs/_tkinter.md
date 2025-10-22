Usage Examples
Import with GUI File Picker
bash# Open file picker to select CSV
python manage_hashes.py import vehicle --gui

# With auto-confirm
python manage_hashes.py import vehicle --gui --yes
Import from Command Line
bash# Provide file path directly
python manage_hashes.py import vehicle config/hashes/vehicles.csv

# Will prompt if no file provided
python manage_hashes.py import vehicle
# Enter path to CSV file: config/hashes/vehicles.csv
Export with GUI Save Dialog
bash# Open save dialog to choose where to export
python manage_hashes.py export-unknown trailer --gui
Export to Specific File
bash# Direct export
python manage_hashes.py export-unknown trailer unknown_trailers.csv
Search Functionality
bash# Search by name
python manage_hashes.py search "TRUCK-001"

# Search by partial hash
python manage_hashes.py search "abc123"

Install tkinter (if not already installed)
bash# Ubuntu/Debian
sudo apt update
sudo apt install python3-tk

# Test installation
python3 -c "import tkinter; print('tkinter is installed')"
```

---

## Update `requirements.txt`

Add this line:
```
tabulate>=0.9.0
Install:
bashpip install tabulate
```

---

## Features Added

### 1. **GUI File Picker**
- Opens native file browser
- Filters for CSV files
- Shows preview before selection

### 2. **GUI Save Dialog**
- Opens save dialog for exports
- Suggests default filename
- Prevents accidental overwrites

### 3. **Flexible File Input**
- Command line: `python manage_hashes.py import vehicle path/to/file.csv`
- GUI picker: `python manage_hashes.py import vehicle --gui`
- Interactive prompt: `python manage_hashes.py import vehicle` (then type path)

### 4. **Search Functionality**
- Search by hash value
- Search by entity name
- Case-insensitive
- Shows up to 50 results

### 5. **Enhanced Output**
- Tabulated displays
- Status indicators (✓, ⚠, ✗)
- Coverage percentages
- Clear next-step instructions

---

## Screenshot of GUI Picker (Conceptual)
```
┌─────────────────────────────────────────────────────────┐
│ Select CSV file to import vehicle hashes               │
├─────────────────────────────────────────────────────────┤
│ Look in: ▼ config/hashes/                              │
│                                                         │
│  📁 ..                                                  │
│  📄 vehicles.csv                                        │
│  📄 trailers.csv                                        │
│  📄 departments.csv                                     │
│  📄 teams.csv                                           │
│                                                         │
│ File name: vehicles.csv                    Files of typ│
│                                            ▼ CSV files │
│                                                         │
│                                [Open]  [Cancel]         │
└─────────────────────────────────────────────────────────┘

Testing
bash# Test GUI picker
python manage_hashes.py import vehicle --gui

# Test direct import
python manage_hashes.py import vehicle config/hashes/vehicles.csv

# Test export with save dialog
python manage_hashes.py export-unknown vehicle --gui

# Test search
python manage_hashes.py search "TRUCK"

# Test stats
python manage_hashes.py stats

This gives you maximum flexibility: use GUI when convenient, command line for scripts/automation, and interactive prompts when needed!