"""
Load real clinical guidelines from PDF files into RAG corpus.
This script processes ADA, WHO, and ICMR guidelines.
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import PyPDF2
    import chromadb
    from chromadb.config import Settings
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False
    logger.warning("Required dependencies not available. Install with: pip install PyPDF2 chromadb")


class GuidelineLoader:
    """Load and process clinical guidelines from PDF files."""
    
    def __init__(self, guidelines_dir: str = "data/guidelines"):
        """
        Initialize guideline loader.
        
        Args:
            guidelines_dir: Directory containing guideline PDF files
        """
        self.guidelines_dir = Path(guidelines_dir)
        self.guidelines_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB
        chroma_dir = Path("data/chroma")
        chroma_dir.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(chroma_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        
        try:
            self.collection = self.client.get_collection("clinical_guidelines")
            logger.info(f"Using existing collection with {self.collection.count()} documents")
        except:
            self.collection = self.client.create_collection(
                name="clinical_guidelines",
                metadata={"description": "Clinical practice guidelines corpus"}
            )
            logger.info("Created new collection")
    
    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """
        Extract text from PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text
        """
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        text += f"\n\n--- Page {page_num + 1} ---\n\n{page_text}"
                    except Exception as e:
                        logger.warning(f"Failed to extract page {page_num + 1}: {e}")
                
                logger.info(f"Extracted {len(text)} characters from {pdf_path.name}")
                return text
        
        except Exception as e:
            logger.error(f"Failed to read PDF {pdf_path}: {e}")
            return ""
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to chunk
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)
                
                if break_point > chunk_size * 0.5:  # Only break if we're past halfway
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1
            
            chunks.append(chunk.strip())
            start = end - overlap
        
        return [c for c in chunks if len(c) > 100]  # Filter out very short chunks
    
    def load_ada_guidelines(self) -> int:
        """
        Load ADA 2024 Standards of Care.
        
        Returns:
            Number of chunks loaded
        """
        pdf_path = self.guidelines_dir / "ADA_2024_Standards_of_Care.pdf"
        
        if not pdf_path.exists():
            logger.warning(f"ADA guidelines not found at {pdf_path}")
            logger.info("Please download from: https://diabetesjournals.org/care/issue/47/Supplement_1")
            return 0
        
        logger.info("Loading ADA 2024 Standards of Care...")
        text = self.extract_text_from_pdf(pdf_path)
        
        if not text:
            return 0
        
        chunks = self.chunk_text(text)
        logger.info(f"Created {len(chunks)} chunks from ADA guidelines")
        
        # Add to collection
        documents = chunks
        metadatas = [
            {
                "source": "ADA 2024",
                "year": "2024",
                "guideline": "Standards of Medical Care in Diabetes",
                "population": "adult",
                "condition": "diabetes",
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]
        ids = [f"ada_2024_{i}" for i in range(len(chunks))]
        
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"Loaded {len(chunks)} ADA guideline chunks")
        return len(chunks)
    
    def load_who_guidelines(self) -> int:
        """
        Load WHO Diabetes Guidelines.
        
        Returns:
            Number of chunks loaded
        """
        pdf_path = self.guidelines_dir / "WHO_Diabetes_Guidelines.pdf"
        
        if not pdf_path.exists():
            logger.warning(f"WHO guidelines not found at {pdf_path}")
            logger.info("Please download from: https://www.who.int/publications/i/item/9789241549950")
            return 0
        
        logger.info("Loading WHO Diabetes Guidelines...")
        text = self.extract_text_from_pdf(pdf_path)
        
        if not text:
            return 0
        
        chunks = self.chunk_text(text)
        logger.info(f"Created {len(chunks)} chunks from WHO guidelines")
        
        # Add to collection
        documents = chunks
        metadatas = [
            {
                "source": "WHO Guidelines",
                "year": "2023",
                "guideline": "Management of Diabetes Mellitus",
                "population": "adult",
                "condition": "diabetes",
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]
        ids = [f"who_2023_{i}" for i in range(len(chunks))]
        
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"Loaded {len(chunks)} WHO guideline chunks")
        return len(chunks)
    
    def load_icmr_guidelines(self) -> int:
        """
        Load ICMR Diabetes Guidelines.
        
        Returns:
            Number of chunks loaded
        """
        pdf_path = self.guidelines_dir / "ICMR_Diabetes_2023.pdf"
        
        if not pdf_path.exists():
            logger.warning(f"ICMR guidelines not found at {pdf_path}")
            logger.info("Please download from: https://main.icmr.nic.in/content/diabetes")
            return 0
        
        logger.info("Loading ICMR Diabetes Guidelines...")
        text = self.extract_text_from_pdf(pdf_path)
        
        if not text:
            return 0
        
        chunks = self.chunk_text(text)
        logger.info(f"Created {len(chunks)} chunks from ICMR guidelines")
        
        # Add to collection
        documents = chunks
        metadatas = [
            {
                "source": "ICMR 2023",
                "year": "2023",
                "guideline": "Management of Type 2 Diabetes",
                "population": "adult",
                "condition": "diabetes",
                "region": "India",
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]
        ids = [f"icmr_2023_{i}" for i in range(len(chunks))]
        
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        logger.info(f"Loaded {len(chunks)} ICMR guideline chunks")
        return len(chunks)
    
    def load_all_guidelines(self) -> Dict[str, int]:
        """
        Load all available guidelines.
        
        Returns:
            Dictionary with counts for each guideline source
        """
        results = {
            "ADA": self.load_ada_guidelines(),
            "WHO": self.load_who_guidelines(),
            "ICMR": self.load_icmr_guidelines(),
        }
        
        total = sum(results.values())
        logger.info(f"\nTotal guidelines loaded: {total} chunks")
        logger.info(f"Total corpus size: {self.collection.count()} documents")
        
        return results
    
    def verify_corpus(self):
        """Verify corpus is loaded correctly."""
        count = self.collection.count()
        logger.info(f"\nCorpus verification:")
        logger.info(f"Total documents: {count}")
        
        # Test query
        if count > 0:
            results = self.collection.query(
                query_texts=["diabetes management metformin"],
                n_results=3
            )
            logger.info(f"\nSample query results:")
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i]
                logger.info(f"\n{i+1}. Source: {metadata.get('source', 'Unknown')}")
                logger.info(f"   Preview: {doc[:200]}...")


def main():
    """Main function to load guidelines."""
    if not DEPENDENCIES_AVAILABLE:
        logger.error("Required dependencies not installed.")
        logger.error("Install with: pip install PyPDF2 chromadb")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("MedScribe Clinical Guidelines Loader")
    logger.info("=" * 60)
    
    loader = GuidelineLoader()
    
    logger.info("\nChecking for guideline PDF files...")
    logger.info(f"Guidelines directory: {loader.guidelines_dir.absolute()}")
    
    # Check which files exist
    ada_exists = (loader.guidelines_dir / "ADA_2024_Standards_of_Care.pdf").exists()
    who_exists = (loader.guidelines_dir / "WHO_Diabetes_Guidelines.pdf").exists()
    icmr_exists = (loader.guidelines_dir / "ICMR_Diabetes_2023.pdf").exists()
    
    logger.info(f"\nADA Guidelines: {'✓ Found' if ada_exists else '✗ Not found'}")
    logger.info(f"WHO Guidelines: {'✓ Found' if who_exists else '✗ Not found'}")
    logger.info(f"ICMR Guidelines: {'✓ Found' if icmr_exists else '✗ Not found'}")
    
    if not any([ada_exists, who_exists, icmr_exists]):
        logger.error("\nNo guideline PDFs found!")
        logger.error("Please download guidelines and place them in the guidelines directory.")
        logger.error("See MANUAL_STEPS.md for download instructions.")
        sys.exit(1)
    
    logger.info("\nLoading guidelines into corpus...")
    results = loader.load_all_guidelines()
    
    logger.info("\n" + "=" * 60)
    logger.info("Loading Summary:")
    logger.info("=" * 60)
    for source, count in results.items():
        status = "✓" if count > 0 else "✗"
        logger.info(f"{status} {source}: {count} chunks")
    
    logger.info("\nVerifying corpus...")
    loader.verify_corpus()
    
    logger.info("\n" + "=" * 60)
    logger.info("Guidelines loading complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

# Made with Bob
