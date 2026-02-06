
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from kgbuilder.storage.ontology import FusekiOntologyService
from kgbuilder.storage.neo4j_store import Neo4jGraphStore
from kgbuilder.analytics.inference import Neo4jInferenceEngine

def test_inference():
    load_dotenv()
    
    # Initialize services (using .env settings)
    ontology_service = FusekiOntologyService(
        fuseki_url=os.getenv("FUSEKI_URL") or os.getenv("KGBUILDER_ONTOLOGY_URL", "http://localhost:3030"),
        dataset_name=os.getenv("KGBUILDER_ONTOLOGY_DATASET", "kgbuilder"),
    )
    
    graph_store = Neo4jGraphStore(
        uri=os.getenv("NEO4J_URI") or os.getenv("KGBUILDER_NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USER") or os.getenv("KGBUILDER_NEO4J_USER", "neo4j"), 
            os.getenv("NEO4J_PASSWORD") or os.getenv("KGBUILDER_NEO4J_PASSWORD", "changeme")
        ),
        database=os.getenv("NEO4J_DATABASE") or os.getenv("KGBUILDER_NEO4J_DATABASE", "neo4j"),
    )
    
    engine = Neo4jInferenceEngine(graph_store, ontology_service)
    
    print("--- Testing Metadata Fetch ---")
    characteristics = ontology_service.get_special_properties()
    print(f"Symmetric Properties: {characteristics.get('symmetric')}")
    print(f"Inverse Property Pairs: {characteristics.get('inverse')}")
    print(f"Transitive Properties: {characteristics.get('transitive')}")
    
    hierarchy = ontology_service.get_class_hierarchy()
    print(f"Class Hierarchy Sample: {hierarchy[:5] if hierarchy else 'None'}")
    
    print("\n--- Running Inference ---")
    stats = engine.run_full_inference()
    print(f"Inference Stats: {stats}")

if __name__ == "__main__":
    test_inference()
