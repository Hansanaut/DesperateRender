# Desperate Render™ – AI Reference for Experiment SAVE Files (Revision 2)

**Revision:** 2  
**Purpose:** Authoritative reference for an AI that designs Desperate Render experiments, defines them as JSON, validates them, and prepares them for import.  
**Status:** Checked against the repository state on branch `main`.

This is the English counterpart to `DESPERATE_RENDER_AI_EXPERIMENT_JSON_GUIDE_REV2.md`. The German version remains unchanged. If documentation and application behavior disagree, the current source code always takes precedence.

---

## 1. Purpose and distinctions

An experiment SAVE file describes **an experiment definition**. It is not a list of queued jobs, a results manifest, a collection of generated images, or a guarantee that Fooocus accepts every setting at runtime.

The AI must create a comprehensible experiment definition and determine the expected number of concrete generation configurations from the builder logic. Valid JSON syntax alone is not sufficient.

Core implementation:

- `models/experiment.py` – data models, enums, defaults, and size constants.
- `models/prompt_block.py` – prompt-block model and variant identification.
- `models/generation_configuration.py` – configuration for one generation job.
- `services/experiment/experiment_store.py` – JSON serialization, deserialization, storage, and reference paths.
- `services/experiment/matrix_builder.py` – matrix expansion and configuration generation.

## 2. SAVE files, storage, and revisions

### 2.1 Format

- UTF-8 JSON.
- **MANDATORY: The filename must end exactly with `_exp.json`.** The LOAD command uses this suffix to discover experiment SAVE files. Files ending only in `.json` (without the `_exp` part) are not directly discoverable through LOAD.
- This is a functional requirement, not merely the store's preferred naming convention.
- The application stores experiment definitions in date-based subdirectories.

### 2.2 Actual naming convention

The experiment directory is:

    <Experiment-Root>/<sanitized-experiment-name>_YYYYMMDD/

The JSON filename must follow this pattern and, in all cases, retain the exact `_exp.json` suffix:

    YYYYMMDD-HHMMSS-<sanitized-experiment-name>_exp.json

**Do not rename or generate an experiment SAVE file with a plain `.json` ending. The LOAD command will not find it in its normal file discovery.**

If that filename already exists, a suffix is added, for example `...-2_exp.json`. The timestamp is based on **updated_at**, which the store updates immediately before every explicit save.

### 2.3 Revision behavior

- Every explicit save creates a new JSON revision.
- Previous JSON revisions are not overwritten or deleted by the store.
- **created_at** remains unchanged; **updated_at** changes on every save.
- The logical **experiment_id** remains the same across revisions of one experiment.
- The store generally creates new logical IDs as `YYYYMMDD-NNN`, e.g. `20261101-001`. This ID is not the JSON filename.
- Deleting or overwriting existing revisions is not an AI task.

### 2.4 Reference images

When saving, reference images are copied into a revision-specific directory. JSON stores relative paths within that revision; the loader resolves them to absolute paths. Reference images are not embedded in JSON. The files must exist separately and be accessible to the store.

## 3. Top-level JSON structure

The top-level object corresponds to the **Experiment** model.

| Field | Type | Meaning |
|---|---|---|
| experiment_id | String | Required logical experiment ID |
| name | String | Display name |
| version | Integer | Definition version; default 1 |
| status | Enum string | Experiment status |
| created_at | ISO datetime | Required creation timestamp |
| updated_at | ISO datetime | Required modification timestamp |
| positive_prompts | Array | Legacy positive prompt slots |
| negative_prompts | Array | Negative prompt slots |
| prompt_blocks | Array | Independent positive-prompt dimensions |
| styles | String array | Styles actually selected |
| available_styles | String array | Stored style pool; not used by MatrixBuilder for selection |
| random_style | Boolean | Enable random style selection |
| random_style_count | Integer | Number of randomly selected styles |
| style_references | Array | Style reference images |
| composition_references | Array | Composition reference images |
| generation | Object | Fixed generation settings and seed behavior |
| matrix | Object | Selection rules for experiment dimensions |
| configuration_count | Integer | Count determined by the builder |
| total_image_count | Integer | Derived counter, currently tied to configuration_count |
| estimated_runtime_seconds | Number/null | Runtime estimate |
| estimated_storage_bytes | Integer/null | Storage estimate |
| test_run_completed | Boolean | Whether a test run is complete |

