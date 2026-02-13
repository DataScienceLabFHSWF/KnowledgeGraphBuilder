#!/usr/bin/env python3
"""Cross-Domain KG Linking Script.

Creates explicit links between decommissioning KG entities and law graph entities.
Establishes governance and definitional relationships between domains.

Usage:
    python scripts/link_kg_to_laws.py --dry-run                    # Preview links
    python scripts/link_kg_to_laws.py --create-links              # Create links
    python scripts/link_kg_to_laws.py --visualize                 # Generate viz query

Environment variables:
    NEO4J_PASSWORD - Neo4j password
    PYTHONPATH - must include src/
"""

import argparse
import json
import os
import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple

import structlog
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = structlog.get_logger(__name__)


class KGLawLinker:
    """Creates cross-domain links between decommissioning KG and law graph."""

    def __init__(
        self,
        neo4j_uri: str = None,
        neo4j_user: str = None,
        database: str = "neo4j",  # Single database to use
        link_prefix: str = "LINKED_",  # Prefix for linked relationships
    ):
        # Load from environment variables with defaults
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_password = os.environ.get("NEO4J_PASSWORD", "changeme")
        self.database = database
        self.link_prefix = link_prefix
        
        # Configurable law patterns - can be extended
        self.law_patterns = {
            'AtG': {
                'patterns': [r'\bAtG\b', r'\bAtomgesetz\b'],
                'full_name': 'Atomgesetz'
            },
            'BBergG': {
                'patterns': [r'\bBBergG\b', r'\bBundesberggesetz\b'],
                'full_name': 'Bundesberggesetz'
            },
            'BImSchG': {
                'patterns': [r'\bBImSchG\b', r'\bImmissionsschutzgesetz\b'],
                'full_name': 'Bundes-Immissionsschutzgesetz'
            },
            'KrWG': {
                'patterns': [r'\bKrWG\b', r'\bKreislaufwirtschaftsgesetz\b'],
                'full_name': 'Kreislaufwirtschaftsgesetz'
            },
            'StrlSchG': {
                'patterns': [r'\bStrlSchG\b', r'\bStrahlenschutzgesetz\b'],
                'full_name': 'Strahlenschutzgesetz'
            },
            'StrlSchV': {
                'patterns': [r'\bStrlSchV\b', r'\bStrahlenschutzverordnung\b'],
                'full_name': 'Strahlenschutzverordnung'
            }
        }
        
        # Entity type to relationship mapping
        self.governance_mappings = {
            'Facility': 'GOVERNED_BY',
            'Organization': 'GOVERNED_BY',
            'Process': 'GOVERNED_BY',
            'Activity': 'GOVERNED_BY',
            'NuclearMaterial': 'DEFINED_IN',
            'WasteCategory': 'DEFINED_IN',
            'Permit': 'GOVERNED_BY',
            'SafetySystem': 'GOVERNED_BY',
            'Regulation': 'GOVERNED_BY',
        }

    def get_decommissioning_entities(self) -> List[Dict]:
        """Retrieve all decommissioning KG entities."""
        driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )

        try:
            with driver.session(database=self.database) as session:
                # Get entities with evidence and source info
                query = """
                MATCH (n)
                WHERE NOT any(l IN labels(n) WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])
                AND n.label IS NOT NULL
                AND n.node_type IS NOT NULL
                RETURN n.id as id, n.label as label, n.node_type as entity_type,
                       n.confidence as confidence, n.properties as properties
                """
                result = session.run(query)
                entities = [dict(record) for record in result]
                logger.info(f"Retrieved {len(entities)} decommissioning entities")
                return entities
        finally:
            driver.close()

    def find_law_references_in_text(self, text: str) -> List[Dict]:
        """Find explicit law references in text with context."""
        references = []
        
        # Pattern for German law citations - ordered from most specific to least
        citation_patterns = [
            # § 7 Abs. 3 AtG (paragraph, subsection, law)
            (re.compile(r'§\s*(\d+[\w]*)\s+Abs\.?\s*(\d+[\w]*)\s+([A-Z][A-Za-z]+)', re.IGNORECASE), 
             lambda m: (f"{m.group(1)} Abs. {m.group(2)}", self._normalize_law_code(m.group(3)))),
            
            # § 4 Absatz 1 (paragraph, subsection)
            (re.compile(r'§\s*(\d+[\w]*)\s+Absatz\s+(\d+[\w]*)', re.IGNORECASE),
             lambda m: (f"{m.group(1)} Abs. {m.group(2)}", None)),
             
            # § 7 AtG (paragraph, law)
            (re.compile(r'§\s*(\d+[\w]*)\s+([A-Z][A-Za-z]+)', re.IGNORECASE),
             lambda m: (m.group(1), self._normalize_law_code(m.group(2)))),
             
            # § 29 StrlSchV (paragraph, ordinance)
            (re.compile(r'§\s*(\d+[\w]*)\s+([A-Z][A-Za-z]+)', re.IGNORECASE),
             lambda m: (m.group(1), self._normalize_law_code(m.group(2)))),
             
            # Art. 12 BBergG (article, law)
            (re.compile(r'Art\.?\s*(\d+[\w]*)\s+([A-Z][A-Za-z]+)', re.IGNORECASE),
             lambda m: (f"Art. {m.group(1)}", self._normalize_law_code(m.group(2)))),
             
            # Law codes and full names
            (re.compile(r'\b(Strahlenschutzgesetz|Atomgesetz|Berggesetz|Immissionsschutzgesetz|Kreislaufwirtschaftsgesetz)\b', re.IGNORECASE),
             lambda m: (None, self._normalize_law_code(m.group(1)))),
             
            (re.compile(r'\b(AtG|BBergG|BImSchG|KrWG|StrlSchG|StrSchG|StrVG|AtVfV|UVPG|StrlSchV)\b', re.IGNORECASE),
             lambda m: (None, self._normalize_law_code(m.group(1)))),
        ]
        
        for pattern, extractor in citation_patterns:
            for match in pattern.finditer(text):
                section, law_code = extractor(match)
                
                # Only include if it's a recognized law or we have a section reference
                if law_code and (law_code in self.law_patterns or law_code == 'StrlSchV'):
                    references.append({
                        'law_code': law_code,
                        'section': section,
                        'context': text[max(0, match.start()-50):match.end()+50].strip(),
                        'confidence': 0.95,  # High confidence for explicit citations
                        'type': 'explicit_citation'
                    })
                elif section and not law_code:
                    # If we have a section but no law code, try to infer from context
                    # This handles cases like "§ 4 Absatz 1" without the law name
                    references.append({
                        'law_code': 'AtG',  # Default to Atomic Energy Act for nuclear context
                        'section': section,
                        'context': text[max(0, match.start()-50):match.end()+50].strip(),
                        'confidence': 0.7,  # Lower confidence for inferred law
                        'type': 'explicit_citation'
                    })
        
        return references

    def _normalize_law_code(self, code: str) -> str:
        """Normalize law code abbreviations."""
        code = code.upper()
        mappings = {
            'STRSCHG': 'StrlSchG',
            'STRVG': 'StrVG', 
            'ATVFV': 'AtVfV',
            'UVPG': 'UVPG',
        }
        return mappings.get(code, code)

    def determine_relationship_type(self, entity_type: str, law_context: str) -> str:
        """Determine the appropriate relationship type."""
        # Check governance mappings
        if entity_type in self.governance_mappings:
            return self.governance_mappings[entity_type]

        # Default based on context
        if 'definition' in law_context.lower() or 'defined' in law_context.lower():
            return 'DEFINED_IN'
        elif 'permit' in law_context.lower() or 'approval' in law_context.lower():
            return 'REQUIRES'
        else:
            return 'GOVERNED_BY'

    def create_links(self, dry_run: bool = True) -> Dict:
        """Create cross-domain links between KG entities and laws with prefixed relationships."""
        entities = self.get_decommissioning_entities()
        links_created = []
        stats = defaultdict(int)

        driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )

        try:
            with driver.session(database=self.database) as session:
                for entity in entities:
                    entity_id = entity['id']
                    entity_label = entity['label']
                    entity_type = entity['entity_type']
                    
                    # Collect all text sources for explicit law reference detection
                    text_sources = [entity_label]
                    if entity.get('properties'):
                        import json
                        try:
                            props = json.loads(entity['properties']) if isinstance(entity['properties'], str) else entity['properties']
                            if isinstance(props, dict):
                                # Look for evidence, source_text, context, description, or other text fields
                                for key in ['evidence', 'source_text', 'context', 'description', 'text', 'content']:
                                    if key in props and props[key]:
                                        if isinstance(props[key], list):
                                            text_sources.extend([str(x) for x in props[key]])
                                        else:
                                            text_sources.append(str(props[key]))
                        except (json.JSONDecodeError, TypeError):
                            pass  # Skip if properties can't be parsed

                    # Find explicit law references in all text sources
                    explicit_refs = []
                    for text in text_sources:
                        if text:
                            refs = self.find_law_references_in_text(text)
                            explicit_refs.extend(refs)
                    
                    # Create links for explicit references
                    for ref in explicit_refs:
                        relationship_type = self.determine_relationship_type(
                            entity_type, ref.get('context', '')
                        )
                        
                        link = {
                            'source_entity': entity_id,
                            'target_law': ref['law_code'],
                            'relationship': relationship_type,
                            'confidence': ref['confidence'],
                            'reason': 'explicit_citation',
                            'section': ref.get('section'),
                            'context': ref.get('context')
                        }
                        links_created.append(link)
                        stats['explicit_citations'] += 1

                        if not dry_run:
                            self._create_relationship(session, link)

                    # Progress logging
                    if len(links_created) % 50 == 0:
                        logger.info(f"Processed {len(links_created)} links so far...")

        finally:
            driver.close()

        result = {
            'total_entities_processed': len(entities),
            'total_links_created': len(links_created),
            'stats': dict(stats),
            'links': links_created[:100]  # Sample of links
        }

        logger.info(f"Cross-domain linking complete: {len(links_created)} links created")
        return result

    def _create_relationship(self, session, link: Dict):
        """Create a relationship in Neo4j with prefixed relationship types."""
        relationship_type = f"{self.link_prefix}{link['relationship']}"
        
        if link['relationship'] in ['REFERENCES', 'GOVERNED_BY', 'DEFINED_IN', 'REQUIRES']:
            # All relationship types link to law codes (Gesetzbuch nodes)
            query = f"""
            MERGE (law:Gesetzbuch {{abbreviation: $law_code}})
            WITH law
            MATCH (entity) WHERE entity.id = $entity_id
            MERGE (entity)-[r:{relationship_type} {{confidence: $confidence}}]->(law)
            SET r.reason = $reason
            """
            if link.get('section'):
                query = query.replace("SET r.reason = $reason", "SET r.reason = $reason, r.section = $section")
            if link.get('context'):
                query = query.replace("SET r.reason = $reason", "SET r.reason = $reason, r.context = $context")
            
            params = {
                'entity_id': link['source_entity'],
                'law_code': link['target_law'],
                'confidence': link['confidence'],
                'reason': link['reason']
            }
            if link.get('section'):
                params['section'] = link['section']
            if link.get('context'):
                params['context'] = link['context']
                
            session.run(query, **params)

        else:
            raise ValueError(f"Unsupported relationship type: {link['relationship']}")

    def generate_visualization_query(self) -> str:
        """Generate a Neo4j Browser query for visualizing cross-domain links."""
        query = """
// Cross-Domain KG-Law Links Visualization
MATCH (n)-[r:REFERENCES|GOVERNED_BY|DEFINED_IN|REQUIRES]->(law)
WHERE NOT any(l IN labels(n) WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])
RETURN n, r, law
LIMIT 100
        """
        return query.strip()

    def get_link_statistics(self) -> Dict:
        """Get statistics about existing cross-domain links with prefixed relationship types."""
        driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )

        try:
            with driver.session(database=self.database) as session:
                # Use prefixed relationship types
                prefixed_types = [f"{self.link_prefix}{t}" for t in ['REFERENCES', 'GOVERNED_BY', 'DEFINED_IN', 'REQUIRES']]
                rel_types_str = '|'.join(prefixed_types)
                
                query = f"""
                MATCH (n)-[r:{rel_types_str}]->(law)
                WHERE NOT any(l IN labels(n) WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])
                RETURN type(r) as rel_type, count(*) as count
                ORDER BY count DESC
                """
                result = session.run(query)
                stats = {record['rel_type']: record['count'] for record in result}

                total_query = f"""
                MATCH (n)-[r:{rel_types_str}]->(law)
                WHERE NOT any(l IN labels(n) WHERE l IN ['Paragraf', 'Abschnitt', 'Gesetzbuch'])
                RETURN count(r) as total
                """
                total_result = session.run(total_query).single()
                stats['total'] = total_result['total'] if total_result else 0

                return stats
        finally:
            driver.close()


