# MarketStimulator
Simulates a simplified exchange where multiple "bot" agents trade a single stock.

## Setup (Pro)
Follow these steps to set up a local environment (recommended):

1. Create a virtual environment:

   - Windows: `python -m venv venv`

2. Activate the venv:

   - Windows PowerShell: `.\venv\Scripts\Activate`
   - Windows CMD: `venv\\Scripts\\activate.bat`
   - Mac/Linux: `source venv/bin/activate`

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Run the simulation

With the venv active, run:

```bash
python simulate.py
```

This runs a 100-tick simulation and writes `market_simulation.png` in the project root.

## Files

- `market_engine.py` — engine with a random-walk true price, order book, and very small matcher
- `bots.py` — `MarketMaker` that posts symmetric buy/sell orders around the true price
- `simulate.py` — script to run the simulation and save a plot
- `requirements.txt` — project dependencies (numpy, matplotlib)

## Notes

- The true price is generated using a NumPy random walk (`np.random.normal`).
- The `MarketMaker` provides simple liquidity and helps generate trades you can visualize.
