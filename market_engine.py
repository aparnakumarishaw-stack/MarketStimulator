"""market_engine.py — a small matching engine used for the project tests

Implements:
- MarketEngine: simple random-walk true price, limit order book, matching, and market orders
- Methods used by the tests: place_order, _match_orders, execute_market_order, get_cumulative_depth
- calculate_price_impact: simulates filling a market order (without mutating the book) and returns slippage in bps
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd


class MarketEngine:
    """A very small matching engine for testing and demo purposes.

    Orders are simple dicts: {'side': 'buy'|'sell', 'price': float, 'size': float, 'bot': Any}
    """

    def __init__(self, init_price: float = 100.0, vol: float = 0.5, rng: np.random.Generator | None = None):
        self.true_price = float(init_price)
        self.vol = float(vol)
        self.rng = rng if rng is not None else np.random.default_rng()

        self.order_book: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.bots: List[Any] = []
        self.true_history: List[float] = [self.true_price]
        self.tick = 0
        self._order_id = 0

    def register_bot(self, bot: Any) -> None:
        self.bots.append(bot)

    def place_order(self, order: Dict[str, Any]) -> None:
        """Add an order to the book. Orders are expected to contain 'side','price','size','bot'.
        This method does not run the matcher; call `_match_orders()` or `step()` to match."""
        o = dict(order)
        o['price'] = float(o['price'])
        o['size'] = float(o['size'])
        o['side'] = str(o['side'])
        o['_id'] = self._order_id
        self._order_id += 1
        self.order_book.append(o)

    def step(self) -> None:
        """Advance one tick: update true price, let bots post orders, then match."""
        self.tick += 1
        # simple random-walk for the latent price
        self.true_price += float(self.rng.normal(0, self.vol))
        self.true_history.append(self.true_price)

        for bot in list(self.bots):
            try:
                bot.on_tick(self)
            except Exception:
                # keep engine robust in tests
                pass

        self._match_orders()

    def _sorted_book(self, side: str) -> List[Dict[str, Any]]:
        """Return a list of orders for a side sorted by price/time priority.
        - For 'buy': highest price first, earlier ids first
        - For 'sell': lowest price first, earlier ids first
        """
        side = str(side)
        side_orders = [o for o in self.order_book if o['side'] == side]
        if side == 'buy':
            return sorted(side_orders, key=lambda x: (-x['price'], x['_id']))
        else:
            return sorted(side_orders, key=lambda x: (x['price'], x['_id']))

    def _match_orders(self) -> None:
        """Match resting buys and sells using price/time priority.

        When a buy.price >= sell.price we execute a trade. Trade price is the midpoint
        between the two order prices (to reflect an aggressive limit crossing behavior).
        """
        while True:
            buys = self._sorted_book('buy')
            sells = self._sorted_book('sell')
            if not buys or not sells:
                break
            best_buy = buys[0]
            best_sell = sells[0]
            if best_buy['price'] < best_sell['price']:
                break

            trade_size = min(best_buy['size'], best_sell['size'])
            trade_price = 0.5 * (best_buy['price'] + best_sell['price'])

            # record trade
            trade = {'price': float(trade_price), 'size': float(trade_size), 'tick': self.tick}
            self.trade_history.append(trade)

            # reduce sizes and purge zero-sized orders
            best_buy['size'] -= trade_size
            best_sell['size'] -= trade_size

            self.order_book = [o for o in self.order_book if o['size'] > 0]

    def execute_market_order(self, side: str, quantity: float) -> Dict[str, Any]:
        """Execute a market sweep without adding an order to the book.

        For a buy market order we consume sells from best to worst and vice versa.
        Return a summary with executed_size, unfilled_size, and vwap (None if no fill).
        """
        side = str(side)
        qty_remaining = float(quantity)
        total_cost = 0.0
        executed = 0.0

        # passive side
        passive_side = 'sell' if side == 'buy' else 'buy'
        passive = self._sorted_book(passive_side)

        for o in list(passive):
            if qty_remaining <= 0:
                break
            take = min(qty_remaining, o['size'])
            total_cost += take * o['price']
            qty_remaining -= take
            executed += take
            # mutate the real book to remove consumed quantity
            # find the order in self.order_book by id and reduce/remove
            for real in self.order_book:
                if real['_id'] == o['_id']:
                    real['size'] -= take
                    break

        # purge zero-sized orders
        self.order_book = [o for o in self.order_book if o['size'] > 0]

        vwap = (total_cost / executed) if executed > 0 else None
        return {'executed_size': executed, 'unfilled_size': float(quantity) - executed, 'vwap': vwap}

    def load_snapshot(self, snapshot: list[Dict[str, Any]]) -> None:
        """Replace the current order book with the provided snapshot.

        Each order in `snapshot` should be a dict with at least `side`, `price`, and `size`.
        This method assigns internal `_id` values so the engine can reference orders.
        """
        self.order_book = []
        for o in snapshot:
            new = dict(o)
            new['price'] = float(new['price'])
            new['size'] = float(new['size'])
            new['side'] = str(new['side'])
            new['bot'] = new.get('bot', None)
            new['_id'] = self._order_id
            self._order_id += 1
            self.order_book.append(new)

    def simulate_market_order(self, side: str, quantity: float, book: list[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        """Simulate a market sweep on a copy of the provided `book` (or current book)
        and return a dict like `execute_market_order` plus the simulated resulting book
        (a list of orders with reduced sizes). This method does not mutate engine state.
        """
        side = str(side)
        qty_remaining = float(quantity)
        total_cost = 0.0
        executed = 0.0

        if book is None:
            # work on a deep-ish copy of the current book
            sim_book = [dict(o) for o in self.order_book]
        else:
            sim_book = [dict(o) for o in book]

        passive_side = 'sell' if side == 'buy' else 'buy'
        # select passive orders sorted by price/time priority
        passive = [o for o in sim_book if o['side'] == passive_side]
        if passive_side == 'sell':
            passive = sorted(passive, key=lambda x: (x['price'], x['_id']))
        else:
            passive = sorted(passive, key=lambda x: (-x['price'], x['_id']))

        for o in passive:
            if qty_remaining <= 0:
                break
            take = min(qty_remaining, o['size'])
            total_cost += take * o['price']
            qty_remaining -= take
            executed += take
            # reduce in the sim_book by id
            for real in sim_book:
                if real['_id'] == o['_id']:
                    real['size'] -= take
                    break

        # remove zero-sized
        sim_book = [o for o in sim_book if o['size'] > 0]
        vwap = (total_cost / executed) if executed > 0 else None
        return {'executed_size': executed, 'unfilled_size': float(quantity) - executed, 'vwap': vwap, 'book': sim_book}

    def get_cumulative_depth(self) -> pd.DataFrame:
        """Return a DataFrame with columns: side, price, cum_size"""
        if not self.order_book:
            return pd.DataFrame(columns=['side', 'price', 'cum_size'])

        df = pd.DataFrame(self.order_book)
        out = []
        for side in ('buy', 'sell'):
            s = df[df['side'] == side]
            if s.empty:
                continue
            grouped = s.groupby('price', as_index=False)['size'].sum()
            if side == 'buy':
                grouped = grouped.sort_values('price', ascending=False)
                grouped['cum_size'] = grouped['size'].cumsum()
            else:
                grouped = grouped.sort_values('price', ascending=True)
                grouped['cum_size'] = grouped['size'].cumsum()
            grouped['side'] = side
            out.append(grouped[['side', 'price', 'cum_size']])

        return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=['side', 'price', 'cum_size'])

    def calculate_price_impact(self, side: str, quantity: int) -> float:
        """Simulate a market order of size `quantity` and return slippage in bps.

        Uses the current order book and does not mutate it. The mid-price is taken
        as (best_bid + best_ask) / 2. If either side is missing, returns 0.
        """
        # find best bid and ask
        bids = [o for o in self.order_book if o['side'] == 'buy']
        asks = [o for o in self.order_book if o['side'] == 'sell']
        best_bid = max([b['price'] for b in bids]) if bids else None
        best_ask = min([a['price'] for a in asks]) if asks else None
        if best_bid is None or best_ask is None:
            return 0.0

        mid = 0.5 * (best_bid + best_ask)

        qty_remaining = float(quantity)
        total_cost = 0.0
        filled = 0.0

        if side == 'buy':
            # consume asks from best to worst
            sims = sorted(asks, key=lambda x: (x['price'], x['_id']))
            for o in sims:
                if qty_remaining <= 0:
                    break
                take = min(qty_remaining, o['size'])
                total_cost += take * o['price']
                filled += take
                qty_remaining -= take
        else:
            # sell: consume bids from best (high) to worst
            sims = sorted(bids, key=lambda x: (-x['price'], x['_id']))
            for o in sims:
                if qty_remaining <= 0:
                    break
                take = min(qty_remaining, o['size'])
                total_cost += take * o['price']
                filled += take
                qty_remaining -= take

        if filled == 0:
            return 0.0

        avg_exec_price = total_cost / filled
        if side == 'buy':
            impact_bps = (avg_exec_price / mid - 1.0) * 10000.0
        else:
            impact_bps = (1.0 - avg_exec_price / mid) * 10000.0
        return float(impact_bps)

