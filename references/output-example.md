# Output example (placeholder data)

Every block below is the **real output** of the commands above it, run on `examples/results.json` and `examples/draft.md`. All titles are placeholders; a real run must contain only sources found and verified in the session. Regenerate by running the commands in the same order.

## Mode 1: `examples/results.json`

### Input shape

```json
{
  "cutoff": "B",
  "articles": [
    {
      "title": "Placeholder Survey on Topic X",
      "authors": ["Doe, J.", "Roe, A. B."],
      "year": 2024, "type": "journal", "venue": "Journal J, 12(3), 1-20",
      "url": "https://example.org/a", "doi": "10.1000/x",
      "category": "concept", "tier": "A", "keyword": "Survey + topic X",
      "steps": {"S1": true, "S2": true, "S3": true, "S4": true, "S5": true,
                "S6": true, "S7": true, "S8": true, "S10": true, "S11": true},
      "evidence": {"S6": "Scopus Q1 (SJR 2024)", "S7": "ISSN valid (check_ids.py)"},
      "notes": {"en": "why it failed", "fa": "دلیل رد شدن"}
    }
  ]
}
```

Leave out `S9`: the script computes it from `tier` and the cut-off. Use `null` (or omit the key) for a step you could not verify, and `false` for a step that was checked and failed. `authors` and `notes` are optional; `notes` may be a string or an `{en, fa}` pair, and the renderer prints the column's language. Steps after the first ❌ may be omitted: they render as ❓ but the article is already rejected.

### Command

```bash
python3 scripts/render_table.py examples/results.json --lang en --evidence --bibliography apa
```

### Rendered output

```
### Approved sources (all steps ticked)

| # | Article | Type | Tier | Category | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | [Placeholder Survey on Topic X](https://example.org/a) (2024) | Journal | A | Concept | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**Steps:** 1 = Area · 2 = Subject · 3 = Keyword · 4 = Source type · 5 = Publisher/venue · 6 = Indexing · 7 = Identifiers · 8 = Specialization & year · 9 = Tier ≥ cut-off · 10 = Category · 11 = Extraction

#### Evidence

- #1 → 6: Scopus Q1 (SJR 2024); 7: ISSN valid (check_ids.py)

### Pending: needs your verification

| # | Article | Step | Reason / what to check |
|---|---|---|---|
| 1 | [Placeholder Application Paper](https://example.org/b) (2024) | 6 Indexing ❓ | WoS status not verifiable here: check mjl.clarivate.com |

### Rejected

| # | Article | Step | Reason / what to check |
|---|---|---|---|
| 1 | Placeholder Undergraduate Thesis (2021) | 4 Source type ❌ | Undergraduate thesis |

**Summary:** 1 approved · 1 pending · 1 rejected (Tier cut-off: B)

### References

1. Doe, J., & Roe, A. B. (2024). Placeholder Survey on Topic X. Journal J (Publisher P), 12(3), 1-20. https://doi.org/10.1000/x.
3. Example, B. (2024). Placeholder Application Paper. Journal K (Publisher Q), 8(1), 44-59. https://doi.org/10.1000/y.

**Included but still pending — verify before submitting:** 1
```

### Same file, Persian

```bash
python3 scripts/render_table.py examples/results.json --lang fa
```

```
### منابع تأییدشده (همه مراحل تیک‌خورده)

| # | منبع | نوع | رتبه | دسته | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | [Placeholder Survey on Topic X](https://example.org/a) (2024) | مقاله ژورنالی | A | مفهوم | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**مراحل:** 1 = حوزه · 2 = موضوع · 3 = کلیدواژه · 4 = نوع منبع · 5 = ناشر/محل انتشار · 6 = نمایه‌سازی · 7 = شناسه‌ها (ISSN/ISBN) · 8 = تخصص و سال · 9 = رتبه ≥ حد نصاب · 10 = دسته‌بندی · 11 = استخراج

### در انتظار بررسی شما

| # | منبع | مرحله | دلیل / مورد بررسی |
|---|---|---|---|
| 1 | [Placeholder Application Paper](https://example.org/b) (2024) | 6 نمایه‌سازی ❓ | وضعیت WoS از این سشن قابل تأیید نیست: mjl.clarivate.com را چک کن |

### ردشده

| # | منبع | مرحله | دلیل / مورد بررسی |
|---|---|---|---|
| 1 | Placeholder Undergraduate Thesis (2021) | 4 نوع منبع ❌ | پایان‌نامهٔ کارشناسی |

**خلاصه:** 1 تأییدشده · 1 در انتظار · 1 ردشده (حد نصاب رتبه: B)
```

