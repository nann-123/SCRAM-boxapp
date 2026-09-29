# Config Mapping Spec

The GUI does not expose the SCRAM cfg file as one long form. It reorganizes the same semantics into workflow cards and structured tables while preserving parser/serializer compatibility.

## Workflow Cards

- `Experiment and Scheme`
  - experiment name
  - template / preset
  - case preset
  - mixing assumption: `INTERNAL_MIXING` or `EXTERNAL_MIXING`
- `Process Toggles and Mixing Notes`
  - coagulation toggle
  - condensation / evaporation toggle
  - nucleation toggle
  - internal/external mixing explanation
- `Runtime and Output`
  - simulation time
  - minimum timestep (dead control — greyed out; the core reads `dtmin` but never uses it)
  - output directory
- `Environment and Initial State`
  - temperature
  - pressure
  - humidity
  - initial scenario
  - initial external-mixing placement flag
  - density mode
  - fixed density
- `Advanced Controls`
  - coefficient file
  - sulfate computation
  - nucleation model
  - groups / solver / thermodynamic / grid / composition fields

## Conditional Visibility

- `INTERNAL_MIXING`
  - shows the note explaining the single-average-composition assumption per size section
- `EXTERNAL_MIXING`
  - shows the note explaining the size-composition grid and mixed/unmixed particle diagnostics
- `with_cond = 0`
  - hides condensation-specific controls
- `with_nucl = 0`
  - hides nucleation model controls
- `tag_external = 0`
  - hides external-initial-state advanced fields

## Structured Tables

### Species Table

Columns:

- `species_id`
- `species_name`
- `group_id`
- `init_gas`
- `emission`
- `notes`

### Size Bins Table

Columns:

- `bin_id`
- `lower_bound`
- `upper_bound`
- `representative_diameter`
- `initial_number`
- `notes`

### Fraction Table

Columns:

- `fraction_id`
- `lower_bound`
- `upper_bound`
- `notes`

### Emission Table

- one row per species
- one column per size bin plus an actions column with add/remove controls
- serialized back to SCRAM emission rows for compatibility

### Initial Mass Table

- one row per species
- one column per size bin
- cells map to `species_records[*].bin_values`

## Dimension-Driven Regeneration

The following scalar fields drive table size:

- `n_species`
- `n_sizebin`
- `n_frac`

Changing these values and clicking `Generate Structure` rebuilds the table skeleton while preserving compatible values where possible.

## Serialization and Deserialization

- parsing reads the current SCRAM config semantics
- serialization rebuilds the config body from the current table dimensions
- species comments are mapped into `species_name` and `notes`
- cfg loading must render parsed values directly into the GUI tables before any table-derived collection occurs

## Validation Rules

- `n_species` must match species table row count
- `n_sizebin` must match the size-bin table, emission table width, and initial mass table width
- diameter bounds must be strictly increasing and have length `n_sizebin + 1`
- fraction bounds must be strictly increasing, start at `0`, end at `1`, and have length `n_frac + 1`
- mixing assumption must be `INTERNAL_MIXING` or `EXTERNAL_MIXING`


## 2026-09-29 GUI changes (keep this spec in sync)

- **Mixing assumption** is no longer locked: the combo's initial value is inferred from the loaded cfg (`n_frac == 1`
  → `INTERNAL_MIXING`, else `EXTERNAL_MIXING`) and may be changed freely. Compare runs always run both arms and
  ignore this combo.
- **Config preview now shows what is actually sent to the core**: `_render_preview_text()` runs the same
  `RunService.transform_config` pipeline as `prepare_run` and prepends a header with the rewritten keys and the
  two-arm diff keys.
- **`nucl_model`** is a two-option combo (1 = ternary nucleation, 5 = paper validation mode). Selecting 5 switches
  and locks the species table to the 30-species baseline layout (slot 2 = BC/group 4, slot 4 = SO4/group 1).
- **`tag_init`** gained a control: `Initial values from` (1 = per-bin masses in the cfg, 0 = built-in scenario
  distributions). With 0 the per-bin mass table is greyed out and the serializer emits the 5-column short species
  rows (species total mass = sum of per-bin masses).
- **Input guards** in `ConfigModel.validate()`: zero-mass input (U-06a), `nucl_model=5` layout mismatch (U-07),
  and the undefined `(tag_init=0, tag_external=0, n_frac>1)` combination (1.1 core reads uninitialized memory there).
  Loading a bad cfg now warns immediately; running is still blocked until it is fixed.
- **`mapping_scheme`** is wired through to `SCRAM_COEFF_REPARTITION_MODE` (it was silently forced to
  `COAG_TARGET_NEAREST` before).
- **Paths** handed to the core are ASCII-only (`RunService.ascii_name`), and `SCRAM_RESULTS_DIR` is always absolute
  (the 1.2 core reads it; a relative value made the result collector read misaligned outputs).
