A good rubric for LLM judges should optimize for clarity, consistency, and traceability.
- Single objective per criterion: each dimension should measure one thing (e.g., factuality, not factuality + style).
- Behaviorally anchored levels: define what scores mean with concrete observable evidence, not vague labels like “good” or “poor.”
- Mutually exclusive score bands: reduce overlap between levels so the model can choose one level confidently.
- Complete coverage of task goals: include all critical requirements from the prompt; avoid irrelevant dimensions.
- Evidence-first scoring: require extracted evidence/quotes before assigning a score to reduce hallucinated judgments.
- Separation of reasoning and verdict: have the judge provide structured rationale, then score, to improve auditability.