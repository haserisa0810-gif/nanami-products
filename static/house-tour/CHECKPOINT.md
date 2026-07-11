# Checkpoint — Abstract Museum Edition (v1)

**Do not delete or overwrite this edition casually.**

| Item | Value |
|------|--------|
| Tag | `checkpoint/house-tour-abstract-museum-v1` |
| Commit | `7111e7e` (message: Birth Chart Museum abstract edition) |
| Route | `/house-tour` |
| Assets | `static/house-tour/**`, `templates/house_tour.html` |

## What this edition is

- **Birth Chart Museum** — guided cinematic tour + free walk
- Symbolic / low-poly galleries (not photoreal buildings)
- YAML natal load (client-side), JA/EN i18n
- Click-to-walk, drag-to-look
- Sample chart (ねこ編集長) + paste your own YAML

## How to restore

```bash
git checkout checkpoint/house-tour-abstract-museum-v1
# or
git checkout 7111e7e -- static/house-tour templates/house_tour.html tests/test_house_tour.py
```

## Sibling experiment

Architecture-oriented “museum quality” experiments live on:

```text
feature/house-tour-architecture-edition
```

They must **not** replace `/house-tour` without an explicit product decision.
Keep abstract as the default public demo until architecture edition is clearly better.

## Compare editions

| Edition | Route | Role |
|---------|-------|------|
| Abstract Museum (this) | `/house-tour` | Concept, UX, YAML, i18n, tour |
| Architecture Museum | `/house-tour-architecture` | Materials, lighting, hero buildings 4/5/9 |

Both coexist. Do not delete abstract when expanding architecture.
