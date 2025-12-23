I think we have created robust system which are async grid bot, recovery system and reconciliation system. But the issue is they are not in sync. We need to decide there work flow and make them in sync.

When a user start a bot by webUI pm2, in long mode or short mode first recovery system by default should trigger and it should first check is guardian bot is giving go or not. If guardian bot is giving go then it should start the recovery system. If guardian bot is not giving go then it should not start the recovery system, and wait for a go signal to start the recovery system, so right now if guardian is not giving go signal then it is waiting for signal to be green(go).

As guardian give it a green signal then it should check missed grids, if missed grid are not available then it should send a signal to the normal async grid bot to start the normal grid bot or if missed grids are available then it should first place market order for those missed grids and then their corresponding tp order, then it should set its flag to false and normal async grid bot signal to true until next restart.
 As normal grid system receive the go signal from recovery system it should first set the startup recovery system to false and normal grid signal true until next restart of the bot. After setting it false now async grid bot should look for guardian go signal if its red then it should wait for the green signal. After getting go signal from guardian bot it should send a signal or read reconcillation/exchange for already available grid step with the orders only placed by the bot. reconcillation has no data for the grid it want to send a buy signal then it should start its normal operation without looking at the recovery system or reconcillation. Then async grid bot resume its grid buy/sell behaviour till the guardian bot is having a go signal. As guardain bot gives halt or red signal then normal async bot set its signal to false and recovery system signal to true. 
 Now recovery system has true signal and async grid bot has false. and guardian is giving red signal so recovery system wait for signal to be green(go).as its signal go green it look for missed grid if there are no missed grid or grids are missed then it should cover those missed grid by market order and tp order as we planned and then set its signal to false and normal async grid bot signal to true until next halt. 
 as normal grid bot receive the signal from recovery system it should set its signal to true and flag recovery system to false until next halt. 

 this process goes on with the guardian bot signal. 
 in this way all system will be in sync. In the meanwhile reconcillation system keeps on checking the order system every 5 minutes.  

 # Bot System Sync Flow Diagram (Mermaid)

```
[ IMPROVED, CLEAN, STEP‑BY‑STEP FLOW ]

1. USER STARTS BOT (WebUI / PM2 → Long/Short Mode)
        ↓
2. RECOVERY SYSTEM STARTS FIRST (always)
        ↓
3. RECOVERY CHECKS GUARDIAN BOT
        ↓
    ┌─────────── RED (HALT) ────────────┐
    │                                   ↓
    │                        WAIT UNTIL GREEN
    │                                   ↓
    └────────── GREEN (GO) ───────────→ CONTINUE

4. RECOVERY CHECKS FOR MISSED GRIDS
        ↓
    ┌─────────────── NO MISSED ────────────────┐
    │                                          ↓
    │                          SEND SIGNAL → ASYNC BOT START
    │                                          ↓
    └────────────→ SET RECOVERY = FALSE, ASYNC = TRUE

    ┌─────────────── MISSED FOUND ─────────────┐
    │                                          ↓
    │              PLACE MARKET + TP ORDERS FOR MISSED GRIDS
    │                                          ↓
    │               SET RECOVERY = FALSE, ASYNC = TRUE
    └───────────────────────────────────────────

5. ASYNC GRID BOT STARTS
        ↓
6. ASYNC SETS FLAGS: RECOVERY = FALSE, ASYNC = TRUE
        ↓
7. ASYNC CHECKS GUARDIAN
        ↓
    ┌───────── RED ─────────┐
    │                       ↓
    │             WAIT UNTIL GREEN
    │                       ↓
    └───────── GREEN ─────→ RECONCILIATION CHECK

8. ASYNC → RECONCILIATION / EXCHANGE CHECK
        ↓
    ┌──────── NO BOT DATA ─────────┐
    │                              ↓
    │            IGNORE RECON → START NORMAL BUY/SELL GRID LOGIC
    │                              ↓
    └──────── VALID DATA ─────────→ RESUME NORMAL GRID OPS

9. ASYNC RUNS NORMAL BUY/SELL LOOP
        ↓
10. IF GUARDIAN TURNS RED DURING RUN
        ↓
SET ASYNC = FALSE
SET RECOVERY = TRUE
        ↓
RETURN TO RECOVERY LOOP

11. RECOVERY LOOP RESTARTS (Guardian still RED)
        ↓
    WAIT UNTIL GUARDIAN GREEN
        ↓
    CHECK MISSED GRIDS AGAIN
        ↓
    ┌──────── NO MISSED ─────────┐      ┌──────── MISSED FOUND ───────┐
    │                             ↓      │                              ↓
    │            ASYNC = TRUE           │          COVER MISSED GRIDS
    │          RECOVERY = FALSE         │     (Market + TP for each grid)
    │                             ↓      │                              ↓
    └──────────→ ASYNC RESUMES          └────────→ ASYNC RESUMES

12. THE CYCLE CONTINUES BASED ON GUARDIAN SIGNALS

Parallel Process:
• RECONCILIATION SYSTEM RUNS EVERY 5 MINUTES
• IT ONLY READS EXCHANGE AND STORED BOT ORDERS
```
