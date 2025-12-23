#!/usr/bin/env python3
"""
Bulletproof Provenance Detector
Determines if orders are Bot-placed or Manual with high accuracy.
"""

import re
import logging
import threading
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

log = logging.getLogger("provenance_detector")


@dataclass
class ProvenanceResult:
    """Result of provenance detection"""
    provenance: str  # 'bot', 'manual', 'unknown'
    confidence: float  # 0.0 to 1.0
    evidence: Dict[str, Any]  # Supporting evidence
    strategy: str  # Detected strategy
    reason: str  # Human-readable reason


class BulletproofProvenanceDetector:
    """
    Bulletproof provenance detector with multiple detection methods.
    
    Detection Methods (in order of priority):
    1. Client Order ID patterns (highest confidence)
    2. Order metadata analysis
    3. Timing analysis
    4. Heuristic matching
    """
    
    def __init__(self):
        # Bot patterns with confidence scores
        self.bot_patterns = {
            # BOT- prefix patterns (highest confidence)
            r'^BOT-([a-zA-Z0-9]+)-(\d+)-([a-zA-Z0-9]+)(?:-([a-zA-Z0-9]+))?$': {
                'confidence': 1.0,
                'strategy_extractor': lambda m: m.group(1),
                'type_extractor': lambda m: m.group(4) or 'unknown'
            },
            
            # Legacy GBOT patterns
            r'^GBOT_([A-Z]+)_(\d+)$': {
                'confidence': 0.95,
                'strategy_extractor': lambda m: 'grid',
                'type_extractor': lambda m: m.group(1)
            },
            
            # Current bot patterns (BUY/TP with timestamp)
            r'^BUY(\d{13})$': {
                'confidence': 0.9,
                'strategy_extractor': lambda m: 'grid',
                'type_extractor': lambda m: 'buy'
            },
            
            r'^TP(\d{13})$': {
                'confidence': 0.9,
                'strategy_extractor': lambda m: 'grid',
                'type_extractor': lambda m: 'tp'
            },
            
            # Alternative bot patterns
            r'^GRIDBOT_([A-Z]+)_(\d+)$': {
                'confidence': 0.85,
                'strategy_extractor': lambda m: 'grid',
                'type_extractor': lambda m: m.group(1)
            }
        }
        
        # Manual patterns (indicators of manual trading)
        self.manual_indicators = {
            'empty_client_id': 0.8,
            'user_prefix': 0.7,
            'manual_prefix': 0.9,
            'short_client_id': 0.6,
            'non_numeric_timestamp': 0.5
        }
    
    def detect_provenance(
        self,
        client_order_id: Optional[str],
        order_metadata: Optional[Dict[str, Any]] = None,
        order_timing: Optional[Dict[str, Any]] = None
    ) -> ProvenanceResult:
        """
        Detect order provenance with high accuracy.
        
        Args:
            client_order_id: Client order ID from exchange
            order_metadata: Additional order metadata
            order_timing: Order timing information
            
        Returns:
            ProvenanceResult with detection details
        """
        try:
            # Method 1: Client Order ID Pattern Analysis
            if client_order_id:
                result = self._analyze_client_id_pattern(client_order_id)
                if result.confidence >= 0.8:
                    return result
            
            # Method 2: Metadata Analysis
            if order_metadata:
                result = self._analyze_metadata(order_metadata)
                if result.confidence >= 0.7:
                    return result
            
            # Method 3: Timing Analysis
            if order_timing:
                result = self._analyze_timing(order_timing)
                if result.confidence >= 0.6:
                    return result
            
            # Method 4: Heuristic Analysis
            result = self._heuristic_analysis(client_order_id, order_metadata)
            
            return result
            
        except Exception as e:
            log.error(f"❌ Provenance detection error: {e}")
            return ProvenanceResult(
                provenance="unknown",
                confidence=0.0,
                evidence={"error": str(e)},
                strategy="unknown",
                reason="Detection error occurred"
            )
    
    def _analyze_client_id_pattern(self, client_order_id: str) -> ProvenanceResult:
        """Analyze client order ID patterns for bot indicators"""
        client_id = str(client_order_id).strip()
        
        # Test against bot patterns
        for pattern, config in self.bot_patterns.items():
            match = re.match(pattern, client_id)
            if match:
                strategy = config['strategy_extractor'](match)
                order_type = config['type_extractor'](match)
                
                return ProvenanceResult(
                    provenance="bot",
                    confidence=config['confidence'],
                    evidence={
                        "pattern": pattern,
                        "match_groups": match.groups(),
                        "strategy": strategy,
                        "order_type": order_type
                    },
                    strategy=strategy,
                    reason=f"Matched bot pattern: {pattern}"
                )
        
        # Test against manual indicators
        manual_score = 0.0
        evidence = {}
        
        if not client_id or client_id == "":
            manual_score += self.manual_indicators['empty_client_id']
            evidence['empty_client_id'] = True
        
        if any(client_id.startswith(prefix) for prefix in ['user_', 'manual_', 'human_', 'user']):
            manual_score += self.manual_indicators['user_prefix']
            evidence['user_prefix'] = True
        
        if len(client_id) < 8:
            manual_score += self.manual_indicators['short_client_id']
            evidence['short_client_id'] = True
        
        # Additional manual patterns
        if 'manual' in client_id.lower() or 'user' in client_id.lower():
            manual_score += 0.6
            evidence['manual_keywords'] = True
        
        if manual_score >= 0.6:  # Lower threshold for manual detection
            return ProvenanceResult(
                provenance="manual",
                confidence=min(manual_score, 1.0),
                evidence=evidence,
                strategy="unknown",
                reason="Matched manual indicators"
            )
        
        # Default to unknown if no clear pattern
        return ProvenanceResult(
            provenance="unknown",
            confidence=0.3,
            evidence={"client_id": client_id},
            strategy="unknown",
            reason="No clear pattern detected"
        )
    
    def _analyze_metadata(self, metadata: Dict[str, Any]) -> ProvenanceResult:
        """Analyze order metadata for provenance indicators"""
        evidence = {}
        bot_score = 0.0
        manual_score = 0.0
        
        # Bot indicators in metadata
        if metadata.get('strategy') in ['grid', 'scalp', 'hedge']:
            bot_score += 0.8
            evidence['strategy_metadata'] = metadata['strategy']
        
        if metadata.get('session_id', '').startswith('gridbot_'):
            bot_score += 0.9
            evidence['bot_session'] = True
        
        if metadata.get('origin') in ['normal', 'recovery', 'smart_gap_fill']:
            bot_score += 0.7
            evidence['bot_origin'] = metadata['origin']
        
        # Manual indicators in metadata
        if metadata.get('source') == 'manual':
            manual_score += 0.9
            evidence['manual_source'] = True
        
        if metadata.get('user_placed', False):
            manual_score += 0.8
            evidence['user_placed'] = True
        
        # Determine result
        if bot_score > manual_score and bot_score >= 0.6:
            return ProvenanceResult(
                provenance="bot",
                confidence=min(bot_score, 1.0),
                evidence=evidence,
                strategy=metadata.get('strategy', 'unknown'),
                reason="Metadata indicates bot origin"
            )
        elif manual_score > bot_score and manual_score >= 0.6:
            return ProvenanceResult(
                provenance="manual",
                confidence=min(manual_score, 1.0),
                evidence=evidence,
                strategy="unknown",
                reason="Metadata indicates manual origin"
            )
        
        return ProvenanceResult(
            provenance="unknown",
            confidence=0.3,
            evidence=evidence,
            strategy="unknown",
            reason="Inconclusive metadata"
        )
    
    def _analyze_timing(self, timing: Dict[str, Any]) -> ProvenanceResult:
        """Analyze order timing for bot patterns"""
        evidence = {}
        bot_score = 0.0
        
        # Bot timing patterns
        if timing.get('placed_during_bot_session', False):
            bot_score += 0.7
            evidence['bot_session_timing'] = True
        
        if timing.get('rapid_succession', False):
            bot_score += 0.6
            evidence['rapid_succession'] = True
        
        if timing.get('grid_pattern_timing', False):
            bot_score += 0.8
            evidence['grid_timing'] = True
        
        if bot_score >= 0.6:
            return ProvenanceResult(
                provenance="bot",
                confidence=min(bot_score, 1.0),
                evidence=evidence,
                strategy="grid",
                reason="Timing patterns suggest bot origin"
            )
        
        return ProvenanceResult(
            provenance="unknown",
            confidence=0.3,
            evidence=evidence,
            strategy="unknown",
            reason="Inconclusive timing analysis"
        )
    
    def _heuristic_analysis(
        self,
        client_order_id: Optional[str],
        metadata: Optional[Dict[str, Any]]
    ) -> ProvenanceResult:
        """Heuristic analysis when other methods are inconclusive"""
        evidence = {}
        bot_score = 0.0
        manual_score = 0.0
        
        # Heuristic bot indicators
        if client_order_id and len(client_order_id) > 15:
            # Long client IDs often indicate bot systems
            bot_score += 0.4
            evidence['long_client_id'] = True
        
        if metadata and metadata.get('automated', False):
            bot_score += 0.8
            evidence['automated_flag'] = True
        
        # Heuristic manual indicators
        if not client_order_id or client_order_id == "":
            manual_score += 0.6
            evidence['no_client_id'] = True
        
        if client_order_id and len(client_order_id) < 5:
            manual_score += 0.5
            evidence['very_short_client_id'] = True
        
        # Determine result
        if bot_score > manual_score:
            return ProvenanceResult(
                provenance="bot",
                confidence=min(bot_score, 0.7),  # Cap heuristic confidence
                evidence=evidence,
                strategy="unknown",
                reason="Heuristic analysis suggests bot"
            )
        elif manual_score > bot_score:
            return ProvenanceResult(
                provenance="manual",
                confidence=min(manual_score, 0.7),  # Cap heuristic confidence
                evidence=evidence,
                strategy="unknown",
                reason="Heuristic analysis suggests manual"
            )
        
        return ProvenanceResult(
            provenance="unknown",
            confidence=0.2,
            evidence=evidence,
            strategy="unknown",
            reason="Heuristic analysis inconclusive"
        )
    
    def get_provenance_summary(self, orders: list) -> Dict[str, Any]:
        """Get summary of provenance distribution for a list of orders"""
        summary = {
            'total': len(orders),
            'bot': 0,
            'manual': 0,
            'unknown': 0,
            'strategies': {},
            'confidence_distribution': {
                'high': 0,  # >= 0.8
                'medium': 0,  # 0.5-0.8
                'low': 0  # < 0.5
            }
        }
        
        for order in orders:
            client_id = order.get('client_order_id', '')
            metadata = order.get('metadata', {})
            
            result = self.detect_provenance(client_id, metadata)
            
            # Count by provenance
            summary[result.provenance] += 1
            
            # Count strategies
            strategy = result.strategy
            if strategy not in summary['strategies']:
                summary['strategies'][strategy] = 0
            summary['strategies'][strategy] += 1
            
            # Count confidence levels
            if result.confidence >= 0.8:
                summary['confidence_distribution']['high'] += 1
            elif result.confidence >= 0.5:
                summary['confidence_distribution']['medium'] += 1
            else:
                summary['confidence_distribution']['low'] += 1
        
        return summary


