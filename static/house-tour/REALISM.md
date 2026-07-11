# How far can “museum quality” go with Three.js only?

**Goal:** Not photoreal AAA.  
**Target:** *Google Arts & Culture* / real museum walkthrough — believable architecture, materials, and light.

**Constraint:** Three.js + WebGL in the browser. No Unity / Unreal.

---

## Short answer

| Level | Feasible with Three.js? | Effort | Notes |
|-------|-------------------------|--------|--------|
| A. Better low-poly (current+) | ✅ Yes | Low | Sharper materials, less “art object” |
| B. Believable architecture (museum walkthrough) | ✅ Yes | Medium–High | Best ROI for Birth Chart Museum |
| C. Near-photoreal interiors | ⚠️ Partially | Very high | Needs many textures, LODs, baking |
| D. Game-engine cinematic quality | ❌ Not practical | — | Wrong tool; keep Three.js for B |

**Recommendation:** Aim for **Level B — Architecture Museum Edition**.  
Keep **Level A abstract** as the stable product/demo at `/house-tour`.

---

## What “museum quality” actually means

Not ray-traced marble. It means:

1. **Readable architecture** — you instantly know “house / theater / tower”
2. **Scale that feels human** — doors ~2 m, chairs you could sit on, not wall-filling blobs
3. **Materials that read** — wood grain, stone, brass, fabric (PBR textures)
4. **Light that tells a story** — warm hearth, stage spot, cool dome skylight
5. **Props as exhibits** — globe, telescope, map on pedestals, not merged into walls
6. **Far → near → enter** — approach path, facade, then interior

This is closer to **architectural visualization + museum UX** than to Fortnite.

---

## What Three.js can do well (for this product)

### Architecture

- Custom rooms from primitives + extruded plans (or glTF buildings from Blender)
- Distinct silhouettes per house (roof, dome, tower, proscenium)
- Multi-room shells with corridors (true walkthrough, not one box)

### Materials & light

- `MeshStandardMaterial` / `MeshPhysicalMaterial` (roughness, metalness, clearcoat)
- Environment maps (HDRI) for soft museum reflections
- Baked lightmaps (Blender → UV) for stable, cheap beauty
- Real-time: spots, rect area lights (limited), shadows (selective)

### Assets

- glTF / GLB props: telescope, globe, furniture (CC0 kits or custom Blender)
- Texture sets: 1–2k wood/stone/plaster (compressed KTX2 / Basis)
- Optional Draco mesh compression for size

### UX we already have (reuse)

- Guided cinematic camera
- Click-to-walk, drag look
- YAML natal placement of planets as “exhibits”
- JA/EN strings

**Do not rebuild UX.** Rebuild **space quality** on a parallel route.

---

## What is hard / not worth it (in pure Three.js)

| Temptation | Reality |
|------------|---------|
| Photoreal skin, hair, crowds | Out of scope; not needed for museum |
| Unlimited dynamic GI | Use baked lightmaps |
| 12 fully unique photoreal interiors day-1 | Too much content; prototype 3 rooms first |
| Huge open world | Keep ring museum campus, denser rooms |
| Mobile high shadow everything | Quality tiers (already have low/high) |

---

## House-by-house architecture targets (Level B)

| House | Building language | Key props | Light mood |
|-------|-------------------|-----------|------------|
| 1 | Dawn portal / entrance hall | Mirror, threshold, coat | Cool dawn side light |
| 2 | Stone storehouse / treasury | Shelves, tools, craft, keys | Warm lamps |
| 3 | Long study corridor | Books, letters, map | Cool daylight |
| 4 | Old residence living room | Hearth, photos, chair | Firelight |
| 5 | Real proscenium theater | Stage, seats, piano, unfinished art | Dark house / bright stage |
| 6 | Lab / workshop | Desks, clock, gears, coffee | Even work light |
| 7 | Reception / contract room | Facing chairs, table, contract | Symmetric soft light |
| 8 | Lower vault (not horror) | Chest, water, cup, sprout | Slit light |
| 9 | Observatory + library | Globe, brass telescope, maps, dome | High cool skylight |
| 10 | Tower lookout | Stairs, deck, emblem, lighthouse | Bright overhead |
| 11 | Round hall / network plaza | Round table, nodes | Cool linked points |
| 12 | Quiet cloister + water | Veils, basin, moonlight | Soft mist / low contrast |

**Trust (esp. overseas):** Prefer “could exist as a museum wing” over “mystical purple void.”

---

## Suggested build path (safe)

```text
1. KEEP  /house-tour          ← abstract edition (checkpoint tag)
2. ADD   /house-tour-architecture  ← optional experiment route
3. Prototype only: House 4, 5, 9  (home / theater / observatory)
4. If visitors feel “I want to walk in” → expand other houses
5. If not → invest in abstract edition polish instead
```

### Content pipeline (realistic but shippable)

1. Blockout in Blender (real meters)
2. UV + bake ambient occlusion / light
3. Export glTF
4. Three.js loader + reuse existing tour / YAML / i18n
5. Quality: high = shadows + env map; low = baked only

### Performance budget (browser)

- ~5–15 MB initial for 3 hero rooms + shared props
- Prefer instancing for books/chairs
- One shadow-casting light per active room
- Mobile: no soft shadows, smaller textures

---

## Verdict

| Question | Answer |
|----------|--------|
| Can we make rooms feel like real museum architecture in Three.js? | **Yes (Level B)** |
| Photoreal? | No need; avoid chasing C |
| Should we overwrite abstract edition? | **No** |
| Best next step | Parallel route + 3 hero rooms in glTF, reuse tour/YAML |

**Abstract edition = product concept and UX capital.**  
**Architecture edition = spatial trust and “I want to visit this museum.”**

Compare both until one clearly wins for launch.
