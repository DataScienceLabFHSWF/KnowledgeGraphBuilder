"""KG validation (SHACL, ontology, competency questions).

Implementation of Issues #7.1-#7.3: Validation Framework

TODO (Core interfaces):
- [ ] Define Validator protocol (validate -> ValidationReport)
- [ ] Define ValidationReport with violations and statistics

TODO (SHACL Validator - Issue #7.2):
- [ ] Implement SHACLValidator using pyshacl
  - Load SHACL shape graphs
  - Validate against ontology constraints
  - Report violations with suggestions
- [ ] Support cardinality constraints
- [ ] Support pattern constraints
- [ ] Generate fix suggestions
- [ ] Add unit tests with sample shapes

TODO (Ontology Validator):
- [ ] Validate node types against ontology classes
- [ ] Validate edge predicates against ontology relations
- [ ] Check domain/range constraints
- [ ] Check property types

TODO (Competency Question Validator - Issue #7.3):
- [ ] Parse CQs (questions and/or SPARQL templates)
- [ ] Execute CQ queries against graph
- [ ] Report which CQs are answerable
- [ ] Track CQ coverage percentage
- [ ] Suggest improvements for unanswerable CQs
- [ ] Add unit tests

TODO (Quality):
- [ ] Generate detailed validation reports
- [ ] Add confidence scores to violations
- [ ] Add structured logging
- [ ] Add integration tests

See Planning/ISSUES_BACKLOG.md Issues #7.1-#7.3 for acceptance criteria.
"""

from .validators import (
    CompetencyQuestionValidator,
    OntologyValidator,
    SHACLValidator,
    Validator,
    ValidationReport,
    ValidationViolation,
)

__all__ = [
    "Validator",
    "ValidationReport",
    "ValidationViolation",
    "SHACLValidator",
    "OntologyValidator",
    "CompetencyQuestionValidator",
]

__all__ = []
