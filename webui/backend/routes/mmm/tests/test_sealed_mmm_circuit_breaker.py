"""
Contract tests for MMM Circuit Breaker — T2-3

SEALED — v1.0.0 — March 21, 2026
Do not modify without UNSEAL command in AI_SEAL.md

Covers state transitions: CLOSED→OPEN→HALF_OPEN→CLOSED, failure counting, partial beat.

File: webui/backend/routes/mmm/mmm_circuit_breaker.py

--- allow_request contracts ---
C-CB-AR-1: CLOSED → True
C-CB-AR-2: OPEN, timeout not elapsed → False
C-CB-AR-3: OPEN, timeout elapsed → transitions to HALF_OPEN, returns True
C-CB-AR-4: HALF_OPEN → True (one probe allowed)

--- record_success contracts ---
C-CB-RS-1: CLOSED success → stays CLOSED, failure_count resets
C-CB-RS-2: HALF_OPEN success → transitions to CLOSED, open_depth reset
C-CB-RS-3: OPEN success (unexpected) → transitions to CLOSED

--- record_failure contracts ---
C-CB-RF-1: CLOSED, below threshold → stays CLOSED, count increments
C-CB-RF-2: CLOSED, reaches threshold → trips to OPEN, count resets
C-CB-RF-3: HALF_OPEN failure → back to OPEN, open_depth increments
C-CB-RF-4: OPEN failure → failure_count increments (still OPEN)

--- state transitions ---
C-CB-ST-1: Full CLOSED→OPEN→HALF_OPEN→CLOSED cycle
C-CB-ST-2: HALF_OPEN failure deepens backoff (open_depth increases)
C-CB-ST-3: Exponential backoff: depth=1→30s, depth=2→60s, depth=3→120s

--- partial_beat_allowed ---
C-CB-PB-1: depth=1 → True
C-CB-PB-2: depth=2 → True
C-CB-PB-3: depth=3 → False (skip heartbeat entirely)

--- reset ---
C-CB-R-1: Manual reset from OPEN → CLOSED, depth/counts cleared
C-CB-R-2: Reset returns previous state info

--- should_alert ---
C-CB-SA-1: OPEN + consecutive_opens >= 3 → True
C-CB-SA-2: OPEN + consecutive_opens < 3 → False
C-CB-SA-3: CLOSED → False
"""

import pytest
import time


@pytest.fixture
def cb():
    from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitBreaker
    return CircuitBreaker('test-session', failure_threshold=3)


