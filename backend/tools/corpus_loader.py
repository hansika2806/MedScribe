"""
Clinical guidelines corpus loader
Loads real clinical guidelines from PubMed and hard-coded sources into ChromaDB
"""
import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import required libraries
try:
    from Bio import Entrez
    import chromadb
    from chromadb.config import Settings
    CORPUS_AVAILABLE = True
    logger.info("Corpus loading libraries available")
except ImportError as e:
    CORPUS_AVAILABLE = False
    logger.warning(f"Corpus loading libraries not available: {e}")


# Hard-coded clinical guideline documents
HARDCODED_GUIDELINES = [
    {
        "content": """ADA Standards of Medical Care in Diabetes 2024.
Pharmacologic Therapy for Type 2 Diabetes. Metformin 
remains the preferred initial pharmacologic agent for 
type 2 diabetes in adults. If HbA1c is above 9%, 
consider initiating dual therapy. Target HbA1c below 7% 
for most non-pregnant adults with diabetes. Metformin 
dosing: start 500mg twice daily with meals, increase to 
1000mg twice daily as tolerated. Maximum dose 2550mg/day.""",
        "metadata": {
            "population": "adult",
            "condition": "diabetes",
            "drug_class": "antidiabetic",
            "source": "ADA 2024",
            "section": "Section 9: Pharmacologic Approaches",
            "year": "2024"
        }
    },
    {
        "content": """ADA Standards of Medical Care in Diabetes 2024.
Glycemic Targets. For most nonpregnant adults with 
diabetes, an HbA1c goal of less than 7% is appropriate. 
Less stringent HbA1c goals such as less than 8% may be 
appropriate for patients with limited life expectancy, 
history of severe hypoglycemia, or extensive comorbidities.
Blood pressure target for adults with diabetes is below 
130/80 mmHg. SMBG frequency should be sufficient to 
facilitate reaching glucose goals.""",
        "metadata": {
            "population": "adult",
            "condition": "diabetes",
            "drug_class": "antidiabetic",
            "source": "ADA 2024",
            "section": "Section 6: Glycemic Targets",
            "year": "2024"
        }
    },
    {
        "content": """JNC 8 Guidelines for Management of High Blood 
Pressure in Adults. In the general nonblack population 
including those with diabetes, initial antihypertensive 
treatment should include a thiazide-type diuretic, 
calcium channel blocker, ACE inhibitor, or ARB. 
For adults aged 18-59 years with hypertension, 
treat to a systolic goal of less than 140 mmHg. 
Lisinopril starting dose: 10mg once daily. 
Maximum dose: 40mg once daily. 
First-line agent for hypertension with diabetes.""",
        "metadata": {
            "population": "adult",
            "condition": "hypertension",
            "drug_class": "antihypertensive",
            "source": "JNC 8 Guidelines",
            "section": "Recommendation 6",
            "year": "2014"
        }
    },
    {
        "content": """AHA/ACC Chest Pain Guideline 2021. 
Evaluation of patients with chest pain requires 
systematic risk stratification. For patients with 
acute chest pain and suspected ACS, obtain 12-lead ECG 
within 10 minutes of arrival. Measure high-sensitivity 
cardiac troponin at presentation and 1-3 hours later. 
HEART score greater than 6 indicates high risk requiring 
early invasive strategy. Musculoskeletal chest pain 
diagnosis requires exclusion of cardiac, pulmonary, 
and gastrointestinal causes.""",
        "metadata": {
            "population": "adult",
            "condition": "cardiac",
            "drug_class": "general",
            "source": "AHA/ACC 2021",
            "section": "Chest Pain Evaluation",
            "year": "2021"
        }
    },
    {
        "content": """WHO Guidelines for Treatment of Diabetes 
Mellitus. Metformin is recommended as first-line 
pharmacological therapy for type 2 diabetes in adults 
when lifestyle interventions are insufficient. 
Insulin therapy should be initiated when HbA1c remains 
above 9% despite dual oral therapy, or when patient 
presents with severe hyperglycemia. Blood glucose 
targets: fasting 4-7 mmol/L, post-meal below 10 mmol/L.
Regular monitoring of renal function required for 
metformin therapy — contraindicated if eGFR below 30.""",
        "metadata": {
            "population": "adult",
            "condition": "diabetes",
            "drug_class": "antidiabetic",
            "source": "WHO Guidelines",
            "section": "Diabetes Management",
            "year": "2023"
        }
    },
    {
        "content": """ICMR Clinical Practice Guidelines for 
Management of Type 2 Diabetes 2023 India. 
Indian patients with type 2 diabetes have unique 
characteristics including younger age of onset, 
higher visceral adiposity, and greater susceptibility 
to diabetic nephropathy. Metformin remains first-line 
therapy. Target HbA1c below 7% for most patients. 
Consider SGLT2 inhibitors or GLP-1 agonists for 
patients with established cardiovascular disease. 
Monitor HbA1c every 3 months until stable, then 
every 6 months. Screen for diabetic nephropathy 
annually with urine albumin-creatinine ratio.""",
        "metadata": {
            "population": "adult",
            "condition": "diabetes",
            "drug_class": "antidiabetic",
            "source": "ICMR 2023",
            "section": "Indian Clinical Guidelines",
            "year": "2023"
        }
    },
    {
        "content": """ADA Pediatric Diabetes Standards 2024.
Children and adolescents with type 1 diabetes require 
insulin therapy. Metformin may be used as adjunct 
therapy in type 2 diabetes in youth aged 10 years 
and older. Starting dose for pediatric patients: 
500mg once daily with evening meal, increase slowly. 
Maximum dose 2000mg/day in pediatric patients. 
HbA1c target below 7% for most pediatric patients. 
Insulin dosing in children is weight-based: 
0.5-1.0 units/kg/day total daily dose.""",
        "metadata": {
            "population": "pediatric",
            "condition": "diabetes",
            "drug_class": "antidiabetic",
            "source": "ADA Pediatric 2024",
            "section": "Pediatric Standards",
            "year": "2024"
        }
    },
    {
        "content": """Pediatric Hypertension Guidelines AAP 2017.
Normal blood pressure in children varies by age, 
sex, and height. Hypertension in children defined as 
blood pressure at or above 95th percentile on three 
separate occasions. Pharmacologic treatment indicated 
for stage 2 hypertension or when lifestyle modification 
fails for stage 1. ACE inhibitors are first-line agents 
for children with hypertension and diabetes or 
proteinuria. Amlodipine dosing in children: 
0.1-0.2 mg/kg/day, maximum 5mg/day for children 
under 6 years.""",
        "metadata": {
            "population": "pediatric",
            "condition": "hypertension",
            "drug_class": "antihypertensive",
            "source": "AAP 2017",
            "section": "Pediatric Hypertension",
            "year": "2017"
        }
    }
]


