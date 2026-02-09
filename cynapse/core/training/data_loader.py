"""
Document Data Loader for Elara Training
=======================================

Processes PDFs, text files, and code for training.
Extracts text, chunks it, and tokenizes for model training.
"""

import re
import json
import pickle
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import warnings

# Try to import PyPDF2 for PDF processing
try:
    import PyPDF2
    HAS_PDF = True
except ImportError:
    HAS_PDF = False
    warnings.warn("PyPDF2 not installed. PDF processing disabled.")

try:
    import torch
    from torch.utils.data import Dataset, DataLoader
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    warnings.warn("PyTorch not installed. Training will use mock data.")


@dataclass
class TrainingConfig:
    """Configuration for document processing"""
    chunk_size: int = 1024
    chunk_overlap: int = 128
    batch_size: int = 4
    max_files: int = 1000
    supported_extensions: Tuple[str, ...] = ('.txt', '.pdf', '.md', '.py', '.json')


class DocumentDataLoader:
    """
    Loads and processes documents for Elara training.
    
    Supports:
    - PDF files (with PyPDF2)
    - Text files (.txt, .md)
    - Code files (.py, .json, etc.)
    - Directory recursion
    """
    
    def __init__(self, config: Optional[TrainingConfig] = None):
        self.config = config or TrainingConfig()
        self.processed_docs: List[Dict] = []
        self.total_tokens: int = 0
        
    def load_documents(self, docs_path: Path) -> List[Dict]:
        """
        Load all documents from a directory or single file.
        
        Args:
            docs_path: Path to directory or file
            
        Returns:
            List of processed document dictionaries
        """
        docs_path = Path(docs_path)
        
        if not docs_path.exists():
            raise FileNotFoundError(f"Path not found: {docs_path}")
        
        self.processed_docs = []
        
        if docs_path.is_file():
            # Single file
            doc = self._process_file(docs_path)
            if doc:
                self.processed_docs.append(doc)
        elif docs_path.is_dir():
            # Directory - scan recursively
            files_processed = 0
            for ext in self.config.supported_extensions:
                for file_path in docs_path.rglob(f"*{ext}"):
                    if files_processed >= self.config.max_files:
                        print(f"Reached max file limit ({self.config.max_files})")
                        break
                    
                    doc = self._process_file(file_path)
                    if doc:
                        self.processed_docs.append(doc)
                        files_processed += 1
                        
        print(f"Processed {len(self.processed_docs)} documents")
        return self.processed_docs
    
    def _process_file(self, file_path: Path) -> Optional[Dict]:
        """Process a single file based on its type."""
        try:
            suffix = file_path.suffix.lower()
            
            if suffix == '.pdf' and HAS_PDF:
                text = self._extract_pdf_text(file_path)
            elif suffix in ['.txt', '.md', '.py', '.json']:
                text = self._extract_text_file(file_path)
            else:
                return None
                
            if not text or len(text.strip()) < 100:
                return None  # Skip very short documents
                
            # Chunk the text
            chunks = self._chunk_text(text)
            
            return {
                'path': str(file_path),
                'filename': file_path.name,
                'type': suffix,
                'text': text,
                'chunks': chunks,
                'num_chunks': len(chunks),
                'total_chars': len(text)
            }
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return None
    
    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text from PDF using PyPDF2."""
        if not HAS_PDF:
            return ""
            
        text = ""
        try:
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            print(f"PDF extraction error: {e}")
            
        return text
    
    def _extract_text_file(self, file_path: Path) -> str:
        """Extract text from plain text files."""
        encodings = ['utf-8', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
                
        return ""
    
    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks for training.
        
        Uses sentence-aware chunking to avoid cutting mid-sentence.
        """
        chunks = []
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap
        
        # Simple chunking strategy
        start = 0
        while start < len(text):
            end = start + chunk_size
            
            # Try to find a sentence boundary
            if end < len(text):
                # Look for period, question mark, or newline
                for i in range(end, max(start, end - overlap), -1):
                    if i < len(text) and text[i] in '.!?\n':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if len(chunk) > 100:  # Only keep substantial chunks
                chunks.append(chunk)
            
            start = end - overlap
            
        return chunks
    
    def create_training_dataset(self) -> Optional['TextDataset']:
        """
        Create a PyTorch Dataset from processed documents.
        
        Returns:
            TextDataset ready for training, or None if PyTorch unavailable
        """
        if not HAS_TORCH:
            print("PyTorch not available. Cannot create dataset.")
            return None
            
        if not self.processed_docs:
            print("No documents loaded. Call load_documents() first.")
            return None
            
        # Flatten all chunks into training samples
        all_chunks = []
        for doc in self.processed_docs:
            all_chunks.extend(doc['chunks'])
            
        print(f"Created dataset with {len(all_chunks)} chunks")
        return TextDataset(all_chunks)
    
    def get_statistics(self) -> Dict:
        """Get statistics about loaded documents."""
        if not self.processed_docs:
            return {}
            
        total_chars = sum(d['total_chars'] for d in self.processed_docs)
        total_chunks = sum(d['num_chunks'] for d in self.processed_docs)
        
        file_types = {}
        for doc in self.processed_docs:
            ext = doc['type']
            file_types[ext] = file_types.get(ext, 0) + 1
            
        return {
            'num_documents': len(self.processed_docs),
            'total_characters': total_chars,
            'total_chunks': total_chunks,
            'avg_chunk_size': total_chars // max(total_chunks, 1),
            'file_types': file_types
        }
    
    def save_processed_data(self, output_path: Path):
        """Save processed documents to disk for faster reloading."""
        with open(output_path, 'wb') as f:
            pickle.dump(self.processed_docs, f)
        print(f"Saved processed data to {output_path}")
    
    def load_processed_data(self, input_path: Path):
        """Load previously processed documents."""
        with open(input_path, 'rb') as f:
            self.processed_docs = pickle.load(f)
        print(f"Loaded {len(self.processed_docs)} documents from {input_path}")


if HAS_TORCH:
    class TextDataset(Dataset):
        """Simple PyTorch dataset for text chunks."""
        
        def __init__(self, chunks: List[str]):
            self.chunks = chunks
            
        def __len__(self):
            return len(self.chunks)
        
        def __getitem__(self, idx):
            return self.chunks[idx]
else:
    # Mock dataset when PyTorch unavailable
    class TextDataset:
        def __init__(self, chunks: List[str]):
            self.chunks = chunks
        def __len__(self):
            return len(self.chunks)
        def __getitem__(self, idx):
            return self.chunks[idx]


# CLI interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python data_loader.py <path_to_documents>")
        sys.exit(1)
        
    docs_path = Path(sys.argv[1])
    loader = DocumentDataLoader()
    
    print(f"Loading documents from {docs_path}...")
    loader.load_documents(docs_path)
    
    stats = loader.get_statistics()
    print("\nStatistics:")
    print(f"  Documents: {stats['num_documents']}")
    print(f"  Total chars: {stats['total_characters']:,}")
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"  File types: {stats['file_types']}")
    
    # Save processed data
    loader.save_processed_data(Path("processed_docs.pkl"))
