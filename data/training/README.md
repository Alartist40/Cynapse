# Training Data Directory

Place your training documents here. Supported formats:
- `.txt` - Plain text files
- `.pdf` - PDF documents (requires pypdf)
- `.json` - JSON data files
- `.md` - Markdown documents

These files will be used by the Elara model and other neurons for training and fine-tuning.

## Usage

1. Add your documents to this folder
2. Run the training script:
   ```bash
   cd neurons/elara
   python train.py --data-dir ../../data/training
   ```

**Note**: Large files should be added to `.gitignore` to avoid bloating the repository.
