import time, math, uuid

class OMS:
    """
    Tiny order layer around ccxt.delta with:
      - tick/lot rounding
      - reduce_only / post_only / tif support
      - consistent client IDs (GBOT_*).
    """

    def __init__(self, ex, symbol, logger, client_prefix="GBOT"):
        self.ex = ex
        self.symbol = symbol
        self.log = logger
        self.prefix = client_prefix
        m = self.ex.market(symbol)
        # Derive tick & lot
        self.tick = None
        self.lot  = None
        # ccxt may expose precision or limits; be defensive:
        if "limits" in m and m["limits"].get("price", {}).get("min"):
            self.tick = float(m["limits"]["price"]["min"])
        elif "precision" in m and m["precision"].get("price") is not None:
            self.tick = 10 ** (-int(m["precision"]["price"]))
        else:
            self.tick = 0.5  # observed on BTCUSD at Delta; safe default

        if "limits" in m and m["limits"].get("amount", {}).get("min"):
            self.lot = float(m["limits"]["amount"]["min"])
        elif "precision" in m and m["precision"].get("amount") is not None:
            self.lot = 10 ** (-int(m["precision"]["amount"]))
        else:
            self.lot = 1.0

    # ---------- helpers ----------
    def _round_price(self, p):
        step = float(self.tick)
        return round(round(p / step) * step, 10)

    def _round_size(self, s):
        step = float(self.lot)
        q = math.floor(s / step) * step
        return max(step, round(q, 10))

    def _cid(self, tag):
        return f"{self.prefix}_{tag}_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"

    def fetch_open(self):
        return self.ex.fetch_open_orders(self.symbol)

    def fetch_order(self, order_id):
        return self.ex.fetch_order(order_id, self.symbol)

    def cancel_order(self, order_id):
        try:
            return self.ex.cancel_order(order_id, self.symbol)
        except Exception:
            return None

    def place_limit(self, side, price, size, *, reduce_only=False, post_only=False, tif="GTC", tag=""):
        price = self._round_price(price)
        size  = self._round_size(size)
        params = {
            "reduce_only": bool(reduce_only),
            "reduceOnly": bool(reduce_only),  # both spellings just in case
            "post_only": bool(post_only),
            "postOnly": bool(post_only),
            "timeInForce": tif,
            "client_order_id": self._cid(tag),
            "clientOrderId":   self._cid(tag),
        }
        o = self.ex.create_order(self.symbol, "limit", side, size, price, params)
        return o, price, size
