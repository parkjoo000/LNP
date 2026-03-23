# Column Pattern Dictionary

Used by file-classifier (STEP 2) to identify assay type from CSV header row.
All matching is case-insensitive. Aliases are listed under each instrument.

---

## physical — Dynamic Light Scattering / Nanoparticle Tracking Analysis

### Zetasizer_v3 (Malvern Panalytical)
**Required columns** (all three must be present for HIGH confidence):
- `Z-Ave (d.nm)` | `Z-Avg (d.nm)` | `Z-Average (d.nm)`
- `PdI` | `PDI` | `Polydispersity Index`
- `Zeta Potential (mV)` | `Zeta (mV)`

Optional: `Intercept`, `Result Quality`, `Cumulants Fit`

### NanoSight NS300 (Malvern)
**Required columns** (any two sufficient):
- `Mean` | `Mean Diameter (nm)`
- `Mode` | `Mode Diameter (nm)`
- `D10` | `D50` | `D90`
- `Concentration (particles/ml)`

### ZetaView (Particle Metrix)
**Required columns**:
- `Size [nm]` | `Size (nm)`
- `PDI` | `Polydispersity`
- `Zeta Potential [mV]`

### Generic_physical (fallback — MEDIUM confidence)
Any two of: `Size`, `Diameter`, `PDI`, `Zeta`, `EE%`, `Encapsulation Efficiency`, `nm`

---

## invivo_fluc — IVIS Bioluminescence (Luciferase / FLUC)

### LivingImage_4x (PerkinElmer)
**Required columns** (all must be present for HIGH confidence):
- `Total Flux [p/s]` | `Total Flux (p/s)` | `Total Flux`
- `Average Radiance [p/s/cm²/sr]` | `Avg Radiance`
- `ROI` | `Region`

Optional: `Min Radiance`, `Max Radiance`, `Area [cm²]`, `Image`, `Subject`

### LivingImage_export_csv (PerkinElmer — tabular export)
**Required columns**:
- `Measurement` | `Value`
- `Unit`
- `Image` | `Acquisition`

### Generic_FLUC (fallback — MEDIUM confidence)
Any of: `Flux`, `Bioluminescence`, `Radiance`, `Luminescence`, `Photons`

---

## invivo_epo — ELISA Plate Reader (Erythropoietin)

### SpectraMax_EPO (Molecular Devices)
**Required columns** (all must be present for HIGH confidence):
- `Well` | `Well ID`
- `OD 450` | `OD450` | `Absorbance at 450`
- `Sample` | `Sample ID`
- `Dilution Factor` | `Dilution`

Optional: `Corrected OD`, `Concentration (pg/mL)`, `% CV`

### Generic_ELISA (fallback — MEDIUM confidence)
Any two of: `OD450`, `Absorbance`, `Conc`, `pg/mL`, `ng/mL`, `Concentration`

---

## toxicity — Blood Chemistry Analyzer

### Fuji_DriChem (FUJIFILM)
**Required columns** (all must be present for HIGH confidence):
- `ALT(GPT)` | `ALT (U/L)` | `ALT`
- `AST(GOT)` | `AST (U/L)` | `AST`
- `BUN` | `BUN (mg/dL)`

Optional: `CREA`, `TBIL`, `ALP`, `GGT`, `Date`, `Animal ID`

### Hitachi_7180 (Roche/Hitachi)
**Required columns**:
- `Alanine aminotransferase` | `Alanine Aminotransferase`
- `Aspartate aminotransferase` | `Aspartate Aminotransferase`
- `Blood Urea Nitrogen` | `Urea Nitrogen`

### VetScan (Abaxis)
**Required columns**:
- `ALT/SGPT`
- `AST/SGOT`
- `BUN/UREA`

Optional: `CREA`, `GLU`, `TP`, `ALB`

### Generic_blood (fallback — MEDIUM confidence)
Any two of: `ALT`, `AST`, `BUN`, `Creatinine`, `CREA`, `Liver`, `Kidney`, `Toxicology`

---

## Confidence Scoring Algorithm

```
required_count = number of required columns for instrument
matched_count  = number of required columns found in header (case-insensitive)
confidence_ratio = matched_count / required_count

HIGH   → ratio == 1.0 (all required columns found)
MEDIUM → 0.6 <= ratio < 1.0
LOW    → ratio < 0.6  → CLASSIFY_FAIL
```

If multiple instruments match at HIGH: choose the one with the highest `matched_count + optional_matched`.
If multiple instruments tie: prefer the more specific (non-Generic) pattern.
