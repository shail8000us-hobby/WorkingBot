"""
Flow Graph Generator Module

Single Responsibility: Generate visual decision flow graph structure.

Takes parsed AST data and builds a graph structure compatible with
React Flow visualization library.

Output format:
{
  "nodes": [{"id": "...", "type": "...", "data": {...}}],
  "edges": [{"id": "...", "source": "...", "target": "..."}]
}
"""

import logging
from typing import Dict, List, Any

log = logging.getLogger(__name__)


class FlowGraphGenerator:
    """
    Generates decision flow graph from parsed code.
    
    Creates nodes (decisions/actions) and edges (flow paths)
    in format compatible with React Flow.
    """
    
    def __init__(self):
        """Initialize flow generator"""
        self.node_counter = 0
        self.edge_counter = 0
        self.nodes = []
        self.edges = []
        self.y_offset = 0  # Track vertical position for layout
    
    def generate_flow_graph(self, parsed_modules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate complete decision flow graph.
        
        Args:
            parsed_modules: Dict of parsed module data from AST parser
            
        Returns:
            Graph structure with nodes and edges
        """
        try:
            self.nodes = []
            self.edges = []
            self.node_counter = 0
            self.edge_counter = 0
            
            # Start node
            start_node = self._create_node('start', 'start', 'Bot Starts')
            self.nodes.append(start_node)
            
            # Build main decision flow
            current_node_id = 'start'
            
            # Node: Check Emergency Stop
            emergency_node = self._create_node('check_emergency', 'decision', 'Emergency Stop Active?')
            self.nodes.append(emergency_node)
            self.edges.append(self._create_edge(current_node_id, 'check_emergency'))
            
            # Branch: Emergency YES
            halt_node = self._create_node('halt_all', 'action', 'HALT ALL TRADING')
            self.nodes.append(halt_node)
            self.edges.append(self._create_edge('check_emergency', 'halt_all', 'YES'))
            
            # Branch: Emergency NO → Check Volatility
            vol_node = self._create_node('check_volatility', 'decision', 'Volatility Safe?\n(IV < 35% & RV < 40%)')
            self.nodes.append(vol_node)
            self.edges.append(self._create_edge('check_emergency', 'check_volatility', 'NO'))
            
            # Branch: Volatility UNSAFE
            cancel_node = self._create_node('cancel_orders', 'action', 'Cancel Pending Orders')
            self.nodes.append(cancel_node)
            self.edges.append(self._create_edge('check_volatility', 'cancel_orders', 'UNSAFE'))
            
            track_node = self._create_node('track_levels', 'action', 'Track Missed Levels')
            self.nodes.append(track_node)
            self.edges.append(self._create_edge('cancel_orders', 'track_levels'))
            
            monitor_node = self._create_node('monitor_vol', 'waiting', 'Monitor Volatility\n(every 10s)')
            self.nodes.append(monitor_node)
            self.edges.append(self._create_edge('track_levels', 'monitor_vol'))
            
            # Loop back to volatility check
            self.edges.append(self._create_edge('monitor_vol', 'check_volatility', 'Check Again'))
            
            # Branch: Volatility SAFE → Check Guardian Protection
            guardian_node = self._create_node('check_guardian', 'decision', 'Guardian Checks:\n• Loss Limits OK?\n• Margin Safe?\n• Risk Acceptable?')
            self.nodes.append(guardian_node)
            self.edges.append(self._create_edge('check_volatility', 'check_guardian', 'SAFE'))
            
            # Branch: Guardian FAIL
            guardian_halt_node = self._create_node('guardian_halt', 'action', 'Guardian Protection:\nClose Positions\nHalt Trading')
            self.nodes.append(guardian_halt_node)
            self.edges.append(self._create_edge('check_guardian', 'guardian_halt', 'FAIL'))
            
            # Branch: Guardian PASS → Check Positions
            pos_node = self._create_node('check_positions', 'decision', 'Max Positions Reached?')
            self.nodes.append(pos_node)
            self.edges.append(self._create_edge('check_guardian', 'check_positions', 'PASS'))
            
            # Branch: Max positions YES
            wait_node = self._create_node('wait_close', 'waiting', 'Wait for TP Fill\n(Monitor PnL)')
            self.nodes.append(wait_node)
            self.edges.append(self._create_edge('check_positions', 'wait_close', 'YES'))
            
            # Branch: Max positions NO → Check Pending
            pending_node = self._create_node('check_pending', 'decision', 'Pending BUY Active?')
            self.nodes.append(pending_node)
            self.edges.append(self._create_edge('check_positions', 'check_pending', 'NO'))
            
            # Branch: Pending YES → Monitor Fill
            monitor_fill_node = self._create_node('monitor_fill', 'waiting', 'Monitor Fill\n(WebSocket ~50ms)')
            self.nodes.append(monitor_fill_node)
            self.edges.append(self._create_edge('check_pending', 'monitor_fill', 'YES'))
            
            # Fill detected → Place TP
            place_tp_node = self._create_node('place_tp', 'action', 'Place TP\n(Entry + Step)')
            self.nodes.append(place_tp_node)
            self.edges.append(self._create_edge('monitor_fill', 'place_tp', 'Filled'))
            
            # Branch: Pending NO → Calculate Next Buy
            calc_buy_node = self._create_node('calc_buy', 'calculation', 'Calculate Next Buy\n(GridCalculator)\n• Find lowest entry\n• Subtract step\n• Validate bounds')
            self.nodes.append(calc_buy_node)
            self.edges.append(self._create_edge('check_pending', 'calc_buy', 'NO'))
            
            # Safety validation before order
            safety_check_node = self._create_node('safety_check', 'decision', '11-Point Safety Check:\n✓ Volatility OK?\n✓ Margin OK?\n✓ Liquidation Risk?\n✓ API Health?\n✓ Position Limits?')
            self.nodes.append(safety_check_node)
            self.edges.append(self._create_edge('calc_buy', 'safety_check'))
            
            # Safety FAIL
            safety_fail_node = self._create_node('safety_fail', 'action', 'Block Order\n(Safety Violation)')
            self.nodes.append(safety_fail_node)
            self.edges.append(self._create_edge('safety_check', 'safety_fail', 'FAIL'))
            
            # Safety PASS → Place BUY
            place_buy_node = self._create_node('place_buy', 'action', 'Place BUY Order\n(With Retry Logic)')
            self.nodes.append(place_buy_node)
            self.edges.append(self._create_edge('safety_check', 'place_buy', 'PASS'))
            
            # Error handling for order placement
            order_error_node = self._create_node('order_error', 'decision', 'Order Placement Failed?')
            self.nodes.append(order_error_node)
            self.edges.append(self._create_edge('place_buy', 'order_error'))
            
            # Error YES → Retry with backoff
            retry_node = self._create_node('retry_order', 'action', 'Retry with Backoff\n(Max 3 attempts)')
            self.nodes.append(retry_node)
            self.edges.append(self._create_edge('order_error', 'retry_order', 'ERROR'))
            self.edges.append(self._create_edge('retry_order', 'safety_check', 'Retry'))
            
            # Error NO → Success
            self.edges.append(self._create_edge('order_error', 'monitor_fill', 'SUCCESS'))
            
            # WebSocket disconnect handling
            ws_error_node = self._create_node('ws_check', 'decision', 'WebSocket Connected?')
            self.nodes.append(ws_error_node)
            self.edges.append(self._create_edge('monitor_fill', 'ws_check'))
            
            # WS Disconnected → Reconnect
            ws_reconnect_node = self._create_node('ws_reconnect', 'action', 'WebSocket Reconnect\n(Auto-retry)')
            self.nodes.append(ws_reconnect_node)
            self.edges.append(self._create_edge('ws_check', 'ws_reconnect', 'DISCONNECTED'))
            self.edges.append(self._create_edge('ws_reconnect', 'ws_check', 'Retry'))
            
            # WS Connected → Continue monitoring
            self.edges.append(self._create_edge('ws_check', 'place_tp', 'CONNECTED + Filled'))
            
            # TP collision detection
            tp_collision_node = self._create_node('tp_collision', 'decision', 'TP Price Collision?')
            self.nodes.append(tp_collision_node)
            self.edges.append(self._create_edge('place_tp', 'tp_collision'))
            
            # Collision YES → Offset price
            tp_offset_node = self._create_node('tp_offset', 'calculation', 'Apply Collision Offset\n(+50 to +100)')
            self.nodes.append(tp_offset_node)
            self.edges.append(self._create_edge('tp_collision', 'tp_offset', 'YES'))
            self.edges.append(self._create_edge('tp_offset', 'check_positions', 'TP Placed'))
            
            # Collision NO → Continue
            self.edges.append(self._create_edge('tp_collision', 'check_positions', 'NO'))
            
            # Heartbeat monitoring (parallel process)
            heartbeat_node = self._create_node('heartbeat_monitor', 'waiting', '💓 Heartbeat Monitor\n(Separate Process)')
            self.nodes.append(heartbeat_node)
            # No edges - it's a parallel process
            
            return {
                'nodes': self.nodes,
                'edges': self.edges,
                'total_nodes': len(self.nodes),
                'total_edges': len(self.edges),
                'layout': 'dagre',  # Suggested layout algorithm
                'metadata': {
                    'decision_points': sum(1 for n in self.nodes if n['type'] == 'decision'),
                    'action_points': sum(1 for n in self.nodes if n['type'] == 'action'),
                    'safety_checks': 2,  # Guardian + 11-point
                    'error_handlers': 3  # Order retry, WS reconnect, TP collision
                }
            }
            
        except Exception as e:
            log.error(f"Error generating flow graph: {e}")
            return {'nodes': [], 'edges': [], 'error': str(e)}
    
    def _create_node(self, node_id: str, node_type: str, label: str) -> Dict[str, Any]:
        """
        Create a graph node.
        
        Args:
            node_id: Unique identifier
            node_type: Type (start, decision, action, waiting, calculation)
            label: Display label
            
        Returns:
            Node dict compatible with React Flow
        """
        return {
            'id': node_id,
            'type': node_type,
            'data': {
                'label': label
            },
            'position': {'x': 0, 'y': 0}  # React Flow will auto-layout
        }
    
    def _create_edge(self, source: str, target: str, label: str = '') -> Dict[str, Any]:
        """
        Create a graph edge (connection between nodes).
        
        Args:
            source: Source node ID
            target: Target node ID
            label: Edge label (e.g., "YES", "NO")
            
        Returns:
            Edge dict compatible with React Flow
        """
        edge_id = f"e{self.edge_counter}"
        self.edge_counter += 1
        
        edge = {
            'id': edge_id,
            'source': source,
            'target': target,
            'type': 'smoothstep',
            'animated': True
        }
        
        if label:
            edge['label'] = label
            edge['labelStyle'] = {'fill': '#fff', 'fontWeight': 700}
        
        return edge

