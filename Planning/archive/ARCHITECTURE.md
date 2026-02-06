# 🏛️ KnowledgeGraphBuilder – System Architecture

> **Version**: 1.0  
> **Last Updated**: 2026-01-30

---

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        KNOWLEDGE GRAPH BUILDER SYSTEM                                           │
│                                           (This Repository Scope)                                               │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                              INPUT LAYER                                                         │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                      │
│    │    PDF      │   │    DOCX     │   │    PPTX     │   │     TXT     │   │   Markdown  │                      │
│    │  Documents  │   │  Documents  │   │   Slides    │   │    Files    │   │    Files    │                      │
│    └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘                      │
│           │                 │                 │                 │                 │                              │
│           └─────────────────┴─────────────────┴─────────────────┴─────────────────┘                              │
│                                               │                                                                   │
│                                               ▼                                                                   │
│                              ┌────────────────────────────────┐                                                  │
│                              │      DOCUMENT LOADER FACTORY    │                                                  │
│                              │   (Unified Ingestion Interface) │                                                  │
│                              └────────────────────────────────┘                                                  │
│                                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         DOCUMENT PROCESSING LAYER                                                │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│   ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐    │
│   │                                    CHUNKING ENGINE                                                      │    │
│   │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐               │    │
│   │  │  Fixed Size      │  │   Semantic       │  │   Structural     │  │  Hierarchical    │               │    │
│   │  │  Chunker         │  │   Chunker        │  │   Chunker        │  │  Chunker         │               │    │
│   │  │  (Token-based)   │  │   (Paragraph)    │  │   (Section)      │  │  (Nested)        │               │    │
│   │  └──────────────────┘  └──────────────────┘  └──────────────────┘  └──────────────────┘               │    │
│   └────────────────────────────────────────────────────────────────────────────────────────────────────────┘    │
│                                               │                                                                   │
│                                               ▼                                                                   │
│   ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐    │
│   │                                 METADATA ENRICHMENT                                                     │    │
│   │            (Source tracking, Section info, Page numbers, Timestamps, Confidence)                        │    │
│   └────────────────────────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
┌──────────────────────────────────────────┐      ┌──────────────────────────────────────────┐
│         EMBEDDING LAYER                  │      │        GIVEN INPUTS (External)           │
├──────────────────────────────────────────┤      ├──────────────────────────────────────────┤
│                                          │      │                                          │
│  ┌────────────────────────────────────┐  │      │  ┌────────────────────────────────────┐  │
│  │    OLLAMA EMBEDDING PROVIDER       │  │      │  │       ONTOLOGY (OWL/RDF)           │  │
│  │  ┌──────────────────────────────┐  │  │      │  │  - Classes & Hierarchy             │  │
│  │  │  nomic-embed-text            │  │  │      │  │  - Relations & Properties          │  │
│  │  │  mxbai-embed-large           │  │  │      │  │  - Constraints (Domain/Range)      │  │
│  │  │  all-minilm                  │  │  │      │  │  - Axioms                          │  │
│  │  │  (Configurable)              │  │  │      │  └────────────────────────────────────┘  │
│  │  └──────────────────────────────┘  │  │      │                                          │
│  └────────────────────────────────────┘  │      │  ┌────────────────────────────────────┐  │
│                    │                     │      │  │    COMPETENCY QUESTIONS (CQs)      │  │
│                    ▼                     │      │  │  - What should the KG answer?      │  │
│  ┌────────────────────────────────────┐  │      │  │  - Validation criteria             │  │
│  │        VECTOR DATABASE             │  │      │  │  - Coverage requirements           │  │
│  │  ┌──────────────────────────────┐  │  │      │  └────────────────────────────────────┘  │
│  │  │ Primary: Qdrant (Production) │  │  │      │                                          │
│  │  │ Alt: ChromaDB (Development)  │  │  │      │  ┌────────────────────────────────────┐  │
│  │  │ Alt: Milvus (Scale)          │  │  │      │  │     SHACL SHAPES (Validation)      │  │
│  │  └──────────────────────────────┘  │  │      │  │  - Constraint definitions          │  │
│  │  Features:                        │  │      │  │  - Cardinality rules               │  │
│  │  - Hybrid search (dense+sparse)   │  │      │  │  - Pattern constraints             │  │
│  │  - Metadata filtering             │  │      │  └────────────────────────────────────┘  │
│  │  - Persistence                    │  │      │                                          │
│  └────────────────────────────────────┘  │      └──────────────────────────────────────────┘
│                                          │
└──────────────────────────────────────────┘
                       │                                               │
                       └───────────────────────┬───────────────────────┘
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            LLM LAYER (OLLAMA)                                                    │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                     OLLAMA ORCHESTRATION                                                 │   │
│   │                                                                                                          │   │
│   │    ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐                        │   │
│   │    │   Small Models      │    │   Medium Models     │    │   Large Models      │                        │   │
│   │    │   (Development)     │    │   (Testing)         │    │   (Production)      │                        │   │
│   │    │   - Phi-3           │    │   - Mistral 7B      │    │   - Llama 3.1 70B   │                        │   │
│   │    │   - Qwen2 1.5B      │    │   - Qwen2 7B        │    │   - DeepSeek 67B    │                        │   │
│   │    │   - Gemma 2B        │    │   - Gemma 7B        │    │   - Mixtral 8x22B   │                        │   │
│   │    └─────────────────────┘    └─────────────────────┘    └─────────────────────┘                        │   │
│   │                                                                                                          │   │
│   │    Features:                                                                                             │   │
│   │    ✓ Structured Output (JSON Mode)                                                                       │   │
│   │    ✓ Tool Calling / Function Calling                                                                     │   │
│   │    ✓ Streaming Responses                                                                                 │   │
│   │    ✓ Model Hot-Swapping                                                                                  │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        AGENTIC ORCHESTRATION LAYER                                               │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│    ┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐            │
│    │  QUESTION-ASKING  │    │   DEEP RESEARCH   │    │    KG BUILDER     │    │   VALIDATION      │            │
│    │      AGENT        │───▶│      AGENT        │───▶│      AGENT        │───▶│      AGENT        │            │
│    │                   │    │                   │    │                   │    │                   │            │
│    │ - Generate Qs     │    │ - Vector search   │    │ - Entity extract  │    │ - SHACL check     │            │
│    │   from Ontology   │    │ - Synthesize      │    │ - Relation extract│    │ - Ontology check  │            │
│    │ - Prioritize by   │    │   findings        │    │ - Deduplicate     │    │ - CQ validation   │            │
│    │   coverage        │    │ - Cite sources    │    │ - Assemble KG     │    │ - Gap detection   │            │
│    │ - Adaptive        │    │ - Confidence      │    │ - Provenance      │    │ - Fix suggestions │            │
│    └───────────────────┘    └───────────────────┘    └───────────────────┘    └───────────────────┘            │
│           │                         │                         │                         │                       │
│           │                         │                         │                         │                       │
│           │    ┌────────────────────┴─────────────────────────┴─────────────────────────┘                       │
│           │    │                              │                                                                  │
│           │    │    ┌─────────────────────────────────────────────────────────────────┐                         │
│           │    │    │                    TOOL REGISTRY                                 │                         │
│           │    │    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │                         │
│           │    └───▶│  │VectorSearch │  │OntologyQuery│  │  KGQuery    │  │Validator│ │                         │
│           │         │  │    Tool     │  │    Tool     │  │   Tool      │  │  Tool   │ │                         │
│           │         │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │                         │
│           │         └─────────────────────────────────────────────────────────────────┘                         │
│           │                                                                                                      │
│           └─────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│                                                                                                              │   │
│                                    FEEDBACK LOOP (Iterative Refinement)                                ◀────┘   │
│                                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                          KNOWLEDGE EXTRACTION LAYER                                              │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│   ┌────────────────────────────────────┐          ┌────────────────────────────────────┐                        │
│   │       ENTITY EXTRACTOR             │          │      RELATION EXTRACTOR            │                        │
│   │                                    │          │                                    │                        │
│   │  ┌──────────────────────────────┐  │          │  ┌──────────────────────────────┐  │                        │
│   │  │  Ontology-Guided Prompting   │  │          │  │  Ontology-Guided Prompting   │  │                        │
│   │  │  - Class descriptions        │  │          │  │  - Valid relation types      │  │                        │
│   │  │  - Few-shot examples         │  │          │  │  - Domain/range constraints  │  │                        │
│   │  │  - Constraint hints          │  │          │  │  - Cardinality hints         │  │                        │
│   │  └──────────────────────────────┘  │          │  └──────────────────────────────┘  │                        │
│   │                                    │          │                                    │                        │
│   │  Output:                           │          │  Output:                           │                        │
│   │  - Entity ID                       │          │  - Relation ID                     │                        │
│   │  - Label & Type                    │          │  - Source/Target Entity            │                        │
│   │  - Description                     │          │  - Predicate                       │                        │
│   │  - Confidence Score                │          │  - Confidence Score                │                        │
│   │  - Evidence References             │          │  - Evidence References             │                        │
│   └────────────────────────────────────┘          └────────────────────────────────────┘                        │
│                                                                                                                  │
│   ┌────────────────────────────────────────────────────────────────────────────────────┐                        │
│   │                           FINDINGS SYNTHESIZER                                      │                        │
│   │                                                                                     │                        │
│   │   Output Format (YAML):                                                             │                        │
│   │   ┌──────────────────────────────────────────────────────────────────────────────┐ │                        │
│   │   │  finding_id: FR-0231                                                         │ │                        │
│   │   │  ontology_concepts: [RootCause, CorrectiveAction]                            │ │                        │
│   │   │  question: "What are common root causes?"                                    │ │                        │
│   │   │  claims:                                                                     │ │                        │
│   │   │    - text: "Root causes often categorized as people, process, system..."    │ │                        │
│   │   │      confidence: 0.82                                                        │ │                        │
│   │   │      evidence:                                                               │ │                        │
│   │   │        - source_type: local_doc                                              │ │                        │
│   │   │          chunk_id: DOC-112-CH-7                                              │ │                        │
│   │   └──────────────────────────────────────────────────────────────────────────────┘ │                        │
│   └────────────────────────────────────────────────────────────────────────────────────┘                        │
│                                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            KG ASSEMBLY LAYER                                                     │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│    ┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐     │
│    │   ENTITY           │     │    ENTITY          │     │    GRAPH           │     │   PROVENANCE       │     │
│    │   RESOLUTION       │────▶│    MERGING         │────▶│    ASSEMBLY        │────▶│   ATTACHMENT       │     │
│    │                    │     │                    │     │                    │     │                    │     │
│    │ - Fuzzy matching   │     │ - Attribute merge  │     │ - Node creation    │     │ - Source links     │     │
│    │ - Embedding sim    │     │ - Conflict resolve │     │ - Edge creation    │     │ - Confidence       │     │
│    │ - Coreference      │     │ - Confidence agg   │     │ - Constraint check │     │ - Timestamps       │     │
│    └────────────────────┘     └────────────────────┘     └────────────────────┘     └────────────────────┘     │
│                                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           VALIDATION LAYER                                                       │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│    ┌────────────────────────────┐    ┌────────────────────────────┐    ┌────────────────────────────┐          │
│    │    ONTOLOGY VALIDATOR      │    │     SHACL VALIDATOR        │    │    CQ VALIDATOR            │          │
│    │                            │    │                            │    │                            │          │
│    │  - Class membership        │    │  - Shape constraints       │    │  - CQ → SPARQL             │          │
│    │  - Domain/range            │    │  - Cardinality             │    │  - Execute queries         │          │
│    │  - Property characteristics│    │  - Pattern matching        │    │  - Coverage scoring        │          │
│    │  - Consistency             │    │  - Severity levels         │    │  - Gap identification      │          │
│    └────────────────────────────┘    └────────────────────────────┘    └────────────────────────────┘          │
│                       │                         │                                │                               │
│                       └─────────────────────────┴────────────────────────────────┘                               │
│                                                 │                                                                 │
│                                                 ▼                                                                 │
│                              ┌───────────────────────────────────────┐                                           │
│                              │        VALIDATION REPORT              │                                           │
│                              │  - Violations (Error/Warning/Info)    │                                           │
│                              │  - Coverage metrics                   │                                           │
│                              │  - Suggestions for fixes              │                                           │
│                              │  - Refinement triggers                │                                           │
│                              └───────────────────────────────────────┘                                           │
│                                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            STORAGE LAYER                                                         │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│    ┌─────────────────────────────────────┐         ┌─────────────────────────────────────┐                      │
│    │          GRAPH DATABASE             │         │           RDF STORE                 │                      │
│    │                                     │         │                                     │                      │
│    │    ┌───────────────────────────┐    │         │    ┌───────────────────────────┐    │                      │
│    │    │         NEO4J             │    │         │    │    Apache Jena / Fuseki   │    │                      │
│    │    │   (Primary Graph Store)   │    │         │    │      (RDF/SPARQL)         │    │                      │
│    │    │                           │    │         │    │                           │    │                      │
│    │    │   - Cypher queries        │    │         │    │   - SPARQL endpoint       │    │                      │
│    │    │   - Graph traversal       │    │         │    │   - OWL reasoning         │    │                      │
│    │    │   - Path finding          │    │         │    │   - Inference             │    │                      │
│    │    │   - Community detection   │    │         │    │   - Standard compliance   │    │                      │
│    │    └───────────────────────────┘    │         │    └───────────────────────────┘    │                      │
│    │                                     │         │                                     │                      │
│    │    Alt: NetworkX (In-memory)        │         │    Alt: Oxigraph (Lightweight)      │                      │
│    └─────────────────────────────────────┘         └─────────────────────────────────────┘                      │
│                                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            OUTPUT/EXPORT LAYER                                                   │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│    │   JSON-LD   │  │    YARRRML  │  │ RDF/Turtle  │  │   Cypher    │  │   GraphML   │  │  N-Triples  │        │
│    │  (Web/API)  │  │  (Mapping)  │  │  (Semantic) │  │ (Neo4j Imp) │  │  (Analysis) │  │   (Bulk)    │        │
│    └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                                                                                  │
│    Export Features:                                                                                              │
│    ✓ Full provenance preservation                                                                                │
│    ✓ Schema validation before export                                                                             │
│    ✓ Selective export (subgraph, by type, by confidence)                                                         │
│    ✓ Round-trip capable                                                                                          │
│                                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               │
                                               ▼
┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
                                     EXTERNAL SYSTEMS (Other Repo)                                                  
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
                                                                                                                    
│   ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐    │
    │                                       GraphRAG / QA SYSTEM                                              │     
│   │                                                                                                         │    │
    │   ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐                        │     
│   │   │   QA AGENT          │    │  SUBGRAPH RETRIEVER │    │  ANSWER GENERATOR   │                        │    │
    │   │                     │    │                     │    │                     │                        │     
│   │   │  - Query parsing    │───▶│  - Entity lookup    │───▶│  - Context assembly │                        │    │
    │   │  - Intent detection │    │  - Path traversal   │    │  - LLM generation   │                        │     
│   │   │  - Multi-hop        │    │  - Hybrid search    │    │  - Citation         │                        │    │
    │   └─────────────────────┘    └─────────────────────┘    └─────────────────────┘                        │     
│   │                                                                                                         │    │
    └────────────────────────────────────────────────────────────────────────────────────────────────────────┘     
│                                                                                                                  │
    ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐     
│   │                                       FRONTEND APPLICATION                                              │    │
    │                                                                                                         │     
│   │   ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐                        │    │
    │   │   GRAPH EXPLORER    │    │   CHATBOT INTERFACE │    │  EXPLANATION VIEW   │                        │     
│   │   │                     │    │                     │    │                     │                        │    │
    │   │  - Visual graph     │    │  - Natural language │    │  - Reasoning trace  │                        │     
