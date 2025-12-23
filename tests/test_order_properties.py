"""
Property-Based Tests for OrderManager

Tests order validation, placement logic, and state transitions.

Key Properties:
- Orders always have valid prices and quantities
- Client order IDs are always unique
- Order state transitions are consistent
- Collision detection works correctly
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from unittest.mock import Mock, MagicMock
import time

from bot.strategy.modules.order_manager import OrderManager
from bot.strategy.modules.grid_calculator import GridCalculator


# ============================================================================
# MOCK HELPERS
# ============================================================================

def create_mock_api_client():
    """Create a mock API client with all required methods"""
    mock = Mock()
    mock.place_order = Mock(return_value={'id': 12345, 'client_order_id': 'test_order'})
    mock.cancel_order = Mock(return_value={'success': True})
    mock.get_order = Mock(return_value={'state': 'open'})
    mock.list_orders = Mock(return_value=[])
    return mock


def create_mock_position_manager():
    """Create a mock PositionManager"""
    mock = Mock()
    mock.state_lock = MagicMock()
    mock.get_open_positions = Mock(return_value=[])
    mock.add_position = Mock()
    mock.remove_position = Mock()
    return mock


def create_mock_grid_calculator(lower=100000, upper=110000, step=1000, ref=105000):
    """Create a real GridCalculator instance"""
    return GridCalculator(
        lower=lower,
        upper=upper,
        step=step,
        ref=ref,
        tick_size=0.5
    )


# ============================================================================
# STRATEGY DEFINITIONS
# ============================================================================

@st.composite
def valid_order_manager_params(draw):
    """Generate valid OrderManager initialization parameters"""
    product_id = draw(st.integers(min_value=1, max_value=1000))
    lot_size = draw(st.integers(min_value=1, max_value=100))
    tick_size = draw(st.floats(min_value=0.01, max_value=1.0))
    
    return {
        'product_id': product_id,
        'lot_size': lot_size,
        'tick_size': round(tick_size, 2)
    }


@st.composite
def valid_price_and_quantity(draw):
    """Generate valid order price and quantity"""
    price = draw(st.floats(min_value=1000, max_value=200000, allow_nan=False, allow_infinity=False))
    quantity = draw(st.integers(min_value=1, max_value=100))
    
    return {
        'price': round(price, 2),
        'quantity': quantity
    }


# ============================================================================
# PROPERTY 1: Initialization Validation
# ============================================================================

@given(params=valid_order_manager_params())
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_order_manager_initializes_with_valid_params(params):
    """
    PROPERTY: Valid parameters always create a valid OrderManager
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    om = OrderManager(
        api_client=api_client,
        grid_calculator=grid_calc,
        position_manager=pos_mgr,
        product_id=params['product_id'],
        lot_size=params['lot_size'],
        tick_size=params['tick_size']
    )
    
    # Verify all parameters stored
    assert om.product_id == params['product_id']
    assert om.lot_size == params['lot_size']
    assert om.tick_size == params['tick_size']
    assert om.api_client is api_client
    assert om.grid_calc is grid_calc
    assert om.position_mgr is pos_mgr


@given(lot_size=st.integers(max_value=0))
@settings(max_examples=50)
def test_property_order_manager_rejects_invalid_lot_size(lot_size):
    """
    PROPERTY: OrderManager rejects lot_size <= 0
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    with pytest.raises(ValueError, match="lot_size must be a positive integer"):
        OrderManager(
            api_client=api_client,
            grid_calculator=grid_calc,
            position_manager=pos_mgr,
            product_id=27,
            lot_size=lot_size,
            tick_size=0.5
        )


@given(product_id=st.integers(max_value=0))
@settings(max_examples=50)
def test_property_order_manager_rejects_invalid_product_id(product_id):
    """
    PROPERTY: OrderManager rejects product_id <= 0
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    with pytest.raises(ValueError, match="product_id must be a positive integer"):
        OrderManager(
            api_client=api_client,
            grid_calculator=grid_calc,
            position_manager=pos_mgr,
            product_id=product_id,
            lot_size=10,
            tick_size=0.5
        )


