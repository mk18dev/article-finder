# Phase 1 — Real-evidence tier audit

**Audit date:** 2026-11-23  
**Scope:** Validate the A/B/C/D tier rules against one real, traceable example for each source type and verify the default B cut-off. This is a policy-validation snapshot, not a live production research plan.

## Results

| Source type | Real record | Evidence basis | Expected tier | Default B cut-off |
|---|---|---|---:|---|
| Journal | Data Mining and Knowledge Discovery (ISSN 1384-5810) | Clarivate SCIE; SJR Q1 (2024 and 2025); Springer; data-mining scope | A | Pass |
| Conference | KDD 2024 proceedings | DBLP proceedings record; 30th international KDD; ACM; ISBN 979-8-4007-0490-1 | A | Pass |
| Thesis | Niamh Errington, University of Sheffield, 2022 | Official PhD thesis; thesis lists a derived EBioMedicine paper; EBioMedicine SJR Q1 (2024) | A | Pass |
| Book | Deep Learning, Goodfellow/Bengio/Courville, MIT Press (2016) | Google Books + MIT Press metadata; valid ISBN 9780262035613; OpenAlex-derived citation snapshot is far above 50 | A* | Pass* |

render_table.py defaults to cut-off **B**. The decision requires tier_verified is True and tier <= cutoff; a declared tier alone cannot pass.

## Journal — A

- Journal: Data Mining and Knowledge Discovery, print ISSN 1384-5810 / eISSN 1573-756X.
- Publisher: Springer.
- Clarivate Master Journal List returns an exact ISSN match in the Science Citation Index Expanded (SCIE).
- SCImago reports Q1 for 2024 and Q1 for 2025. The journal scope explicitly covers data mining and knowledge discovery.
- Representative article: “Explainable and interpretable machine learning and data mining” (2024), DOI 10.1007/s10618-024-01041-y.
- **Expected result:** A, provided the record's specialization review and current S6/S7 evidence are present.

Evidence:
- [Clarivate Master Journal List — ISSN 1384-5810](https://mjl.clarivate.com/search-results?issn=1384-5810)
- [SCImago — Data Mining and Knowledge Discovery](https://www.scimagojr.com/journalsearch.php?clean=0&q=13579&tip=sid)
- [Springer — representative 2024 article](https://link.springer.com/article/10.1007/s10618-024-01041-y)
- [IIT Comillas journal record and historical JCR/SJR table](https://www.iit.comillas.edu/publicacion/info_revista/en/707/Data_Mining_and_Knowledge_Discovery)

## Conference — A

- Proceedings: Proceedings of the 30th ACM SIGKDD Conference on Knowledge Discovery and Data Mining, KDD 2024.
- International conference, Barcelona, 25–29 August 2024; the 30th edition establishes a mature series.
- Publisher: Association for Computing Machinery (ACM).
- DOI: 10.1145/3637528; ISBN: 979-8-4007-0490-1.
- DBLP is an accepted proceedings index in the current policy.
- **Expected result:** A, provided the proceedings record, edition/identifier, specialization and publisher evidence are reviewed.

Evidence:
- [DBLP proceedings record](https://dblp.org/rec/conf/kdd/2024.html)
- [DBLP KDD 2024 event record](https://dblp.org/db/conf/kdd/kdd2024.html)
- [ACM proceedings DOI](https://doi.org/10.1145/3637528)
- [ACM KDD 2024 paper record showing proceedings, publisher, ISBN and conference metadata](https://doi.org/10.1145/3637528.3671733)

## Thesis — A

- Thesis: Niamh Errington, Machine learning approaches for uncovering miRNAs as biomarkers of Pulmonary Hypertension (2022).
- The official repository identifies it as a PhD thesis awarded by the University of Sheffield.
- The thesis PDF title page confirms the degree and institution (PDF page 1). Its “Publications and manuscripts” section lists the 2021 EBioMedicine paper (PDF page 4).
- Derived paper: “A diagnostic miRNA signature for pulmonary arterial hypertension using a consensus machine learning approach”, DOI 10.1016/j.ebiom.2021.103444.
- SCImago reports EBioMedicine as Q1 in 2024. The university-reputability flag remains a human-review judgement; it is not inferred from the domain alone.
- **Expected result:** A, provided the repository, degree, university and derived-paper evidence are reviewed and linked.

Evidence:
- [Official White Rose thesis record](https://etheses.whiterose.ac.uk/id/eprint/31740/)
- [Thesis PDF — title page and publications list](https://etheses.whiterose.ac.uk/id/eprint/31740/1/Thesis.pdf)
- [PubMed — derived EBioMedicine paper and DOI](https://pubmed.ncbi.nlm.nih.gov/34186489/)
- [SCImago — EBioMedicine quartiles](https://www.scimagojr.com/journalsearch.php?clean=0&q=21100369815&tip=sid)

## Book — A* (threshold outcome stable; exact count must be refreshed)

- Book: Deep Learning, Ian Goodfellow, Yoshua Bengio and Aaron Courville, MIT Press, 2016.
- Main-book record: 800 pages; ISBN 9780262035613. The publisher's contents cover deep feedforward networks, convolutional networks, sequence modelling, NLP and related deep-learning topics.
- MIT Press was missing from the original trusted-publisher allowlist; it is now explicitly recognized.
- An OpenAlex-derived public snapshot reports thousands of indexed citations (one snapshot reports 8,937; another reports approximately 6.7k). Both are far above the configured strong threshold of 50, but the counts are not identical.
- **Expected result:** A if the reviewer re-fetches the exact OpenAlex API record, records its current count and ISBN, and ensures both match. Do not copy either third-party snapshot count into a production plan without refreshing the API response.

Evidence:
- [MIT Press — official book record](https://mitpress.mit.edu/9780262035613/deep-learning/)
- [Google Books — bibliographic record and contents](https://books.google.com/books/about/Deep_Learning.html?id=Np9SDQAAQBAJ)
- [OpenAlex API record to refresh before production use](https://api.openalex.org/works/W2557283755)
- [OpenAlex-derived snapshot reporting 8,937 citations](https://www.minicod.com/papers/deep-learning-e6c14a0c)
- [Independent OpenAlex-derived snapshot reporting approximately 6.7k citations](https://www.rankless.org/hit-papers/w2557283755)

A* means the tier threshold is unambiguous, but the exact current citation count remains a refresh-before-production item. The verifier now requires a separate OpenAlex citation record, exact count equality, and matching DOI/ISBN; a Google Books/Amazon record alone can no longer substantiate the citation count.

## Tier and cut-off coverage

- Real-source snapshots above exercise the A path for all four source types.
- The B/C/D boundaries, invalid identifiers, missing evidence, malformed values, blacklist override, unsupported indexes, and declared/computed mismatches remain covered by deterministic unit and integration tests.
- The default cut-off is B. Verified A and B records pass; C and D do not pass at the default cut-off. The renderer also refuses a record whose tier has not been independently verified.
- The real-source examples are not substitutes for a human reviewer opening each provider record at the time a real research plan is created. Indexing, quartiles, citation counts and publisher status can change.

## Phase 1 disposition

**Tier-policy implementation and regression coverage:** implemented and CI-gated.  
**Real-source validation:** four representative source types reviewed; book citation count requires a fresh direct OpenAlex API read before production use.  
**No deployment or release is authorized by this audit.**
