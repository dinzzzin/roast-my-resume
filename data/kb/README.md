# Knowledge base for RAG

One folder per source type. `python -m app.rag.build_index` indexes every folder
that contains .md files, so adding a folder needs no code change.

- `code/`   guidelines for code roasts and refactors (code track)
- `resume/` action verbs and strong/weak bullet examples (resume track)

Format: one topic per file. First line `# Title`, then optionally an
`Applies to:` line naming the analyzer metrics it relates to, then the guideline,
ideally with a short bad/good example. Keep each file under ~250 words; longer
files are split at `## ` headings.