## Mode 2: `examples/draft.md`

```bash
python3 scripts/check_draft.py examples/draft.md --lang en
```

```
### Title ❓ (2/6)

| ID | Rule | Result | Detail |
|---|---|---|---|
| T1 | 8-15 words | ✅ | 8 words (slide: 8-15) |
| T2 | Grabs the reader's attention | ❓ | needs a reader's judgment |
| T3 | Clearly states the main topic | ❓ | needs a reader's judgment |
| T4 | As specific as possible; shows scope (research design + statistical population + geographic area) | ❓ | needs a reader's judgment |
| T5 | No period at the end | ✅ | no period at the end |
| T6 | Written after the article was completed | ❓ | needs a reader's judgment |

### Abstract ❌ (2/12)

| ID | Rule | Result | Detail |
|---|---|---|---|
| A1 | 200-250 words | ❌ | 65 words (slide: 200-250) |
| A2 | Grabs the reader's attention | ❓ | needs a reader's judgment |
| A3 | Begins with a short sentence | ❓ | needs a reader's judgment |
| A4 | Shows the main purpose | ❓ | needs a reader's judgment |
| A5 | Shows scientific or practical importance | ❓ | needs a reader's judgment |
| A6 | Briefly shows the methodology | ❓ | needs a reader's judgment |
| A7 | Summarizes the findings | ❓ | needs a reader's judgment |
| A8 | Briefly states the challenges | ❓ | needs a reader's judgment |
| A9 | Highlights practical or theoretical implications | ❓ | needs a reader's judgment |
| A10 | Single paragraph | ✅ | one paragraph |
| A11 | No tables, figures, diagrams, in-text references | ✅ | none found |
| A12 | Written after the article was completed | ❓ | needs a reader's judgment |

### Keywords ❓ (2/3)

| ID | Rule | Result | Detail |
|---|---|---|---|
| K1 | 6-8 keywords | ✅ | 6 terms (slide: 6-8) |
| K2 | Work as traffic lights that attract attention | ❓ | needs a reader's judgment |
| K3 | English keywords start with a capital letter | ✅ | all capitalized |

### Affiliation ✅ (2/2)

| ID | Rule | Result | Detail |
|---|---|---|---|
| F1 | Affiliation present | ✅ | present |
| F2 | Persian and English versions (as in the slide example) | ✅ | Persian: yes, English: yes |

### Introduction ❌ (0/15)

| ID | Rule | Result | Detail |
|---|---|---|---|
| I1 | 500-700 words | ❌ | 81 words (slide: 500-700) |
| I2 | States the general topic of the research | ❓ | needs a reader's judgment |
| I3 | Answers: what is the benefit of reading this article? | ❓ | needs a reader's judgment |
| I4 | Names the most important related previous studies | ❓ | needs a reader's judgment |
| I5 | Main problem and question stated (short problem statement or main research question) | ❓ | needs a reader's judgment |
| I6 | Specific objectives clearly stated, from most general to most specific | ❓ | needs a reader's judgment |
| I7 | Background in which the research was conducted is stated | ❓ | needs a reader's judgment |
| I8 | Unit of analysis clearly stated | ❓ | needs a reader's judgment |
| I9 | Challenge and solution to the problem clearly stated | ❓ | needs a reader's judgment |
| I10 | Ends with a general outline of the other parts | ❓ | needs a reader's judgment |
| I11 | Opening paragraph in simple, non-technical language | ❓ | needs a reader's judgment |
| I12 | Guides the reader step by step to the formal problem statement | ❓ | needs a reader's judgment |
| I13 | Attractive opening sentence | ❓ | needs a reader's judgment |
| I14 | Summarizes research of the last three to five years | ❓ | years mentioned: none; within the last 5 years (2021-2026): none |
| I15 | Recent research is directly related to the problem | ❓ | needs a reader's judgment |

### Research Background ❌ (1/9)

| ID | Rule | Result | Detail |
|---|---|---|---|
| B1 | 1000-1500 words | ❌ | 42 words (slide: 1000-1500) |
| B2 | Reviews what other researchers have done on the topic | ❓ | needs a reader's judgment |
| B3 | Not just a summary: critically evaluates, reorganizes, synthesizes | ❓ | needs a reader's judgment |
| B4 | Discovers inconsistencies and contradictions that form the basis of the research | ❓ | needs a reader's judgment |
| B5 | Explains the material from beginning to end | ❓ | needs a reader's judgment |
| B6 | Sentences are kept short | ❓ | 6 sentences, average 7 words, longest 11 |
| B7 | No sentence contains the word “and” (و) | ✅ | no sentence contains the word and / و |
| B8 | “Reviewing a poorly written article” (slide wording) | ❓ | needs a reader's judgment |
| B9 | Other people have read the article | ❓ | needs a reader's judgment |

### Methodology ❌ (1/11)

| ID | Rule | Result | Detail |
|---|---|---|---|
| M1 | 500-1000 words | ❌ | 36 words (slide: 500-1000) |
| M2 | Explains the research steps | ❓ | needs a reader's judgment |
| M3 | Justifies the steps of the research method | ❓ | needs a reader's judgment |
| M4 | Explains the appropriateness of the chosen method | ❓ | needs a reader's judgment |
| M5 | Names articles to justify the choice | ❓ | 0 in-text reference(s) detected |
| M6 | Statistical population fully described | ❓ | needs a reader's judgment |
| M7 | All statistical populations are stated (if several) | ❓ | needs a reader's judgment |
| M8 | Population described as a regular paragraph, not a list | ✅ | no list lines |
| M9 | Data collection tool introduced (questionnaire, interview, library) | ❓ | needs a reader's judgment |
| M10 | Time of data collection stated | ❓ | needs a reader's judgment |
| M11 | Measured variables listed | ❓ | needs a reader's judgment |

### Findings ❌ (0/9)

| ID | Rule | Result | Detail |
|---|---|---|---|
| R1 | 1000-1500 words | ❌ | 17 words (slide: 1000-1500) |
| R2 | Research findings are discussed | ❓ | needs a reader's judgment |
| R3 | Results presented with full explanations | ❓ | needs a reader's judgment |
| R4 | Tables are used to display the findings | ❌ | 0 table(s) |
| R5 | Three to five tables | ❌ | 0 table(s) (slide: 3-5) |
| R6 | One to two figures | ❌ | 0 figure(s) (slide: 1-2) |
| R7 | Table and figure information is summarized and explained in the text | ❓ | table labels ['1'], figures none |
| R8 | Clear references to tables and figures appear before them | ❓ | table labels ['1'], figures none |
| R9 | Charts are used as well | ❓ | no chart label found; judge whether any figure is a chart |

### Conclusion ❌ (1/7)

| ID | Rule | Result | Detail |
|---|---|---|---|
| C1 | 1000-1500 words | ❌ | 37 words (slide: 1000-1500) |
| C2 | No figures, tables, or in-text references | ✅ | none found |
| C3 | States the main objective of the article | ❓ | needs a reader's judgment |
| C4 | States the significance of the research | ❓ | needs a reader's judgment |
| C5 | States the relevant results | ❓ | needs a reader's judgment |
| C6 | States the findings | ❓ | needs a reader's judgment |
| C7 | Main limitation of the study fully stated | ❓ | needs a reader's judgment |

### References ❓ (1/2)

| ID | Rule | Result | Detail |
|---|---|---|---|
| X1 | Reference list present | ✅ | present |
| X2 | Managed with Word or Endnote | ❓ | needs a reader's judgment |

### Summary

| Section | Rules | ✅ | ❌ | ❓ | Verdict |
|---|---|---|---|---|---|
| Title | 6 | 2 | 0 | 4 | ❓ |
| Abstract | 12 | 2 | 1 | 9 | ❌ |
| Keywords | 3 | 2 | 0 | 1 | ❓ |
| Affiliation | 2 | 2 | 0 | 0 | ✅ |
| Introduction | 15 | 0 | 1 | 14 | ❌ |
| Research Background | 9 | 1 | 1 | 7 | ❌ |
| Methodology | 11 | 1 | 1 | 9 | ❌ |
| Findings | 9 | 0 | 4 | 5 | ❌ |
| Conclusion | 7 | 1 | 1 | 5 | ❌ |
| References | 2 | 1 | 0 | 1 | ❓ |

**1/10 sections approved**
```

```

`--manual manual.json` replaces the ❓ verdicts you judged by reading the draft; a verdict is `true`, `false`, or an object with a note:

```json
{"T2": true, "T3": {"ok": false, "note": "title does not name the population"}, "A3": true}
```

Each section prints as a table (ID, rule, ✅/❌/❓, detail) with the section's verdict in the heading, for example `### Title ❌ (3/6)`, followed by a summary table and a line such as `1/10 sections approved`. A section is approved only when all its rules are ✅.

## After the tables

Add, per approved article, the one- or two-sentence extract in your own words, then one next step. Example shape:

> **#1 (Concept):** gives the field's standard definition and contrasts the two main viewpoints; use it to open the Research Background.
>
> Next step: collect the Challenge sources so the Introduction can state the problem.
