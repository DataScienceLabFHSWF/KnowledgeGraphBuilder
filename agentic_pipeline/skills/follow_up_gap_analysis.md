---
name: follow_up_gap_analysis
tool: null
requires_binding: [agent]
default_kwargs:
  max_new_questions: 5
---

Generate follow-up research questions from entities discovered in the most
recent iteration, focusing on entity types not yet asked about.

Run this after a discovery iteration completes, using that iteration's
newly found entities as `discoveries` and the questions already asked as
`current_questions`.
