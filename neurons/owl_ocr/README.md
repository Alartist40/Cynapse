# One-file Privacy OCR (MVP)

A single Python file tool to perform local OCR on images and redact private information (PII) such as emails, phone numbers, and SSNs.

## 🚀 Features

- **Local Processing**: No data leaves your machine.
- **OCR Capability**: Extracts text from images using Tesseract.
- **PII Detection**: Automatically finds and masks:
    - Emails
    - Phone Numbers
    - Credit Card Numbers
    - Social Security Numbers
- **Redaction**: Draws black rectangles over sensitive data.
- **JSON Reports**: Generates a fast, parseable JSON report of all redacted items.

## 🛠️ Setup

### 1. Prerequisites
- **Python 3.8+** installed.
- **Tesseract OCR**: This tool requires the Tesseract binary.
    - **Download**: [Tesseract at UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
    - **Install/Place**:
        - Create a folder named `tesseract` in the same directory as `redact.py`.
        - Copy your Tesseract installation (specifically `tesseract.exe` and `tessdata` folder) into this `tesseract/` folder.
        - Structure should be:
          ```
          project/
          ├── redact.py
          └── tesseract/
              ├── tesseract.exe
              └── tessdata/
          ```
- **Flair Model (Optional/Future)**: 
    - For advanced Named Entity Recognition (Persons, Locations), download the Flair Mini model and place it as `flair_mini.pt` next to the script. (Currently placeholder support).

### 2. Install Dependencies
Run the following command to install the necessary lightweight Python libraries:
```bash
pip install -r requirements.txt
```
*(Only requires `pypdf` and `Pillow`)*

## 📖 Usage

### Redact an Image
Simply run the script with the path to your image:
```bash
python redact.py input_image.png
```

**Output**:
- `input_image_redacted.png`: The image with black bars over PII.
- `input_image_report.json`: A detailed report of what was found.

### Redact a PDF
*Note: Full PDF Support requires Tesseract to be configured for PDF ingestion or external tools like Poppler. The current MVP focuses on Image OCR stability. PDF inputs might not be fully processed if they don't contain embedded images.*

```bash
python redact.py contract.pdf
```

## 🔒 Privacy & Security

- **Zero Trust**: No network requests are made.
- **Local Only**: All processing happens on your CPU.
- **Open Source**: Verify the code in `redact.py` yourself (it's ~150 lines).

## 📄 License
MIT