### 3.1 Status values

Supported values: `DRAFT`, `READY`, `RUNNING`, `PAUSED`, `ABORTED`, `FAILED`, `COMPLETED`. Use `DRAFT` for a newly designed experiment.

### 3.2 Required fields and loader defaults

The loader requires **experiment_id**, **created_at**, and **updated_at**. Always include them. Other fields may receive model or loader defaults, but a complete SAVE file should explicitly include all central fields.

Timestamps must be parseable by `datetime.fromisoformat()`, e.g. `2026-11-01T12:00:00`. Status is validated against the enum; an unknown value causes a loading error.

## 4. Prompt data

### 4.1 PromptSlot

Positive and negative prompts use **PromptSlot**:

| Field | Type | Rule |
|---|---|---|
| slot_id | Integer | Required; unique within its list or block |
| text | String | Prompt text; default empty |
| fixed | Boolean | Fixed component; default false |

Example:

    {"slot_id": 1, "text": "a glass Erlenmeyer flask", "fixed": false}

**fixed = true** means the prompt is not a variable matrix alternative and remains in every variant. Slot IDs must be unique within the same list or block; different blocks may reuse IDs.

### 4.2 Legacy positive_prompts

- If there is no non-empty prompt block, the builder can use the legacy dimension.
- As soon as at least one prompt block contains content, prompt-block mode replaces the legacy positive-prompt dimension.
- New experiments should not control positive prompts through both legacy slots and prompt blocks.
- The prompt-block editor may transfer existing legacy prompts into initial Block A. Already saved prompt blocks remain authoritative.
- For legacy prompts, fixed slots remain in every variant; only non-fixed slots are varied.

### 4.3 negative_prompts

Negative prompts are PromptSlot objects. If the list is non-empty, it is processed as a matrix dimension. Fixed negative prompts remain in every variant.

### 4.4 prompt_blocks

Example:

    {
      "block_id": "A",
      "name": "Subject",
      "prompts": [
        {"slot_id": 1, "text": "a glass Erlenmeyer flask", "fixed": false},
        {"slot_id": 2, "text": "a futuristic glass Erlenmeyer flask", "fixed": false}
      ],
      "matrix_selection": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null}
    }

Rules:

- **block_id** must be exactly one alphabetic character; it is trimmed and uppercased.
- **name** is the readable dimension name.
- **prompts** contains the block's PromptSlots.
- **matrix_selection** controls selection of variable prompts.
- Empty blocks are ignored.
- A block containing only fixed prompts produces one variant retaining those prompts.
- Block and prompt order matters.
- All non-empty blocks are combined as a Cartesian product; selected prompt texts are assembled in block order.
- Variant IDs combine block and slot IDs, e.g. `A2+B1`. The current `PromptBlock.variant_id()` also accounts for fixed prompts in the identifier, and fixed prompts remain in the final prompt.

Typical independent dimensions: Block A Subject, Block B Lighting, Block C Perspective, Block D Background.

## 5. generation – fixed generation settings

Current GenerationSettings defaults:

| Field | Type | Default | Meaning |
|---|---|---:|---|
| width | Integer | 1024 | Base width |
| height | Integer | 768 | Base height |
| aspect_ratio | String | "4:3" | Stored aspect-ratio value |
| seed_mode | Enum string | "RANDOM" | FIXED or RANDOM |
| seed | Integer/null | null | Legacy single seed |
| seeds | Integer array | [] | Manual seed list |
| random_seed_count | Integer | 1 | Seeds per matrix combination |
| random_seed_fixed | Boolean | true | Generate random seeds once and reuse |
| random_seeds | Integer array | [] | Persisted seeds in fixed-random mode |
| performance | String/null | null | Fooocus performance setting |
| guidance_scale | Number/null | null | Fixed base Guidance Scale |
| sharpness | Number/null | null | Fixed base Sharpness |
| base_model | String/null | null | Legacy/single model |
| base_models | String array | [] | Multiple base models |
| refiner_model | String/null | null | One refiner model |
| refiner_switch | Number/null | null | Refiner switch value |
| output_format | String | "png" | Output format |