│   │   │  - Entity inspect   │    │  - Follow-up Qs     │    │  - Source links     │                        │    │
    │   │  - Filtering        │    │  - Conversation     │    │  - Confidence       │                        │     
│   │   └─────────────────────┘    └─────────────────────┘    └─────────────────────┘                        │    │
    │                                                                                                         │     
│   └────────────────────────────────────────────────────────────────────────────────────────────────────────┘    │
                                                                                                                    
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

---

## Component Interaction Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW SEQUENCE                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘

    Documents          Ontology/CQs           Agents              KG Store           Exports
        │                   │                   │                    │                  │
        │   1. Ingest       │                   │                    │                  │
        │──────────────────▶│                   │                    │                  │
        │   (Load, Chunk,   │                   │                    │                  │
        │    Embed, Index)  │                   │                    │                  │
        │                   │                   │                    │                  │
        │                   │  2. Initialize    │                    │                  │
        │                   │──────────────────▶│                    │                  │
        │                   │  (Load ontology,  │                    │                  │
        │                   │   prepare CQs)    │                    │                  │
        │                   │                   │                    │                  │
        │                   │                   │  3. Research       │                  │
        │◀──────────────────│◀──────────────────│                    │                  │
        │   (Query vectors) │  (Guided by       │                    │                  │
        │                   │   ontology)       │                    │                  │
        │                   │                   │                    │                  │
        │                   │                   │  4. Extract        │                  │
        │                   │                   │──────────────────▶ │                  │
        │                   │                   │  (Entities,        │                  │
        │                   │                   │   Relations)       │                  │
        │                   │                   │                    │                  │
        │                   │                   │  5. Validate       │                  │
        │                   │◀──────────────────│◀───────────────────│                  │
        │                   │  (SHACL, CQ       │  (Check graph)     │                  │
        │                   │   coverage)       │                    │                  │
        │                   │                   │                    │                  │
        │                   │                   │  6. Refine         │                  │
        │                   │                   │──────────────────▶ │                  │
        │                   │                   │  (Fix violations,  │                  │
        │                   │                   │   fill gaps)       │                  │
        │                   │                   │                    │                  │
        │                   │                   │                    │  7. Export       │
        │                   │                   │                    │─────────────────▶│
        │                   │                   │                    │  (JSON-LD,       │
        │                   │                   │                    │   YARRRML, etc)  │
        │                   │                   │                    │                  │
        ▼                   ▼                   ▼                    ▼                  ▼