# PubMed search terms
PUBMED_SEARCH_TERMS = [
    "type 2 diabetes management guidelines adult",
    "hypertension treatment guidelines adult",
    "chest pain diagnosis guidelines adult",
    "diabetes management pediatric guidelines",
    "hypertension pediatric guidelines",
    "metformin dosing diabetes adult",
    "insulin initiation type 2 diabetes",
    "lisinopril hypertension treatment"
]


def fetch_pubmed_abstracts(search_term: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch abstracts from PubMed using Entrez API
    
    Args:
        search_term: Search query
        max_results: Maximum number of results to fetch
        
    Returns:
        List of abstract documents with metadata
    """
    if not CORPUS_AVAILABLE:
        logger.warning("Biopython not available, skipping PubMed fetch")
        return []
    
    try:
        Entrez.email = "medscribe@research.com"
        
        # Search for articles
        handle = Entrez.esearch(
            db="pubmed",
            term=search_term,
            retmax=max_results,
            sort="relevance"
        )
        record = Entrez.read(handle)
        handle.close()
        ids = record["IdList"]
        
        if not ids:
            logger.warning(f"No results found for: {search_term}")
            return []
        
        abstracts = []
        for pmid in ids:
            try:
                # Fetch abstract
                fetch = Entrez.efetch(
                    db="pubmed",
                    id=pmid,
                    rettype="abstract",
                    retmode="text"
                )
                abstract = fetch.read()
                fetch.close()
                
                # Extract metadata from search term
                metadata = {
                    "source": f"PubMed PMID:{pmid}",
                    "pmid": pmid,
                    "search_term": search_term,
                    "year": "2024"  # Default year
                }
                
                # Infer population and condition from search term
                if "pediatric" in search_term.lower():
                    metadata["population"] = "pediatric"
                else:
                    metadata["population"] = "adult"
                
                if "diabetes" in search_term.lower():
                    metadata["condition"] = "diabetes"
                    metadata["drug_class"] = "antidiabetic"
                elif "hypertension" in search_term.lower():
                    metadata["condition"] = "hypertension"
                    metadata["drug_class"] = "antihypertensive"
                elif "chest pain" in search_term.lower():
                    metadata["condition"] = "cardiac"
                    metadata["drug_class"] = "general"
                else:
                    metadata["condition"] = "general"
                    metadata["drug_class"] = "general"
                
                abstracts.append({
                    "content": abstract,
                    "metadata": metadata
                })
                
                # Respect rate limit
                time.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"Failed to fetch PMID {pmid}: {e}")
                continue
        
        logger.info(f"Fetched {len(abstracts)} abstracts for: {search_term}")
        return abstracts
        
    except Exception as e:
        logger.error(f"PubMed search failed for '{search_term}': {e}")
        return []


def load_corpus() -> Optional[Any]:
    """
    Load clinical guidelines corpus into ChromaDB
    
    Returns:
        ChromaDB collection or None if failed
    """
    if not CORPUS_AVAILABLE:
        logger.error("ChromaDB not available, cannot load corpus")
        return None
    
    try:
        # Create data directory
        data_dir = Path("data/chroma")
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        client = chromadb.PersistentClient(
            path=str(data_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        collection_name = "clinical_guidelines"
        try:
            collection = client.get_collection(name=collection_name)
            existing_count = collection.count()
            
            if existing_count > 0:
                logger.info(f"Corpus already loaded with {existing_count} documents")
                return collection
        except:
            # Collection doesn't exist, create it
            collection = client.create_collection(
                name=collection_name,
                metadata={"description": "Clinical practice guidelines corpus"}
            )
        
        logger.info("Loading corpus into ChromaDB...")
        
        # Collect all documents
        all_documents = []
        
        # Add hard-coded guidelines
        logger.info(f"Adding {len(HARDCODED_GUIDELINES)} hard-coded guidelines")
        all_documents.extend(HARDCODED_GUIDELINES)
        
        # Fetch PubMed abstracts
        logger.info("Fetching PubMed abstracts...")
        for search_term in PUBMED_SEARCH_TERMS:
            abstracts = fetch_pubmed_abstracts(search_term, max_results=3)
            all_documents.extend(abstracts)
            time.sleep(1)  # Rate limiting between searches
        
        # Add documents to collection
        if all_documents:
            documents = [doc["content"] for doc in all_documents]
            metadatas = [doc["metadata"] for doc in all_documents]
            ids = [f"doc_{i}" for i in range(len(all_documents))]
            
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            logger.info(f"Loaded {len(all_documents)} documents into corpus")
            logger.info(f"Corpus breakdown: {len(HARDCODED_GUIDELINES)} hard-coded + {len(all_documents) - len(HARDCODED_GUIDELINES)} PubMed")
        else:
            logger.warning("No documents to load")
        
        return collection
        
    except Exception as e:
        logger.error(f"Failed to load corpus: {e}")
        return None


# Global collection instance
_collection = None


def get_corpus_collection() -> Optional[Any]:
    """Get or create corpus collection"""
    global _collection
    if _collection is None:
        _collection = load_corpus()
    return _collection


# Made with Bob