Important: the model default for **seed_mode is RANDOM**, not FIXED. Explicitly set FIXED when demonstrating reproducible fixed seeds.

### 5.1 Seed behavior in MatrixBuilder

**FIXED**
- If **seeds** is non-empty, each entry is a separate outer seed variant.
- Otherwise **seed** is used as the single seed.
- If both are empty/null, a configuration may contain a null seed. Provide concrete seeds for reproducibility.

**RANDOM with random_seed_fixed = true**
- The builder generates the number of seeds requested by **random_seed_count**.
- Existing **random_seeds** are reused; missing ones are generated.
- Seeds are stored on the experiment and reused across matrix combinations.
- They form an outer dimension and multiply the configuration count.

**RANDOM with random_seed_fixed = false**
- No fixed seed dimension is expanded in advance.
- Every concrete job receives a newly generated seed.
- **random_seed_count** jobs/seeds are generated for each combination and, where applicable, each randomly selected style.
- These seeds are not pre-created as a persisted reusable dimension.

The builder treats **random_seed_count** as at least 1. Use FIXED with explicit seeds or RANDOM with fixed persisted seeds for reproducible comparisons. Use RANDOM with **random_seed_fixed = false** for independent random seeds per job.

Legacy compatibility: if **seeds** is empty and **seed** is set, the loader transfers the legacy value into the seed list.

### 5.2 Base models and refiner

- If **generation.base_models** contains entries, the builder uses that list as the base-model dimension.
- Otherwise, a set **generation.base_model** is used as one legacy alternative.
- Its selection rule is **matrix.base_models**.
- The current GenerationSettings model has only one **refiner_model** string.
- The builder processes it as a one-item list. **matrix.refiner_models** exists but currently cannot select among multiple refiner models.

Do not assume multiple refiner models are supported.

## 6. matrix – selection rules and combinatorics

### 6.1 MatrixSelection

Discrete dimensions use:

    {"operator": "INDIVIDUAL", "minimum": null, "maximum": null}

Operators:

- **INDIVIDUAL** – each value becomes its own variant.
- **ALL** – all values are combined into one variant.
- **PERMUTATION** – ordered groups.
- **COMBINATION** – unordered groups.

For PERMUTATION and COMBINATION: **minimum** must be at least 1; **maximum** must be at least minimum and no greater than the number of values. Missing bounds default to 1 and the number of values, respectively.

For values A, B, C:

| Operator | Setting | Variants |
|---|---|---:|
| INDIVIDUAL | – | 3 |
| ALL | – | 1 |
| PERMUTATION | min 1, max 3 | 15 |
| PERMUTATION | min 2, max 2 | 6 |
| COMBINATION | min 1, max 3 | 7 |
| COMBINATION | min 2, max 2 | 3 |

For an empty value list, **MatrixBuilder.build()** returns an empty selection `()`, which acts as a neutral dimension in the Cartesian product. An empty dimension does not automatically mean zero configurations.

### 6.2 Discrete matrix dimensions

The data model defines MatrixSelection fields:

- **positive_prompts**
- **negative_prompts**
- **styles**
- **seeds**
- **style_references**
- **composition_references**
- **base_models**
- **refiner_models**
- **lora_configurations**

The current `iter_experiment()` actually processes these dimensions: legacy positive prompts (unless non-empty prompt-block mode is active), negative prompts, styles when Random Style is off, style references, composition references, base models, a configured refiner model, Guidance Scale, Sharpness, and Resolution.

Seeds and prompt blocks are handled separately through their own loops/product expansion.

**LoRA:** `lora_configurations` exists in the matrix model but is not processed as a dimension by the current `iter_experiment()`. Do not infer active LoRA experiment support from the field's existence.

### 6.3 NumericMatrixSelection: Guidance Scale and Sharpness

Guidance Scale and Sharpness use **NumericMatrixSelection**, not MatrixSelection:

    {"enabled": true, "minimum": 2.0, "maximum": 8.0, "steps": 4}

