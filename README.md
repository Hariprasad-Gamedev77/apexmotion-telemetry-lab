# ApexMotion Telemetry Lab

A motorsport telemetry quality and lap-comparison platform that helps users
discover data defects, compare laps by distance, evaluate measurement reliability,
and produce reproducible engineering reports.

> **All demo data is synthetic.** This application does not use or claim to use
> real Formula 1 or any other real motorsport telemetry.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate sample data
python -m apexmotion.synthetic

# Run tests
pytest

# Launch the app (Milestone 3+)
streamlit run app.py
```

## Project Structure

```
apexmotion/
├── apexmotion/          # Core Python package
│   ├── config.py        # Thresholds, units, defaults
│   ├── loader.py        # CSV loading + schema validation
│   ├── quality.py       # Data-quality rule engine
│   ├── alignment.py     # Distance alignment (Milestone 2)
│   ├── metrics.py       # Lap metrics (Milestone 2)
│   ├── passport.py      # Trust Passport (Milestone 4)
│   └── synthetic.py     # Deterministic demo data generator
├── sample_data/         # Pre-generated CSV files
├── tests/               # pytest test suite
├── docs/                # Documentation
└── app.py               # Streamlit app (Milestone 3)
```

## Testing

```bash
# Run all tests with verbose output
pytest -v

# Run with coverage
pytest --cov=apexmotion --cov-report=term-missing

# Run a specific test file
pytest tests/test_quality.py -v
```

## Documentation

See [docs/schema.md](docs/schema.md) for accepted CSV schema and unit conventions.

## License

MIT
