# Municipality Coordinate Source ZIPs

Place the 47 prefecture ZIP files here, for example `01000-24.0a.zip` through
`47000-24.0a.zip`.

The ZIP files are local source data and are intentionally not tracked in Git or
uploaded to Cloud Run because the full set is large. Generate the runtime CSV
with:

```bash
python scripts/generate_municipality_coords.py
```