| Field | Type | Meaning |
|---|---|---|
| enabled | Boolean | Enable/disable the dimension |
| minimum | Number/null | Lower value |
| maximum | Number/null | Upper value |
| steps | Integer | Number of generated values, not intervals |

Builder rules:

- If disabled, no values are generated.
- If enabled, minimum and maximum are required.
- steps must be at least 1.
- maximum must not be less than minimum.
- steps = 1 emits only minimum.
- steps > 1 requires maximum > minimum.
- Multiple values are evenly distributed, including both bounds.
- Values are rounded to ten decimal places.

Example: minimum 2, maximum 8, steps 4 gives `[2.0, 4.0, 6.0, 8.0]`.

Values form an INDIVIDUAL dimension and override the corresponding base value in **generation.guidance_scale** or **generation.sharpness**. Check Fooocus' accepted ranges separately against the installed configuration/runtime.

### 6.4 ResolutionMatrixSelection

Resolution uses a dedicated structure:

    {"enabled": true, "dimension": "width", "minimum": 600, "maximum": 1200, "steps": 3}

| Field | Type | Meaning |
|---|---|---|
| enabled | Boolean | Enable/disable resolution matrix |
| dimension | String | "width" or "height" |
| minimum | Integer/null | Lower bound of varied axis |
| maximum | Integer/null | Upper bound of varied axis |
| steps | Integer | Number of evenly spaced values, including bounds |

Current builder rules:

- dimension must be exactly **width** or **height**.
- Missing minimum/maximum default to the current base value of the selected axis.
- steps must be at least 1; maximum must not be less than minimum.
- The selected axis must be within model limits: width 480–2048 px, height 320–2048 px.
- The other axis is derived from **generation.width / generation.height**, rounded to whole pixels, and must also be within its model limits.
- steps = 1 emits only minimum.
- Generated dimensions are assigned directly to GenerationConfiguration; no later image scaling occurs.

Example: base 1024 × 768, width 600–1200, 3 steps:

    600 × 450
    900 × 675
    1200 × 900

**Important – 8-pixel alignment:** The model defines `GENERATION_SIZE_STEP = 8`, but MatrixBuilder does not enforce it. It checks bounds and the derived aspect ratio, not divisibility by 8. For Fooocus-compatible experiments, choose values for which both width and height (including the derived dimension) are divisible by 8, and explicitly verify every resulting size.

**Aspect ratio:** Width and height are derived from the base width/height ratio. **generation.aspect_ratio** is not recalculated; it is passed to GenerationConfiguration as stored. Ensure it matches the base dimensions.

### 6.5 Cartesian product and actual configuration count

Active dimensions are generally combined as a Cartesian product. Example: 3 variants × 4 variants × 2 prompt-block variants × 2 fixed seeds = 48 configurations, assuming no special rules intervene.

Do not calculate the count by simply multiplying array lengths. Account for matrix operators, fixed and variable PromptSlots, prompt-block products, seed mode and random_seed_count, Random Style behavior, and only dimensions actually active and processed by the builder.

The most reliable check is to call **MatrixBuilder.build_experiment()** and count the returned configurations. Alternatively, consume **iter_experiment()** completely. Full iteration updates **configuration_count** and, through it, **total_image_count**. A partially consumed generator does not provide a final count.

## 7. Styles and Random Style

Example:

    "styles": ["Fooocus V2", "Fooocus Enhance"],
    "available_styles": ["Fooocus V2", "Fooocus Enhance"],
    "random_style": false,
    "random_style_count": 1

- **styles** contains the styles actually selected.
- **available_styles** documents the available Fooocus style pool.
- **random_style** enables random selection from styles.
- **random_style_count** is the number of styles drawn per base combination.

Current builder behavior:

- With **random_style = false**, styles are processed through **matrix.styles** as a regular dimension.
- With **random_style = true**, the regular style dimension is omitted. The builder randomly samples from **styles** for each base combination.
- Each selected style creates a separate GenerationConfiguration.
- random_style_count is effectively at least 1.
- Random Style with an empty styles list fails.
- A random_style_count greater than the number of selected styles fails.

**available_styles is not used for selection by MatrixBuilder.** The actual selection list is **styles**. Never invent style names; use names confirmed in the installed style pool.

