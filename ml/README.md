# Anilla ML — Phase 2 Training Data Pipeline

Builds the training dataset for the NLP + triage clustering layer.

## Setup

```bash
cd ml
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Data Sources

### MTSamples (recommended first step)

1. Go to https://www.kaggle.com/datasets/tboyle10/medicaltranscriptions
2. Download `medicaltranscriptions.zip`
3. Unzip and place CSV at `ml/data/raw/mtsamples.csv`

Or with the Kaggle CLI:
```bash
kaggle datasets download -d tboyle10/medicaltranscriptions
unzip medicaltranscriptions.zip -d ml/data/raw/
```

### Synthea (synthetic patients, no restrictions)

1. Download the JAR from https://github.com/synthetichealth/synthea/releases
   → `synthea-with-dependencies.jar`
2. Generate data (5,000 patients recommended):
```bash
java -jar synthea-with-dependencies.jar \
  -p 5000 \
  --exporter.csv.export=true \
  --exporter.fhir.export=false \
  -o ml/data/raw/synthea
```

## Run the Pipeline

```bash
# From project root
python ml/pipeline.py                  # both sources
python ml/pipeline.py --source mtsamples
python ml/pipeline.py --source synthea
python ml/pipeline.py --format csv     # CSV instead of parquet
```

## Output

```
ml/output/
  train.parquet   (~70% of rows, stratified by triage_cluster)
  val.parquet     (~15%)
  test.parquet    (~15%)
  stats.json      — cluster distribution, row counts
```

### Schema

| Column | Type | Description |
|--------|------|-------------|
| `source` | str | `"mtsamples"` or `"synthea"` |
| `source_id` | str | Original row ID |
| `raw_text` | str | Chief complaint / free-text |
| `extracted_features` | JSON str | SymptomExtractor output — symptoms, severity, duration, red flags |
| `triage_cluster` | str | One of 8 clusters (see `config.yaml`) |
| `specialty` | str | Original specialty label (audit trail) |
| `split` | str | `train` / `val` / `test` |

## Triage Clusters

Defined in `config.yaml` — edit there to add/rename clusters without touching code:

- `cardiac`
- `respiratory`
- `neurological`
- `musculoskeletal`
- `gastrointestinal`
- `mental_health`
- `dermatological`
- `preventive`
- `other`

## Adding MIMIC-IV-ED (after PhysioNet credentialing)

Once you have MIMIC-IV-ED access, add a `ml/data/sources/mimic.py` loader
following the same interface as `mtsamples.py` and `synthea.py`:
- Returns a DataFrame with columns: `source_id`, `raw_text`, `specialty`
- Pass it through the same `ClusterMapper` + `SymptomExtractor` pipeline
- MIMIC ED triage notes map directly to `triage_cluster` via ESI levels