class TestAllowRequest:

    @pytest.mark.sealed
    def test_c_cb_ar_1_closed_allows(self, cb):
        assert cb.allow_request() is True

    @pytest.mark.sealed
    def test_c_cb_ar_2_open_timeout_not_elapsed(self, cb):
        # Trip the breaker
        for _ in range(3):
            cb.record_failure('error')
        assert cb.state.value == 'OPEN'
        assert cb.allow_request() is False

    @pytest.mark.sealed
    def test_c_cb_ar_3_open_timeout_elapsed_goes_half_open(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        for _ in range(3):
            cb.record_failure('error')
        # Manually push last_open_at far back to simulate timeout
        cb._last_open_at = time.monotonic() - 999  # 999s ago > any timeout
        result = cb.allow_request()
        assert result is True
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.sealed
    def test_c_cb_ar_4_half_open_allows(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        # Manually set to HALF_OPEN
        cb._state = CircuitState.HALF_OPEN
        assert cb.allow_request() is True


class TestRecordSuccess:

    @pytest.mark.sealed
    def test_c_cb_rs_1_closed_success_resets_failures(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        cb.record_failure('e')
        cb.record_failure('e')
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    @pytest.mark.sealed
    def test_c_cb_rs_2_half_open_success_closes(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        cb._state = CircuitState.HALF_OPEN
        cb._open_depth = 2
        cb._consecutive_opens = 2
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb._open_depth == 0
        assert cb._consecutive_opens == 0

    @pytest.mark.sealed
    def test_c_cb_rs_3_open_success_closes(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        cb._state = CircuitState.OPEN
        cb._last_open_at = time.monotonic()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED


class TestRecordFailure:

    @pytest.mark.sealed
    def test_c_cb_rf_1_below_threshold_stays_closed(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        cb.record_failure('e')  # threshold=3, count=1
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 1

    @pytest.mark.sealed
    def test_c_cb_rf_2_reaches_threshold_trips(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        for _ in range(3):
            cb.record_failure('e')
        assert cb.state == CircuitState.OPEN
        assert cb._failure_count == 0  # reset on trip

    @pytest.mark.sealed
    def test_c_cb_rf_3_half_open_failure_deepens_backoff(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        cb._state = CircuitState.HALF_OPEN
        cb._open_depth = 1
        cb.record_failure('probe failed')
        assert cb.state == CircuitState.OPEN
        assert cb._open_depth == 2  # incremented before _trip

    @pytest.mark.sealed
    def test_c_cb_rf_4_open_failure_does_not_re_trip(self, cb):
        """Failure while OPEN just records error but doesn't re-trip or reset depth."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        for _ in range(3):
            cb.record_failure('e')
        assert cb.state == CircuitState.OPEN
        depth_before = cb._open_depth
        cb.record_failure('while open')
        # Still OPEN, but failure count goes to 1 (not threshold yet)
        assert cb.state == CircuitState.OPEN
        assert cb._open_depth == depth_before  # unchanged by OPEN-state failure


class TestStateTransitions:

    @pytest.mark.sealed
    def test_c_cb_st_1_full_cycle(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        # CLOSED → OPEN
        for _ in range(3):
            cb.record_failure('e')
        assert cb.state == CircuitState.OPEN

        # OPEN → HALF_OPEN (simulated timeout)
        cb._last_open_at = time.monotonic() - 999
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

        # HALF_OPEN → CLOSED
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.sealed
    def test_c_cb_st_2_half_open_failure_deepens(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        for _ in range(3):
            cb.record_failure('e')
        depth1 = cb._open_depth
        cb._last_open_at = time.monotonic() - 999
        cb.allow_request()  # go HALF_OPEN
        cb.record_failure('probe failed')  # back to OPEN with deeper backoff
        assert cb.state == CircuitState.OPEN
        assert cb._open_depth > depth1

    @pytest.mark.sealed
    def test_c_cb_st_3_exponential_backoff(self, cb):
        """Depth 1 → 30s, depth 2 → 60s, depth 3 → 120s, max 300s."""
        from webui.backend.routes.mmm.mmm_circuit_breaker import RESET_TIMEOUT
        cb._open_depth = 1
        assert cb.reset_timeout == RESET_TIMEOUT * 1  # 30s
        cb._open_depth = 2
        assert cb.reset_timeout == RESET_TIMEOUT * 2  # 60s
        cb._open_depth = 3
        assert cb.reset_timeout == RESET_TIMEOUT * 4  # 120s
        cb._open_depth = 10
        assert cb.reset_timeout == 300.0  # capped


class TestPartialBeatAllowed:

    @pytest.mark.sealed
    def test_c_cb_pb_1_depth_1_allows_partial(self, cb):
        cb._open_depth = 1
        assert cb.partial_beat_allowed is True

    @pytest.mark.sealed
    def test_c_cb_pb_2_depth_2_allows_partial(self, cb):
        cb._open_depth = 2
        assert cb.partial_beat_allowed is True

    @pytest.mark.sealed
    def test_c_cb_pb_3_depth_3_skips_heartbeat(self, cb):
        cb._open_depth = 3
        assert cb.partial_beat_allowed is False


class TestReset:

    @pytest.mark.sealed
    def test_c_cb_r_1_manual_reset_closes(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        for _ in range(3):
            cb.record_failure('e')
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._open_depth == 0
        assert cb._failure_count == 0

    @pytest.mark.sealed
    def test_c_cb_r_2_returns_previous_state(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        for _ in range(3):
            cb.record_failure('e')
        result = cb.reset()
        assert result['previous_state'] == 'OPEN'
        assert result['new_state'] == 'CLOSED'


class TestShouldAlert:

    @pytest.mark.sealed
    def test_c_cb_sa_1_open_with_consecutive_opens(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState, CONSECUTIVE_OPEN_ALERT_THRESHOLD
        cb._state = CircuitState.OPEN
        cb._consecutive_opens = CONSECUTIVE_OPEN_ALERT_THRESHOLD
        assert cb.should_alert is True

    @pytest.mark.sealed
    def test_c_cb_sa_2_open_below_threshold(self, cb):
        from webui.backend.routes.mmm.mmm_circuit_breaker import CircuitState
        cb._state = CircuitState.OPEN
        cb._consecutive_opens = 1
        assert cb.should_alert is False

    @pytest.mark.sealed
    def test_c_cb_sa_3_closed_no_alert(self, cb):
        assert cb.should_alert is False