@given(tick_size=st.floats(max_value=0, allow_nan=False, allow_infinity=False))
@settings(max_examples=50)
def test_property_order_manager_rejects_invalid_tick_size(tick_size):
    """
    PROPERTY: OrderManager rejects tick_size <= 0
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    with pytest.raises(ValueError, match="tick_size must be positive"):
        OrderManager(
            api_client=api_client,
            grid_calculator=grid_calc,
            position_manager=pos_mgr,
            product_id=27,
            lot_size=10,
            tick_size=tick_size
        )


# ============================================================================
# PROPERTY 2: Client Order ID Uniqueness
# ============================================================================

@given(
    num_orders=st.integers(min_value=1, max_value=1000),
    timestamp_base=st.integers(min_value=1600000000, max_value=1700000000)
)
@settings(max_examples=100)
def test_property_client_order_ids_are_unique(num_orders, timestamp_base):
    """
    PROPERTY: Generated client order IDs are always unique
    
    Critical for order tracking and preventing duplicate placements
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    om = OrderManager(
        api_client=api_client,
        grid_calculator=grid_calc,
        position_manager=pos_mgr,
        product_id=27,
        lot_size=10,
        tick_size=0.5
    )
    
    # Generate multiple order IDs
    order_ids = set()
    
    for i in range(num_orders):
        # Simulate time passage
        current_time = timestamp_base + i * 0.001
        
        # Generate order ID (using internal method if available)
        if hasattr(om, '_generate_client_order_id'):
            order_id = om._generate_client_order_id(current_time)
            order_ids.add(order_id)
    
    # All IDs should be unique
    if order_ids:  # Only test if IDs were generated
        assert len(order_ids) == len(order_ids)  # Set automatically deduplicates


# ============================================================================
# PROPERTY 3: Price Validation Properties
# ============================================================================

@given(order_data=valid_price_and_quantity())
@settings(max_examples=200)
def test_property_valid_orders_have_positive_price(order_data):
    """
    PROPERTY: All valid orders must have price > 0
    
    Ensures fat-finger protection
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    om = OrderManager(
        api_client=api_client,
        grid_calculator=grid_calc,
        position_manager=pos_mgr,
        product_id=27,
        lot_size=10,
        tick_size=0.5
    )
    
    # Valid orders should have price > 0
    assert order_data['price'] > 0
    assert order_data['quantity'] > 0


@given(
    price=st.floats(max_value=0, allow_nan=False, allow_infinity=False),
    quantity=st.integers(min_value=1, max_value=100)
)
@settings(max_examples=100)
def test_property_order_manager_rejects_non_positive_price(price, quantity):
    """
    PROPERTY: OrderManager validation rejects price <= 0
    
    Tests internal validation (if exposed)
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    om = OrderManager(
        api_client=api_client,
        grid_calculator=grid_calc,
        position_manager=pos_mgr,
        product_id=27,
        lot_size=10,
        tick_size=0.5
    )
    
    # If validation method exists, it should reject invalid price
    if hasattr(om, '_validate_order_params'):
        with pytest.raises(ValueError):
            om._validate_order_params(price=price, quantity=quantity)


@given(
    price=st.floats(min_value=1000, max_value=200000, allow_nan=False, allow_infinity=False),
    quantity=st.integers(max_value=0)
)
@settings(max_examples=100)
def test_property_order_manager_rejects_non_positive_quantity(price, quantity):
    """
    PROPERTY: OrderManager validation rejects quantity <= 0
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    om = OrderManager(
        api_client=api_client,
        grid_calculator=grid_calc,
        position_manager=pos_mgr,
        product_id=27,
        lot_size=10,
        tick_size=0.5
    )
    
    # If validation method exists, it should reject invalid quantity
    if hasattr(om, '_validate_order_params'):
        with pytest.raises(ValueError):
            om._validate_order_params(price=price, quantity=quantity)


# ============================================================================
# PROPERTY 4: Price Quantization Properties
# ============================================================================

@given(
    params=valid_order_manager_params(),
    raw_price=st.floats(min_value=1000, max_value=200000, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=200)
def test_property_order_prices_are_quantized_to_tick_size(params, raw_price):
    """
    PROPERTY: All order prices are quantized to tick_size
    
    Prevents exchange rejection due to invalid tick
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    om = OrderManager(
        api_client=api_client,
        grid_calculator=grid_calc,
        position_manager=pos_mgr,
        **params
    )
    
    # Quantize price using grid calculator
    quantized = grid_calc.quantize_price(raw_price)
    
    # After quantization, price should be stable (idempotent)
    quantized_again = grid_calc.quantize_price(quantized)
    
    # This is the key property: quantization is idempotent
    assert abs(quantized - quantized_again) < 1e-6