# Global instance
_provenance_detector = None


def get_provenance_detector() -> BulletproofProvenanceDetector:
    """Get global provenance detector instance"""
    global _provenance_detector
    if _provenance_detector is None:
        _provenance_detector = BulletproofProvenanceDetector()
    return _provenance_detector


def detect_order_provenance(
    client_order_id: Optional[str],
    order_metadata: Optional[Dict[str, Any]] = None,
    order_timing: Optional[Dict[str, Any]] = None
) -> ProvenanceResult:
    """Convenience function to detect order provenance"""
    detector = get_provenance_detector()
    return detector.detect_provenance(client_order_id, order_metadata, order_timing)


if __name__ == "__main__":
    # Test the provenance detector
    detector = get_provenance_detector()
    
    # Test cases
    test_cases = [
        ("BOT-grid-1729012345-a7f3-buy", "bot"),
        ("GBOT_BUY_123456789", "bot"),
        ("BUY1761036206087", "bot"),
        ("TP1761036206087", "bot"),
        ("user_manual_123", "manual"),
        ("", "manual"),
        ("random_id", "unknown")
    ]
    
    print("🧪 Testing Provenance Detector:")
    for client_id, expected in test_cases:
        result = detector.detect_provenance(client_id)
        status = "✅" if result.provenance == expected else "❌"
        print(f"{status} {client_id} -> {result.provenance} (expected: {expected}, confidence: {result.confidence:.2f})")
    
    print("\n✅ Provenance detector test completed")