Random Style does not guarantee the same selection on every run. For reproducible style comparisons, use the regular style matrix with explicit selections.

## 8. Reference images

**style_references** and **composition_references** contain objects such as:

    {
      "reference_id": 1,
      "path": "Experiment/style/001_reference.png",
      "reference_type": "STYLE"
    }

| Field | Type | Rule |
|---|---|---|
| reference_id | Integer | Required reference ID |
| path | String | Path to the actual image file |
| reference_type | Enum string | STYLE or COMPOSITION |

The type must match the list: style_references → STYLE; composition_references → COMPOSITION.

Rules:
1. Never invent reference paths.
2. Every referenced file must exist before import.
3. Use empty arrays when there are no references.
4. For externally created JSON, relative paths must match the planned experiment location, or accessible absolute paths must be supplied.
5. On save, the store copies files into the revision and writes relative paths into the saved JSON.
6. Never modify or remove previous revision folders or their reference data.

## 9. Complete schema example

This example uses prompt blocks, two fixed seeds, and a numeric Guidance Scale matrix. It has no reference images or unverified style names.

    {
      "experiment_id": "20261101-001",
      "name": "Cyberpunk Erlenmeyer",
      "version": 1,
      "status": "DRAFT",
      "created_at": "2026-11-01T12:00:00",
      "updated_at": "2026-11-01T12:00:00",
      "positive_prompts": [],
      "negative_prompts": [
        {"slot_id": 1, "text": "blurry, low quality, distorted geometry", "fixed": true}
      ],
      "prompt_blocks": [
        {
          "block_id": "A",
          "name": "Subject",
          "prompts": [
            {"slot_id": 1, "text": "a glass Erlenmeyer flask", "fixed": false},
            {"slot_id": 2, "text": "a futuristic glass Erlenmeyer flask", "fixed": false}
          ],
          "matrix_selection": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null}
        },
        {
          "block_id": "B",
          "name": "Lighting",
          "prompts": [
            {"slot_id": 1, "text": "cyan and magenta neon lighting", "fixed": false},
            {"slot_id": 2, "text": "dramatic volumetric lighting", "fixed": false}
          ],
          "matrix_selection": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null}
        }
      ],
      "styles": [],
      "available_styles": [],
      "random_style": false,
      "random_style_count": 1,
      "style_references": [],
      "composition_references": [],
      "generation": {
        "width": 1024,
        "height": 768,
        "aspect_ratio": "4:3",
        "seed_mode": "FIXED",
        "seed": 12345,
        "seeds": [12345, 23456],
        "random_seed_count": 1,
        "random_seed_fixed": true,
        "random_seeds": [],
        "performance": null,
        "guidance_scale": null,
        "sharpness": null,
        "base_model": null,
        "base_models": [],
        "refiner_model": null,
        "refiner_switch": null,
        "output_format": "png"
      },
      "matrix": {
        "positive_prompts": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
        "negative_prompts": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
        "styles": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
        "seeds": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
        "style_references": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
        "composition_references": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
        "base_models": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
        "refiner_models": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
        "lora_configurations": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
        "guidance_scale": {"enabled": true, "minimum": 2.0, "maximum": 8.0, "steps": 4},
        "sharpness": {"enabled": false, "minimum": null, "maximum": null, "steps": 1},
        "resolution": {"enabled": false, "dimension": "width", "minimum": null, "maximum": null, "steps": 3}
      },
      "configuration_count": 0,
      "total_image_count": 0,
      "estimated_runtime_seconds": null,
      "estimated_storage_bytes": null,
      "test_run_completed": false
    }

### 9.1 Expected configuration count

- Block A: 2 variants.
- Block B: 2 variants.
- Prompt-block product: 2 × 2 = 4 variants.
- Guidance Scale: 4 values (2.0, 4.0, 6.0, 8.0).
- Fixed seeds: 2.
- Negative prompt: fixed, so it adds no multiplicative dimension.

Expected result: **4 × 4 × 2 = 32 GenerationConfigurations.**

The counters are intentionally 0. They are derived values updated by a fully executed builder; they are not evidence that images have already been generated.

## 10. AI workflow for creating an experiment