def main():
    parser = argparse.ArgumentParser(description="Create cross-domain links between KG and law graph")
    parser.add_argument("--dry-run", action="store_true",
                       help="Preview links without creating them")
    parser.add_argument("--create-links", action="store_true",
                       help="Create the cross-domain links with prefixed relationship types")
    parser.add_argument("--visualize", action="store_true",
                       help="Generate visualization query")
    parser.add_argument("--stats", action="store_true",
                       help="Show existing link statistics")
    parser.add_argument("--database", default="neo4j",
                       help="Neo4j database to use")
    parser.add_argument("--link-prefix", default="LINKED_",
                       help="Prefix for linked relationship types")

    args = parser.parse_args()

    linker = KGLawLinker(
        database=args.database,
        link_prefix=args.link_prefix
    )

    if args.stats:
        stats = linker.get_link_statistics()
        print("Existing Cross-Domain Links:")
        print(json.dumps(stats, indent=2))
        return

    if args.visualize:
        query = linker.generate_visualization_query()
        print("Neo4j Browser Visualization Query:")
        print(query)
        return

    if args.dry_run or args.create_links:
        result = linker.create_links(dry_run=args.dry_run)

        print(f"Entities processed: {result['total_entities_processed']}")
        print(f"Links created: {result['total_links_created']}")
        print(f"Statistics: {json.dumps(result['stats'], indent=2)}")

        if result['links']:
            print("\nSample links:")
            for link in result['links'][:10]:
                target = link.get('target_paragraph', link.get('target_law', 'unknown'))
                print(f"  {link['source_entity']} -[{link['relationship']}]-> {target}")

        if args.dry_run:
            print("\nThis was a dry run. Use --create-links to actually create the relationships.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()