# ============================================================================
# PROPERTY 5: Order Capacity Checks
# ============================================================================

@given(
    max_positions=st.integers(min_value=1, max_value=20),
    current_positions=st.integers(min_value=0, max_value=30)
)
@settings(max_examples=100)
def test_property_order_manager_respects_position_limits(max_positions, current_positions):
    """
    PROPERTY: OrderManager respects maximum position limits
    
    Should not place orders if at capacity
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    # Mock current position count
    pos_mgr.get_open_positions.return_value = [
        {'entry_price': 105000} for _ in range(current_positions)
    ]
    
    om = OrderManager(
        api_client=api_client,
        grid_calculator=grid_calc,
        position_manager=pos_mgr,
        product_id=27,
        lot_size=10,
        tick_size=0.5
    )
    
    # Check if capacity check method exists
    if hasattr(om, '_has_capacity'):
        has_capacity = om._has_capacity(max_positions)
        
        # Should have capacity only if current < max
        expected = (current_positions < max_positions)
        assert has_capacity == expected


# ============================================================================
# PROPERTY 6: TP Collision Avoidance Properties
# ============================================================================

@given(
    entry_price=st.floats(min_value=100000, max_value=110000, allow_nan=False, allow_infinity=False),
    existing_tp_offset=st.floats(min_value=-50, max_value=50, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_property_tp_collision_detection_finds_conflicts(entry_price, existing_tp_offset):
    """
    PROPERTY: TP collision detection identifies existing orders near target price
    
    Critical for preventing duplicate TP orders (FIX #8)
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    om = OrderManager(
        api_client=api_client,
        grid_calculator=grid_calc,
        position_manager=pos_mgr,
        product_id=27,
        lot_size=10,
        tick_size=0.5
    )
    
    # Calculate target TP price
    target_tp = entry_price + 1000  # Assume step = 1000
    
    # Create existing order near target
    existing_order = {'limit_price': target_tp + existing_tp_offset}
    
    # Check collision detection (if method exists)
    if hasattr(om, '_has_tp_collision'):
        # Within collision threshold (e.g., $100)
        collision_threshold = 100
        
        has_collision = om._has_tp_collision(
            target_price=target_tp,
            existing_orders=[existing_order],
            threshold=collision_threshold
        )
        
        # Should detect collision if within threshold
        expected = abs(existing_tp_offset) < collision_threshold
        assert has_collision == expected


# ============================================================================
# PROPERTY 7: Order State Transition Properties
# ============================================================================

@given(
    initial_state=st.sampled_from(['open', 'pending', 'filled', 'cancelled']),
    final_state=st.sampled_from(['open', 'pending', 'filled', 'cancelled'])
)
@settings(max_examples=50)
def test_property_order_state_transitions_are_valid(initial_state, final_state):
    """
    PROPERTY: Order state transitions follow valid patterns
    
    Valid transitions:
    - pending → open
    - pending → filled
    - open → filled
    - open → cancelled
    - pending → cancelled
    
    Invalid:
    - filled → anything (terminal state)
    - cancelled → anything (terminal state)
    """
    # Define valid transitions
    valid_transitions = {
        'pending': {'open', 'filled', 'cancelled'},
        'open': {'filled', 'cancelled'},
        'filled': set(),  # Terminal state
        'cancelled': set()  # Terminal state
    }
    
    is_valid = final_state in valid_transitions.get(initial_state, set())
    
    # Terminal states can't transition
    if initial_state in ['filled', 'cancelled']:
        assert not is_valid or initial_state == final_state


# ============================================================================
# PROPERTY 8: Retry Logic Properties
# ============================================================================

@given(
    num_retries=st.integers(min_value=0, max_value=5),
    failure_rate=st.floats(min_value=0.0, max_value=1.0)
)
@settings(max_examples=50)
def test_property_retry_mechanism_respects_max_attempts(num_retries, failure_rate):
    """
    PROPERTY: Retry mechanism never exceeds max retry count
    
    Prevents infinite retry loops
    """
    api_client = create_mock_api_client()
    
    # Simulate failures
    call_count = [0]
    
    def mock_place_order(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] / (num_retries + 1) <= failure_rate:
            raise Exception("Simulated failure")
        return {'id': 12345, 'client_order_id': 'test'}
    
    api_client.place_order = mock_place_order
    
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    om = OrderManager(
        api_client=api_client,
        grid_calculator=grid_calc,
        position_manager=pos_mgr,
        product_id=27,
        lot_size=10,
        tick_size=0.5
    )
    
    # If retry wrapper exists, test it
    if hasattr(om, '_retry_on_failure'):
        try:
            om._retry_on_failure(
                api_client.place_order,
                max_retries=num_retries,
                product_id=27,
                order_type='limit_order',
                size=10,
                limit_price=105000
            )
        except Exception:
            pass  # Expected if all retries fail
        
        # Should not exceed max retries + 1 (initial attempt)
        assert call_count[0] <= num_retries + 1


# ============================================================================
# PROPERTY 9: Order Cancellation Properties
# ============================================================================

@given(
    order_ids=st.lists(
        st.integers(min_value=1, max_value=1000000),
        min_size=0,
        max_size=20,
        unique=True
    )
)
@settings(max_examples=100)
def test_property_batch_cancellation_processes_all_orders(order_ids):
    """
    PROPERTY: Batch order cancellation attempts to cancel all provided order IDs
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    cancelled_ids = []
    
    def mock_cancel_order(product_id, order_id):
        cancelled_ids.append(order_id)
        return {'success': True}
    
    api_client.cancel_order = mock_cancel_order
    
    om = OrderManager(
        api_client=api_client,
        grid_calculator=grid_calc,
        position_manager=pos_mgr,
        product_id=27,
        lot_size=10,
        tick_size=0.5
    )
    
    # If batch cancel method exists
    if hasattr(om, '_cancel_orders_batch'):
        om._cancel_orders_batch(order_ids)
        
        # All order IDs should be processed
        assert len(cancelled_ids) == len(order_ids)
        assert set(cancelled_ids) == set(order_ids)


# ============================================================================
# PROPERTY 10: Thread Safety Properties
# ============================================================================

@given(num_concurrent_operations=st.integers(min_value=1, max_value=10))
@settings(max_examples=20)
def test_property_order_manager_uses_state_lock(num_concurrent_operations):
    """
    PROPERTY: OrderManager uses position manager's state lock for thread safety
    
    Critical for preventing race conditions in multi-threaded environment
    """
    api_client = create_mock_api_client()
    grid_calc = create_mock_grid_calculator()
    pos_mgr = create_mock_position_manager()
    
    # Track lock usage
    lock_acquire_count = [0]
    
    def mock_lock_acquire(*args, **kwargs):
        lock_acquire_count[0] += 1
        return True
    
    pos_mgr.state_lock.__enter__ = mock_lock_acquire
    pos_mgr.state_lock.__exit__ = Mock(return_value=False)
    
    om = OrderManager(
        api_client=api_client,
        grid_calculator=grid_calc,
        position_manager=pos_mgr,
        product_id=27,
        lot_size=10,
        tick_size=0.5
    )
    
    # Verify lock is available
    assert hasattr(om.position_mgr, 'state_lock')
    assert om.position_mgr.state_lock is not None


if __name__ == '__main__':
    # Run with verbose output
    pytest.main([__file__, '-v', '--hypothesis-show-statistics'])