```

---

## Technology Stack Summary

| Component | Primary Choice | Alternatives | Rationale |
|-----------|---------------|--------------|-----------|
| **Language** | Python 3.11+ | - | Type hints, async, ecosystem |
| **LLM Orchestration** | Ollama | LM Studio | Local, open-source, tool calling |
| **Embeddings** | Ollama (nomic-embed) | Sentence Transformers | Unified with LLM provider |
| **Vector DB** | Qdrant | ChromaDB, Milvus | Hybrid search, filtering, scale |
| **Graph DB** | Neo4j | - | Cypher, mature, visualization |
| **RDF Store** | Apache Jena/Fuseki | Oxigraph | SPARQL, reasoning, standards |
| **Validation** | pySHACL | - | Python native, well-maintained |
| **Agent Framework** | Custom + LangGraph | - | Flexibility, observability |
| **Config** | Pydantic + YAML | Dynaconf | Validation, type safety |
| **CLI** | Typer | Click | Modern, type hints |
| **Testing** | Pytest | - | Fixtures, plugins, coverage |
| **Docs** | MkDocs | Sphinx | Material theme, simple |

---

## Vector Database Recommendation

### Primary: **Qdrant**

**Why Qdrant?**
- ✅ **Hybrid search** - Dense + sparse vectors out of the box
- ✅ **Filtering** - Rich metadata filtering with payload indexes
- ✅ **Scalability** - Handles millions of vectors
- ✅ **Self-hosted** - Full control, no vendor lock-in
- ✅ **Python SDK** - First-class Python support
- ✅ **Persistence** - Disk-based with memory mapping
- ✅ **REST + gRPC** - Multiple API options

### Development Alternative: **ChromaDB**

**Why for dev?**
- ✅ Embedded mode (no server needed)
- ✅ Simple API
- ✅ Good for prototyping
- ⚠️ Limited at scale

### Enterprise Alternative: **Milvus**

**Why for enterprise?**
- ✅ Distributed architecture
- ✅ GPU acceleration
- ✅ Strong consistency
- ⚠️ More complex setup

---

## Deployment Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                    DOCKER COMPOSE STACK                            │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│   ┌──────────────────┐    ┌──────────────────┐                    │
│   │   kgbuilder      │    │     ollama       │                    │
│   │   (Python App)   │◀──▶│   (LLM Server)   │                    │
│   │                  │    │                  │                    │
│   │   Port: 8000     │    │   Port: 11434    │                    │
│   └────────┬─────────┘    └──────────────────┘                    │
│            │                                                       │
│            │                                                       │
│   ┌────────┴─────────┐                                            │
│   │                  │                                            │
│   ▼                  ▼                                            │
│   ┌──────────────────┐    ┌──────────────────┐                    │
│   │     qdrant       │    │      neo4j       │                    │
│   │  (Vector Store)  │    │   (Graph DB)     │                    │
│   │                  │    │                  │                    │
│   │   Port: 6333     │    │   Port: 7474     │                    │
│   └──────────────────┘    │   Port: 7687     │                    │
│                           └──────────────────┘                    │
│                                                                    │
│   ┌──────────────────┐                                            │
│   │     fuseki       │    (Optional)                              │
│   │   (RDF Store)    │                                            │
│   │                  │                                            │
│   │   Port: 3030     │                                            │
│   └──────────────────┘                                            │
│                                                                    │
│   Volumes:                                                         │
│   - ./data/qdrant:/qdrant/storage                                 │
│   - ./data/neo4j:/data                                            │
│   - ./data/ollama:/root/.ollama                                   │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Security Considerations

1. **API Keys**: Store in environment variables, never in code
2. **Network**: Internal Docker network for DB communication
3. **Data**: Encrypted volumes for sensitive documents
4. **Auth**: Neo4j authentication enabled, Qdrant API key optional
5. **Logging**: Redact sensitive content in logs

---

## Observability Stack

```
Logging:     structlog → JSON → stdout → (optional) ELK/Loki
Metrics:     prometheus-client → /metrics endpoint
Tracing:     OpenTelemetry → Jaeger (optional)
Monitoring:  Grafana dashboards (optional)
```

---

## Experiment Tracking & Comparison Framework

### Research Comparison Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    EXPERIMENT & COMPARISON FRAMEWORK                                             │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                    EXPERIMENT CONFIGURATION                                              │   │
│   │                                                                                                          │   │
│   │    ┌───────────────────────┐    ┌───────────────────────┐    ┌───────────────────────┐                  │   │
│   │    │   Ontology Versions   │    │    CQ Versions        │    │   RAG Variant Config  │                  │   │
│   │    │                       │    │                       │    │                       │                  │   │
│   │    │  v1.0 (Base)          │    │  v1.0 (Base CQs)      │    │  - classic            │                  │   │
│   │    │  v1.1 (Extended)      │    │  v1.1 (Extended CQs)  │    │  - kg_only            │                  │   │
│   │    │  v2.0 (Major update)  │    │  v2.0 (Revised CQs)   │    │  - hybrid             │                  │   │
│   │    └───────────────────────┘    └───────────────────────┘    └───────────────────────┘                  │   │
│   │                                                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                   │                                                              │
│                                                   ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                     EXPERIMENT RUNNER                                                    │   │
│   │                                                                                                          │   │
│   │    ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐  │   │
│   │    │                         KG BUILDING EXPERIMENT                                                   │  │   │
│   │    │                                                                                                  │  │   │
│   │    │   Iteration 1 ──▶ Iteration 2 ──▶ Iteration 3 ──▶ ... ──▶ Iteration N (Converged)               │  │   │
│   │    │       │               │               │                         │                                │  │   │
│   │    │       ▼               ▼               ▼                         ▼                                │  │   │
│   │    │   ┌───────┐       ┌───────┐       ┌───────┐                ┌───────┐                            │  │   │
│   │    │   │Metrics│       │Metrics│       │Metrics│                │Metrics│                            │  │   │
│   │    │   └───────┘       └───────┘       └───────┘                └───────┘                            │  │   │
│   │    │                                                                                                  │  │   │
│   │    └─────────────────────────────────────────────────────────────────────────────────────────────────┘  │   │
│   │                                                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                   │                                                              │
│                                                   ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                    METRICS COLLECTOR                                                     │   │
│   │                                                                                                          │   │
│   │   Per-Iteration Metrics:                                                                                 │   │
│   │   ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐        │   │
│   │   │   Graph State      │  │   Validation       │  │   Extraction       │  │   Research         │        │   │
│   │   │                    │  │                    │  │                    │  │                    │        │   │
│   │   │ • Node count       │  │ • SHACL violations │  │ • Avg confidence   │  │ • Questions asked  │        │   │
│   │   │ • Edge count       │  │ • Ontology errors  │  │ • Entity count     │  │ • Findings made    │        │   │
│   │   │ • New nodes/edges  │  │ • CQ coverage %    │  │ • Relation count   │  │ • Sources used     │        │   │
│   │   │ • Merged entities  │  │ • Per-CQ scores    │  │ • Low confidence # │  │ • Web queries      │        │   │
│   │   └────────────────────┘  └────────────────────┘  └────────────────────┘  └────────────────────┘        │   │
│   │                                                                                                          │   │
│   │   Graph Quality Metrics:                                                                                 │   │
│   │   ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐        │   │
│   │   │   Structural       │  │   Coverage         │  │   Convergence      │  │   Quality          │        │   │
│   │   │                    │  │                    │  │                    │  │                    │        │   │
│   │   │ • Connected comps  │  │ • Class coverage   │  │ • Iterations to    │  │ • Orphan nodes     │        │   │
│   │   │ • Avg degree       │  │ • Relation coverage│  │   convergence      │  │ • Duplicate ratio  │        │   │
│   │   │ • Density          │  │ • CQ answerability │  │ • Marginal gain    │  │ • Confidence dist  │        │   │
│   │   │ • Centrality       │  │ • Document coverage│  │ • Stability score  │  │ • Evidence depth   │        │   │
│   │   └────────────────────┘  └────────────────────┘  └────────────────────┘  └────────────────────┘        │   │
│   │                                                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                   │                                                              │
│                                                   ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                   METRICS STORAGE (SQLite + JSON)                                        │   │
│   │                                                                                                          │   │
│   │   experiments/                                                                                           │   │
│   │   ├── experiment_001/                                                                                    │   │
│   │   │   ├── config.json           # Full experiment configuration                                          │   │
│   │   │   ├── ontology_v1.0.owl     # Ontology snapshot                                                      │   │
│   │   │   ├── cqs_v1.0.json         # CQ snapshot                                                            │   │
│   │   │   ├── iterations/                                                                                    │   │
│   │   │   │   ├── iter_001.json     # Metrics for iteration 1                                                │   │
│   │   │   │   ├── iter_002.json     # Metrics for iteration 2                                                │   │
│   │   │   │   └── ...                                                                                        │   │
│   │   │   ├── final_kg_stats.json   # Final graph statistics                                                 │   │
│   │   │   └── kg_export/            # Exported KG snapshots                                                  │   │
│   │   └── experiment_002/                                                                                    │   │
│   │                                                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### RAG Variant Comparison Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        RAG VARIANT COMPARISON                                                    │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│                                         QA EVALUATION DATASET                                                    │
│                                     (Provided Question-Answer Pairs)                                             │
│                                                   │                                                              │
│                    ┌──────────────────────────────┼──────────────────────────────┐                              │
│                    │                              │                              │                              │
│                    ▼                              ▼                              ▼                              │
│   ┌────────────────────────────┐  ┌────────────────────────────┐  ┌────────────────────────────┐               │
│   │     VARIANT A              │  │     VARIANT B              │  │     VARIANT C              │               │
│   │  Classic AgenticRAG        │  │  Hybrid AgenticRAG         │  │  KG-Only AgenticRAG        │               │
│   │                            │  │                            │  │                            │               │
│   │  ┌──────────────────────┐  │  │  ┌──────────────────────┐  │  │  ┌──────────────────────┐  │               │
│   │  │                      │  │  │  │                      │  │  │  │                      │  │               │
│   │  │    Vector Store      │  │  │  │    Vector Store      │  │  │  │   Knowledge Graph    │  │               │
│   │  │       ONLY           │  │  │  │        +             │  │  │  │       ONLY           │  │               │
│   │  │                      │  │  │  │   Knowledge Graph    │  │  │  │                      │  │               │
│   │  └──────────────────────┘  │  │  └──────────────────────┘  │  │  └──────────────────────┘  │               │
│   │                            │  │                            │  │                            │               │
│   │  Retrieval:                │  │  Retrieval:                │  │  Retrieval:                │               │
│   │  • Semantic search         │  │  • Semantic search         │  │  • Entity lookup           │               │
│   │  • Top-k chunks            │  │  • Entity lookup           │  │  • Subgraph traversal      │               │
│   │                            │  │  • Subgraph expansion      │  │  • Path finding            │               │
│   │                            │  │  • Hybrid ranking          │  │  • Cypher queries          │               │
│   └────────────────────────────┘  └────────────────────────────┘  └────────────────────────────┘               │
│                    │                              │                              │                              │
│                    └──────────────────────────────┼──────────────────────────────┘                              │
│                                                   ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                      QA EVALUATION ENGINE                                                │   │
│   │                                                                                                          │   │
│   │   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐   │   │
│   │   │                                    METRICS                                                       │   │   │
│   │   │                                                                                                  │   │   │
│   │   │  Accuracy Metrics         RAG Metrics (deepeval)       Reasoning Metrics      Efficiency         │   │   │
│   │   │  ─────────────────        ──────────────────────       ─────────────────      ──────────         │   │   │
│   │   │  • Exact Match            • Faithfulness               • Multi-hop accuracy   • Latency (ms)     │   │   │
│   │   │  • F1 Score               • Relevance                  • Per-hop breakdown    • Tokens used      │   │   │
│   │   │  • Precision              • Answer Completeness        • Reasoning trace      • Retrieval count  │   │   │
│   │   │  • Recall                 • Context Precision          • Path correctness     • LLM calls        │   │   │
│   │   │  • Semantic Similarity    • Context Recall                                                       │   │   │
│   │   │  • BERTScore                                                                                     │   │   │
│   │   └─────────────────────────────────────────────────────────────────────────────────────────────────┘   │   │
│   │                                                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                   │                                                              │
│                                                   ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                    COMPARISON REPORT                                                     │   │
│   │                                                                                                          │   │
│   │   ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐   │   │
│   │   │                                                                                                  │   │   │
│   │   │  | Metric              | Classic RAG | Hybrid RAG | KG-Only RAG | Winner      |                 │   │   │
│   │   │  |---------------------|-------------|------------|-------------|-------------|                 │   │   │
│   │   │  | Exact Match         | 0.42        | 0.58       | 0.51        | Hybrid      |                 │   │   │
│   │   │  | F1 Score            | 0.56        | 0.71       | 0.64        | Hybrid      |                 │   │   │
│   │   │  | Faithfulness        | 0.78        | 0.89       | 0.92        | KG-Only     |                 │   │   │
│   │   │  | Multi-hop (2+)      | 0.31        | 0.62       | 0.58        | Hybrid      |                 │   │   │
│   │   │  | Avg Latency (ms)    | 450         | 720        | 380         | KG-Only     |                 │   │   │
│   │   │                                                                                                  │   │   │
│   │   └─────────────────────────────────────────────────────────────────────────────────────────────────┘   │   │
│   │                                                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Ontology/CQ Evolution Comparison

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    ONTOLOGY/CQ VERSION COMPARISON                                                │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                  │
│   ┌─────────────────────────────────────┐         ┌─────────────────────────────────────┐                       │
│   │      BASE ONTOLOGY (v1.0)           │         │    EXTENDED ONTOLOGY (v1.1)         │                       │
│   │                                     │         │                                     │                       │
│   │  Classes: 15                        │         │  Classes: 23 (+8)                   │                       │
│   │  Relations: 12                      │         │  Relations: 18 (+6)                 │                       │
│   │  Constraints: 8                     │   ───▶  │  Constraints: 14 (+6)               │                       │
│   │                                     │         │                                     │                       │
│   │  CQs: 20                            │         │  CQs: 32 (+12)                      │                       │
│   └─────────────────────────────────────┘         └─────────────────────────────────────┘                       │
│                    │                                              │                                              │
│                    ▼                                              ▼                                              │
│   ┌─────────────────────────────────────┐         ┌─────────────────────────────────────┐                       │
│   │      KG BUILD EXPERIMENT A          │         │      KG BUILD EXPERIMENT B          │                       │
│   │                                     │         │                                     │                       │
│   │  Iterations to converge: 12         │         │  Iterations to converge: 15         │                       │
│   │  Final nodes: 450                   │         │  Final nodes: 680                   │                       │
│   │  Final edges: 890                   │         │  Final edges: 1340                  │                       │
│   │  CQ coverage: 75%                   │         │  CQ coverage: 88%                   │                       │
│   │  SHACL violations: 12               │         │  SHACL violations: 8                │                       │
│   └─────────────────────────────────────┘         └─────────────────────────────────────┘                       │
│                    │                                              │                                              │
│                    └──────────────────────┬───────────────────────┘                                              │
│                                           ▼                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                    IMPACT ANALYSIS                                                       │   │
│   │                                                                                                          │   │
│   │   Ontology Diff:                          CQ Diff:                                                       │   │
│   │   ┌────────────────────────────────┐     ┌────────────────────────────────┐                             │   │
│   │   │ + ProblemCategory              │     │ + "What problem categories...?"│                             │   │
│   │   │ + ContainmentAction            │     │ + "What containment actions...?"│                             │   │
│   │   │ + VerificationMethod           │     │ + "How was the fix verified?" │                             │   │
│   │   │ + hasCategory (relation)       │     │ + "What verification methods...?"│                            │   │
│   │   │ + verifiedBy (relation)        │     │ ...                            │                             │   │
│   │   └────────────────────────────────┘     └────────────────────────────────┘                             │   │
│   │                                                                                                          │   │
│   │   KG Building Impact:                     QA Performance Impact:                                         │   │
│   │   ┌────────────────────────────────┐     ┌────────────────────────────────┐                             │   │
│   │   │ Graph size: +51%               │     │ Exact Match: +12%              │                             │   │
│   │   │ CQ coverage: +13%              │     │ Multi-hop accuracy: +18%       │                             │   │
│   │   │ Validation score: +33%         │     │ Faithfulness: +8%              │                             │   │
│   │   │ Iterations: +25%               │     │ Answer completeness: +15%      │                             │   │
│   │   └────────────────────────────────┘     └────────────────────────────────┘                             │   │
│   │                                                                                                          │   │
│   │   Conclusion: Extended ontology improves coverage and QA at cost of longer build time.                   │   │
│   │                                                                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Experiment Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                          EXPERIMENT LIFECYCLE                                            │
└─────────────────────────────────────────────────────────────────────────────────────────┘

  1. SETUP                    2. BUILD KG                   3. EVALUATE                  4. COMPARE
     │                           │                             │                            │
     ▼                           ▼                             ▼                            ▼
┌─────────────┐           ┌─────────────┐              ┌─────────────┐             ┌─────────────┐
│ Define      │           │ Run Deep-   │              │ Run QA      │             │ Generate    │
│ Experiment  │──────────▶│ Research    │─────────────▶│ Evaluation  │────────────▶│ Comparison  │
│ Config      │           │ Iterations  │              │ on Dataset  │             │ Reports     │
└─────────────┘           └─────────────┘              └─────────────┘             └─────────────┘
     │                           │                             │                            │
     │                           │                             │                            │
     ▼                           ▼                             ▼                            ▼
┌─────────────┐           ┌─────────────┐              ┌─────────────┐             ┌─────────────┐
│ • Ontology  │           │ • Iteration │              │ • Per-Q     │             │ • Cross-exp │
│   version   │           │   metrics   │              │   results   │             │   tables    │
│ • CQ version│           │ • Graph     │              │ • Aggregate │             │ • Plots     │
│ • RAG type  │           │   snapshots │              │   metrics   │             │ • LaTeX     │
│ • Model cfg │           │ • Validation│              │ • Failures  │             │ • Dashboard │
└─────────────┘           └─────────────┘              └─────────────┘             └─────────────┘
```

---

## Change Log

| Date | Version | Change |
|------|---------|--------|
| 2026-01-30 | 1.1 | Added Experiment Tracking & Comparison Framework |
| 2026-01-30 | 1.0 | Initial architecture design |