1. **Clarify the research question:** What is being compared or investigated? Identify the hypothesis or factor of interest.
2. **Define the baseline:** Keep all parameters not under investigation constant.
3. **Select dimensions:** Enable only dimensions that are actually needed.
4. **Choose prompt structure:** Use prompt blocks for new independent positive-prompt dimensions. Use legacy positive prompts only for backward compatibility.
5. **Define values and operators:** Match matrix operators to the intended comparison.
6. **Define seeds:** Use explicit seeds or fixed-random mode for reproducible comparisons.
7. **Build JSON from the current model:** Use correct field names, types, enums, and required timestamps.
8. **Determine the configuration count:** Account for active dimensions, prompt blocks, seeds, and Random Style rules.
9. **Validate:** Check JSON syntax, store loading, builder execution, reference files, style names, and Fooocus parameters.
10. **Deliver:** Provide the JSON, a brief description of the experiment logic, baseline, varied factors, and expected configuration count.

## 11. Validation checklist

Before delivering an experiment file:

- [ ] Valid UTF-8 JSON.
- [ ] **Filename ends exactly with `_exp.json` (mandatory for discovery by the LOAD command).**
- [ ] experiment_id, created_at, and updated_at are present.
- [ ] Timestamps parse with datetime.fromisoformat().
- [ ] Status value is valid.
- [ ] PromptSlots have valid slot_id values and correctly typed text/fixed fields.
- [ ] Prompt block IDs are single alphabetic characters.
- [ ] Every prompt block has a valid matrix_selection.
- [ ] Slot IDs are unique within their list or block.
- [ ] Legacy positive prompts and prompt blocks are not unintentionally used together.
- [ ] All operators are valid.
- [ ] PERMUTATION and COMBINATION bounds are valid.
- [ ] Enabled numeric dimensions have minimum, maximum, and valid steps.
- [ ] NumericMatrixSelection with steps > 1 has maximum > minimum.
- [ ] Enabled resolution matrix has a valid axis, bounds, and steps.
- [ ] All derived resolutions are within model limits.
- [ ] Both width and height are divisible by 8 for Fooocus.
- [ ] generation.aspect_ratio matches the base dimensions.
- [ ] Seeds and seed mode match the experiment plan.
- [ ] Persisted seeds are accounted for after building RANDOM experiments with random_seed_fixed = true.
- [ ] Random Style uses only confirmed names from styles.
- [ ] Reference images actually exist.
- [ ] Refiner and base-model assumptions match supported fields.
- [ ] LoRA is not assumed to be an active matrix dimension.
- [ ] Expected configuration count is verified with the current MatrixBuilder.
- [ ] configuration_count and total_image_count are not confused with images already generated.
- [ ] Existing revisions and reference folders are not overwritten or deleted.

## 12. Do not assume without verification

Check the following against the installed Fooocus version, current runtime, or actual application execution:

- Accepted ranges for Guidance Scale, Sharpness, and Refiner Switch.
- Whether a style name exists in the installed Fooocus version.
- Whether a base model or refiner model is installed and usable.
- Whether reference paths exist on the target machine and are readable by the application.
- Whether additional parameters are actually passed to generation by the Fooocus bridge.
- Whether the generated dimensions are accepted by the specific Fooocus version.
- Whether the experiment can not only be loaded but also executed successfully.

A field's existence in the JSON model does not prove that every downstream component supports it.

## 13. Final instructions to the AI

Create valid, comprehensible, and reproducible Desperate Render experiments. Use only documented fields and valid values. Derive matrix, prompt-block, seed, and Random Style behavior from the actual implementation.

Do not invent reference files, style names, model names, or parameter limits. Always distinguish between:

- the saved experiment definition,
- GenerationConfigurations produced by MatrixBuilder,
- jobs actually queued or executed,
- images and result data actually generated.

Calculate the expected configuration count and, where possible, verify it by loading the experiment with the current ExperimentStore and fully building it with the current MatrixBuilder. Clearly label assumptions that could not be verified through code or runtime tests.

**Quality goal:** The experiment file must load in the current version of Desperate Render and produce exactly the intended generation configurations. Syntactically valid JSON that has not passed store and builder validation is not yet a verified experiment.
