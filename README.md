
# HMT Engineering Solver

A Streamlit-based application for solving Heat and Mass Transfer engineering problems.

## Features

- Methane combustion and adiabatic flame temperature
- Parallel-flow heat-exchanger calculations
- Heat-transfer rate, LMTD, and heat-transfer area
- Energy-balance checks
- Engineering graphs and downloadable PDF reports
- Forced convection over a flat plate

## Technologies

- Python
- Streamlit
- Cantera
- CoolProp
- NumPy and SciPy
- Matplotlib
- ReportLab

## Installation

Install the dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
streamlit run app.py
```

## Project Files

- `app.py` — Main application interface
- `calculations.py` — Heat-exchanger calculation engine
- `convection_app.py` — Forced-convection interface
- `flat_plate.py` — Flat-plate calculations
- `requirements.txt` — Python dependencies