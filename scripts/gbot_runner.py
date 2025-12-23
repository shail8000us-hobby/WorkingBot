#!/usr/bin/env python3
import os, time, json, logging
from pathlib import Path
from dotenv import load_dotenv

from bot.config.aliases import upgrade_mapping
from bot.state.store import load_state_file
from bot.strategy.gbot import GridBotEngine

def setup_log():
    log = logging.getLogger("gbot")
    log.setLevel(logging.INFO)
    h = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    h.setFormatter(fmt)
    log.addHandler(h)
    return log

def main():
    env_path = os.getenv("ENV_PATH", ".env.live")
    load_dotenv(env_path)
    log = setup_log()

    # Read grid/state
    st = load_state_file(Path("state.json"))
    upgrade_mapping(st, record=False)
    lower = float(st["GRIDBOT_LOWER"]); upper = float(st["GRIDBOT_UPPER"])
    step  = float(st["GRIDBOT_STEP"]);  ref   = float(st["GRIDBOT_REF"])
    lot   = float(st.get("GRIDBOT_LOT", 1))

    sym    = os.getenv("DELTA_SYMBOL", "BTC/USD:USD")
    api_k  = os.getenv("DELTA_API_KEY", "")
    api_s  = os.getenv("DELTA_API_SECRET", "")
    base   = os.getenv("DELTA_BASE_URL", "https://api.india.delta.exchange")
    hb     = int(os.getenv("HEARTBEAT_SEC", "5"))
    max_tr = int(os.getenv("MAX_OPEN_TRANCHES", "5"))
    cid    = os.getenv("CLIENT_ID_PREFIX", "GBOT")

    log.info(f"=== GridBot START === sym={sym} REF={ref} STEP={step} bounds=({lower},{upper}) lot={lot} max_tr={max_tr}")

    eng = GridBotEngine(api_key=api_k, api_secret=api_s, base_url=base, symbol=sym,
                        state_path="state.json", logger=log, max_tranches=max_tr, client_prefix=cid)

    last_last = None
    while True:
        ev = eng.on_tick()
        # pretty heartbeat
        try:
            # Use last price from engine's own ticker call by peeking state is not trivial;
            # we just print event kind here. (Your main run.py already shows bids/asks.)
            if ev["event"] == "armed":
                log.info(f"[HB] armed next rung @ {ev.get('rung')}")
            elif ev["event"] == "buy_filled":
                log.info(f"[HB] fill → TP placed @ {ev.get('tp')}")
            elif ev["event"] == "halted_outside_band":
                log.info("[HB] halted (outside band)")
            elif ev["event"] == "max_tranches":
                log.info("[HB] at max tranches; not arming")
        except Exception:
            pass
        time.sleep(hb)

if __name__ == "__main__":
    main()
