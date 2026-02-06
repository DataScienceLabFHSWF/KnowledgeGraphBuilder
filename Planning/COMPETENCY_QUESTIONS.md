# Competency Questions for Decommissioning Knowledge Graph (Strahlenschutz & Atomrecht)

The following competency questions were provided by domain experts and should be used to validate the Knowledge Graph's coverage and quality.

## Question Set 1 (German)

1. **Was ist der Unterschied zwischen „Freigabe“ und „Freisetzung“ bzw. „Herausgabe“ und „Herausbringen“ im Strahlenschutzrecht?**
   - *Goal:* Verify distinction between specific regulatory terms.

2. **Wie weicht die Definition von Kernbrennstoffen im deutschen Atomrecht vom Begriff „Kernmaterial“ nach den EURATOM-Richtlinien voneinander ab?**
   - *Goal:* Contrast definitions between national (AtG) and international (EURATOM) law.

3. **Was wird bei einer Genehmigung einer Anlage nach § 9 AtG genehmigt, was bei einer Genehmigung nach § 7 AtG?**
   - *Goal:* Distinguish between specific paragraphs of the Atomic Energy Act.

4. **Welche Möglichkeiten bestehen für die Haftung bei Kernmaterialtransporten?**
   - *Goal:* Extract liability related concepts.

5. **Ist/kann mit einer Genehmigung nach § 7 AtG eine Genehmigung nach § 12 StrlSchG abgedeckt sein?**
   - *Goal:* Relationship between AtG and StrlSchG.

6. **Können Genehmigungen nach § 7 AtG befristet werden?**
   - *Goal:* Verify attributes of permits.

7. **Was versteht man unter Deckungsvorsorge im Sinne des AtG?**
   - *Goal:* Define standard terminology.

8. **Welches sind die Schutzziele der Sicherung kerntechnischer Anlagen?**
   - *Goal:* Identify security objectives.

9. **Wie sind die Begriffe „Störfall“ und „Unfall“ definiert?**
   - *Goal:* Differentiate between incident levels.

---

## Implementation Plan

To use these questions effectively:
1. **JSON Dataset:** Store these in [data/evaluation/competency_questions.json](data/evaluation/competency_questions.json) to be loaded by the evaluation/discovery loop.
2. **Target Extraction:** Use these questions to guide the discovery loop to focus on relevant document sections.
3. **Automated Testing:** Run SPARQL or LLM-based QA over the resulting KG to check if these can be answered.
