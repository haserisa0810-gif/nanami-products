# Birth Chart Museum — Architecture Edition (experiment)

**Does not replace** the abstract edition at `/house-tour`.

| | Abstract | Architecture (this) |
|--|----------|---------------------|
| Route | `/house-tour` | `/house-tour-architecture` |
| Goal | Concept, UX, symbols | Believable museum buildings |
| Hero rooms | All symbolic | **4 home · 5 theater · 9 observatory/library** |
| Checkpoint | `checkpoint/house-tour-abstract-museum-v1` | branch experiment |

## Open

```text
GET /house-tour-architecture
GET /house-tour-architecture?lang=en
```

## Stack

- Reuses abstract modules: tour, cinematic, controls, YAML, i18n, planets
- New: `js/arch-builder.js`, `js/materials.js` (canvas PBR-ish materials)
- No Unity / Unreal; Three.js only

## Next (if promising)

1. Blender blockout → glTF for hero rooms  
2. Baked lightmaps  
3. Expand remaining houses  
4. Product decision: keep dual editions or promote architecture  

See also: `../house-tour/REALISM.md`, `../house-tour/CHECKPOINT.md`
