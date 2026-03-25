# VISUALS CONTEXT

This file is a consolidated combination of multiple documentation and planning files to preserve context for the AI.

## SOURCE FILE: PAYOFF_GRAPH_ENHANCEMENT_PLAN.md

# Payoff Graph Enhancement Plan
## Industry-Standard Options Trading Visualization

**Created:** January 23, 2026  
**Status:** Planning Phase  
**Goal:** Transform the current payoff graph system into an industry-standard, robust visualization comparable to professional trading platforms (TradingView, Sensibull, OptionsPlay, ThinkOrSwim)

---

## Executive Summary

After analyzing the current implementation across 3 main components:
1. **OptionsPayoffDiagram.js** - Main options payoff with Black-Scholes
2. **PayoffDiagram.js** - Strategy-level payoff (simplified)
3. **StrategyBuilderPanel.js** - Real-time strategy builder preview
4. **Backend PayoffCalculator** - Python calculation engine

**Critical Issues Identified:**
- ❌ Inconsistent calculation methodologies across components
- ❌ Missing multiplier corrections in some calculations
- ❌ No support for American-style early exercise
- ❌ Limited Greeks visualization and sensitivity analysis
- ❌ No probability analysis (probability of profit, expected value)
- ❌ Missing risk metrics (max loss at different confidence levels)
- ❌ No time-decay visualization across multiple dates
- ❌ Incomplete support for complex multi-leg strategies
- ❌ No scenario analysis (what-if simulations)
- ❌ Limited UI/UX for professional traders

---

## ✅ Completed Work (January 26, 2026)

### Day 1 & Day 2: Basic PoP Integration into OptionsPanel

**Status:** COMPLETED  
**Commit:** 1df458e3b (feat: Integrate Day 1 & Day 2 PoP calculation into OptionsPanel)  
**Branch:** BTEH

#### What Was Built:
Simple integration of Probability of Profit (PoP) calculation into the main Options Panel using existing utilities. This provides traders with immediate visibility of their position probability of success.

#### Files Created (Pre-existing utilities):
1. **webui/frontend/src/utils/constants.js**
   - Contains `RISK_FREE_RATE = 0` for Delta Exchange (0% risk-free rate for crypto)
   - Contract multipliers for BTC/ETH (0.001)

2. **webui/frontend/src/utils/greeksFromAPI.js**
   - Greeks data caching with 5-second cache duration
   - Fetches and caches IV, delta, gamma, theta, vega from backend

3. **webui/frontend/src/utils/probabilityCalc.js**
   - `calculatePoP()` - Black-Scholes-based probability calculation
   - Uses spot price, strike, IV, time to expiry, and risk-free rate
   - Returns probability percentage (0-100%)

#### Files Modified:
1. **webui/frontend/src/components/options/OptionsPanel.js**
   - Added PoP calculation useEffect that runs whenever positions change
   - Parses expiry from DDMMYYYY format to calculate time to expiry
   - Filters out expired options from PoP calculations
   - Added PoP column to table with color-coded chips:
     - Green chip for PoP > 50%
     - Orange chip for PoP ≤ 50%
   - Fixed localStorage column visibility to ensure new columns appear for existing users
   - Column defaults now merge with saved preferences: `{ ...defaults, ...parsed }`

#### Technical Implementation Details:
- **PoP Calculation Logic:**
  ```javascript
  const calculatePoP = (spot, strike, iv, timeToExpiry, optionType) => {
    // Black-Scholes probability calculation
    // Returns probability that option expires in-the-money
  }
  ```

- **Time to Expiry Parsing:**
  - Converts DDMMYYYY format to JavaScript Date
  - Calculates days remaining and converts to years
  - Filters positions with < 0.001 years remaining (expired)

- **localStorage Fix:**
  - Previous bug: New columns hidden for users with saved preferences
  - Solution: Merge defaults with saved state to ensure new columns always appear
  - Pattern: `const defaults = { ...allColumns }; return parsed ? { ...defaults, ...parsed } : defaults;`

#### User Experience:
- PoP column appears in main Options Panel table
- Real-time probability display for all active positions
- Color-coded chips for quick visual assessment
- Automatic filtering of expired positions
- Works seamlessly with existing column visibility controls

#### Testing & Deployment:
- ✅ Frontend built successfully (npm run build)
- ✅ Backend restarted and healthy
- ✅ PoP column visibility fixed for existing users
- ✅ Git commits pushed to origin/BTEH

#### Limitations & Future Work:
- Uses simplified Black-Scholes (European options)
- No support for American-style early exercise
- No portfolio-level PoP aggregation
- No probability density visualization (planned for Phase 3)
- No Monte Carlo simulation (planned for Phase 2)

**Next Steps:** This basic integration provides immediate value to traders and establishes the foundation for more advanced probability analysis features outlined in Phase 2 of this plan.

---

## Part 1: Mathematical Foundation & Calculation Engine

### 1.1 Core Pricing Models (Backend Enhancement)

#### A. Black-Scholes-Merton Model (Current - Needs Enhancement)
**Current State:**
- ✅ Basic implementation exists in OptionsPayoffDiagram.js
- ❌ Missing in backend Python calculator
- ❌ No dividend yield support
- ❌ Limited to European options

**Enhancements Required:**
```python
# webui/backend/options_strategy/pricing_engine.py (NEW FILE)

class OptionPricingEngine:
    """
    Industry-standard option pricing with multiple models
    """
    
    # 1. Enhanced Black-Scholes with dividends
    @staticmethod
    def black_scholes_merton(
        spot: float,
        strike: float,
        time_to_expiry: float,  # in years
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float,
        option_type: str
    ) -> dict:
        """
        Returns: {
            'price': float,
            'delta': float,
            'gamma': float,
            'theta': float,
            'vega': float,
            'rho': float
        }
        """
        pass
    
    # 2. Binomial Tree for American options
    @staticmethod
    def binomial_tree(
        spot: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float,
        option_type: str,
        steps: int = 100,
        american: bool = True
    ) -> dict:
        """
        Cox-Ross-Rubinstein binomial tree
        Handles early exercise for American options
        """
        pass
    
    # 3. Monte Carlo simulation for complex payoffs
    @staticmethod
    def monte_carlo(
        spot: float,
        strikes: list,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        num_simulations: int = 10000
    ) -> dict:
        """
        For exotic options and complex strategies
        Returns probability distributions
        """
        pass
```

#### B. Implied Volatility Engine
**Current State:**
- ✅ Newton-Raphson + Bisection implemented in frontend
- ❌ Not available in backend
- ❌ No volatility smile/skew handling

**Enhancements Required:**
```python
class VolatilityEngine:
    """
    Advanced IV calculation and surface modeling
    """
    
    @staticmethod
    def calculate_implied_volatility(
        market_price: float,
        spot: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        dividend_yield: float,
        option_type: str,
        method: str = 'newton-raphson'  # or 'brent', 'bisection'
    ) -> float:
        """
        Enhanced IV with multiple solving methods
        """
        pass
    
    @staticmethod
    def build_volatility_surface(
        market_data: list,  # List of options with prices
        spot: float
    ) -> dict:
        """
        Build volatility smile/skew surface
        Returns: {
            'strikes': [],
            'expiries': [],
            'iv_matrix': [[]]  # 2D grid
        }
        """
        pass
    
    @staticmethod
    def interpolate_iv(
        strike: float,
        expiry: float,
        surface: dict
    ) -> float:
        """
        Get IV for any strike/expiry using surface interpolation
        """
        pass
```

### 1.2 Greeks Calculation (Complete Suite)

**Current State:**
- ⚠️ Delta, Gamma, Theta, Vega calculated in OptionsPayoffDiagram (frontend only)
- ❌ No portfolio-level Greeks
- ❌ Missing second-order Greeks

**Enhancement:**
```python
class GreeksCalculator:
    """
    Complete Greeks calculation for risk management
    """
    
    # First-order Greeks (current)
    @staticmethod
    def calculate_delta(S, K, T, r, sigma, q, option_type) -> float:
        """Rate of change: dV/dS"""
        pass
    
    @staticmethod
    def calculate_vega(S, K, T, r, sigma, q) -> float:
        """Sensitivity to volatility: dV/dσ"""
        pass
    
    @staticmethod
    def calculate_theta(S, K, T, r, sigma, q, option_type) -> float:
        """Time decay: dV/dt (per day)"""
        pass
    
    @staticmethod
    def calculate_rho(S, K, T, r, sigma, q, option_type) -> float:
        """Interest rate sensitivity: dV/dr"""
        pass
    
    # Second-order Greeks (NEW)
    @staticmethod
    def calculate_gamma(S, K, T, r, sigma, q) -> float:
        """Delta sensitivity: d²V/dS²"""
        pass
    
    @staticmethod
    def calculate_vanna(S, K, T, r, sigma, q) -> float:
        """Delta sensitivity to volatility: d²V/dSdσ"""
        pass
    
    @staticmethod
    def calculate_charm(S, K, T, r, sigma, q, option_type) -> float:
        """Delta decay: d²V/dSdt"""
        pass
    
    @staticmethod
    def calculate_vomma(S, K, T, r, sigma, q) -> float:
        """Vega sensitivity: d²V/dσ²"""
        pass
    
    # Portfolio Greeks
    @staticmethod
    def calculate_portfolio_greeks(positions: list) -> dict:
        """
        Aggregate Greeks across all positions
        Returns: {
            'delta': float,
            'gamma': float,
            'theta_per_day': float,
            'vega': float,
            'rho': float,
            'dollar_delta': float,
            'dollar_gamma': float
        }
        """
        pass
```

### 1.3 Payoff Calculation Engine (Enhanced)

**Current Issues:**
- Different formulas in different files
- Inconsistent multiplier handling (0.001 vs 1)
- No transaction cost consideration
- Missing margin requirements

**Enhanced Unified Calculator:**
```python
class PayoffCalculator:
    """
    Unified payoff calculation with all edge cases handled
    """
    
    @staticmethod
    def calculate_payoff_at_price(
        positions: list,
        underlying_price: float,
        time_to_expiry: float = 0,  # 0 = at expiry
        volatility_adjustment: float = 0,  # For vol scenarios
        risk_free_rate: float = 0.05,
        dividend_yield: float = 0
    ) -> dict:
        """
        Calculate P&L at specific underlying price and time
        
        Returns: {
            'total_pnl': float,
            'component_pnls': [
                {
                    'leg_id': str,
                    'pnl': float,
                    'greeks': {...}
                }
            ],
            'greeks': {...},  # Portfolio Greeks
            'margin_required': float,
            'buying_power_effect': float
        }
        """
        pass
    
    @staticmethod
    def calculate_payoff_curve(
        positions: list,
        spot_price: float,
        price_range_pct: float = 25,
        num_points: int = 200,
        time_to_expiry: float = 0
    ) -> dict:
        """
        Generate full payoff curve data
        
        Returns: {
            'prices': [float],
            'payoffs': [float],
            'deltas': [float],
            'gammas': [float],
            'probability_density': [float],  # NEW
            'breakeven_prices': [float],
            'max_profit': float,
            'max_loss': float,
            'profit_range': (float, float),
            'loss_range': (float, float)
        }
        """
        pass
    
    @staticmethod
    def calculate_payoff_surface(
        positions: list,
        spot_price: float,
        price_range_pct: float = 25,
        max_days_to_expiry: float = None,
        price_points: int = 100,
        time_points: int = 20
    ) -> dict:
        """
        3D payoff surface: P&L as function of price AND time
        
        Returns: {
            'prices': [float],  # X-axis
            'times': [float],   # Y-axis (days to expiry)
            'payoff_matrix': [[float]],  # Z-axis (P&L)
            'risk_metrics': {...}
        }
        """
        pass
```

---

## Part 2: Risk Metrics & Probability Analysis

### 2.1 Probability of Profit (PoP)

**NEW FEATURE - Not Currently Implemented**

```python
class ProbabilityAnalyzer:
    """
    Calculate probability-based risk metrics
    """
    
    @staticmethod
    def probability_of_profit(
        positions: list,
        spot_price: float,
        volatility: float,
        time_to_expiry: float,
        distribution: str = 'lognormal'  # or 'normal', 'empirical'
    ) -> dict:
        """
        Calculate probability that strategy is profitable at expiry
        
        Returns: {
            'pop': float,  # Probability of profit (0-1)
            'expected_value': float,  # Mathematical expectation
            'value_at_risk': float,  # VaR at 95% confidence
            'conditional_var': float,  # Expected loss beyond VaR
            'profit_ranges': [
                {
                    'price_range': (float, float),
                    'probability': float,
                    'profit': float
                }
            ]
        }
        """
        pass
    
    @staticmethod
    def monte_carlo_simulation(
        positions: list,
        spot_price: float,
        volatility: float,
        time_to_expiry: float,
        num_simulations: int = 10000
    ) -> dict:
        """
        Monte Carlo simulation for complex strategies
        
        Returns: {
            'final_prices': [float],  # Distribution of outcomes
            'final_pnls': [float],
            'percentiles': {
                'p5': float,
                'p25': float,
                'p50': float,  # Median
                'p75': float,
                'p95': float
            },
            'histogram': {
                'bins': [float],
                'frequencies': [int]
            }
        }
        """
        pass
```

### 2.2 Risk Metrics

**Enhancement to existing calculator:**

```python
class RiskMetrics:
    """
    Comprehensive risk analysis
    """
    
    @staticmethod
    def calculate_risk_reward(positions: list, spot_price: float) -> dict:
        """
        Returns: {
            'max_profit': float,
            'max_loss': float,
            'risk_reward_ratio': float,
            'profit_probability': float,
            'expected_return': float,
            'required_move': float,  # % move needed for profit
            'days_to_breakeven': int,  # Based on theta
            'margin_requirement': float,
            'return_on_margin': float  # ROI
        }
        """
        pass
    
    @staticmethod
    def stress_test(
        positions: list,
        scenarios: list  # [{price_change: %, vol_change: %}]
    ) -> list:
        """
        Stress test across multiple scenarios
        
        Returns: [
            {
                'scenario': str,
                'price_change': float,
                'vol_change': float,
                'resulting_pnl': float,
                'greeks_impact': {...}
            }
        ]
        """
        pass
```

---

## Part 3: Frontend/WebUI Enhancements

### 3.1 Enhanced Payoff Chart Component

**File: webui/frontend/src/components/options/OptionsPayoffDiagram.js**

**Current Issues:**
- Basic 2-line chart (expiry + target)
- Limited interactivity
- No probability overlay
- No Greeks overlay

**Enhancement Plan:**

```javascript
/**
 * ENHANCED: Professional-grade options payoff diagram
 * 
 * Features to Add:
 * 1. Multiple curves: Expiry + multiple time horizons
 * 2. Probability density overlay
 * 3. Greeks visualization (separate panel or overlay)
 * 4. Interactive tooltips with detailed breakdown
 * 5. Scenario comparison (side-by-side)
 * 6. 3D surface view (price x time x P&L)
 * 7. Risk zone highlighting
 * 8. Volatility smile visualization
 */

const EnhancedPayoffDiagram = ({
    positions,
    futuresPositions,
    hiddenPositions,
    displayMode = 'standard', // 'standard', '3d', 'heatmap', 'probability'
    showGreeks = true,
    showProbability = true,
    showMetrics = true,
    timeHorizons = [0, 7, 14, 30], // days to expiry
    priceRange = 20, // % from spot
    resolution = 200 // data points
}) => {
    
    // Feature 1: Multi-time-horizon curves
    const [selectedTimeHorizons, setSelectedTimeHorizons] = useState([0, 15]);
    
    // Feature 2: Probability overlay
    const [showProbabilityDensity, setShowProbabilityDensity] = useState(true);
    
    // Feature 3: Greeks panel
    const [selectedGreek, setSelectedGreek] = useState('delta'); // delta, gamma, theta, vega
    
    // Feature 4: Scenario comparison
    const [scenarios, setScenarios] = useState([
        { name: 'Base', volChange: 0, priceChange: 0 },
        { name: '+10% Vol', volChange: 10, priceChange: 0 }
    ]);
    
    // Feature 5: View mode
    const [viewMode, setViewMode] = useState('2d'); // '2d', '3d', 'heatmap'
    
    // ... rest of implementation
};
```

### 3.2 New UI Components

#### A. Greeks Dashboard Panel
```javascript
/**
 * NEW COMPONENT: webui/frontend/src/components/options/GreeksDashboard.js
 * 
 * Display portfolio Greeks with:
 * - Real-time Greek values
 * - Greek sensitivity charts
 * - Risk ladder (Greeks at different price levels)
 * - Delta hedging calculator
 */

const GreeksDashboard = ({ positions }) => {
    return (
        <Paper>
            {/* Portfolio Greeks Summary */}
            <Box>
                <Chip label={`Δ: ${portfolioGreeks.delta.toFixed(2)}`} />
                <Chip label={`Γ: ${portfolioGreeks.gamma.toFixed(3)}`} />
                <Chip label={`θ: $${portfolioGreeks.theta.toFixed(2)}/day`} />
                <Chip label={`ν: ${portfolioGreeks.vega.toFixed(2)}`} />
            </Box>
            
            {/* Greeks Charts */}
            <ResponsiveContainer>
                <LineChart data={greeksOverPrice}>
                    {/* Show how Greeks change with price */}
                </LineChart>
            </ResponsiveContainer>
            
            {/* Risk Zones */}
            <Box>
                <Typography>⚠️ High Gamma Zone: $95,000 - $98,000</Typography>
                <Typography>📉 Max Theta Decay: ${thetaPerDay}/day</Typography>
            </Box>
        </Paper>
    );
};
```

#### B. Probability Analysis Panel
```javascript
/**
 * NEW COMPONENT: webui/frontend/src/components/options/ProbabilityAnalysis.js
 * 
 * Show probability distributions and risk metrics
 */

const ProbabilityAnalysis = ({ positions, spotPrice, volatility }) => {
    const probabilityData = useMemo(() => {
        // Calculate using Monte Carlo or lognormal distribution
        return calculateProbabilityDistribution(positions, spotPrice, volatility);
    }, [positions, spotPrice, volatility]);
    
    return (
        <Paper>
            {/* Key Metrics */}
            <Grid container spacing={2}>
                <Grid item xs={3}>
                    <Metric 
                        label="Probability of Profit" 
                        value={`${probabilityData.pop.toFixed(1)}%`}
                        color={probabilityData.pop > 50 ? 'success' : 'error'}
                    />
                </Grid>
                <Grid item xs={3}>
                    <Metric 
                        label="Expected Value" 
                        value={`$${probabilityData.expectedValue.toFixed(2)}`}
                    />
                </Grid>
                <Grid item xs={3}>
                    <Metric 
                        label="VaR (95%)" 
                        value={`$${probabilityData.var95.toFixed(2)}`}
                        color="warning"
                    />
                </Grid>
                <Grid item xs={3}>
                    <Metric 
                        label="Risk/Reward" 
                        value={`1:${probabilityData.riskReward.toFixed(2)}`}
                    />
                </Grid>
            </Grid>
            
            {/* Probability Distribution Chart */}
            <ResponsiveContainer height={300}>
                <ComposedChart data={probabilityData.distribution}>
                    {/* Bar chart: probability density */}
                    <Bar dataKey="probability" fill="#3b82f6" opacity={0.3} />
                    
                    {/* Area: payoff at each price */}
                    <Area dataKey="payoff" stroke="#10b981" fill="url(#profitGradient)" />
                </ComposedChart>
            </ResponsiveContainer>
            
            {/* Monte Carlo Results */}
            <Box sx={{ mt: 2 }}>
                <Typography variant="h6">Simulated Outcomes (10,000 trials)</Typography>
                <Stack direction="row" spacing={2}>
                    <Chip label={`P5: $${probabilityData.percentiles.p5}`} size="small" />
                    <Chip label={`P25: $${probabilityData.percentiles.p25}`} size="small" />
                    <Chip label={`Median: $${probabilityData.percentiles.p50}`} size="small" color="primary" />
                    <Chip label={`P75: $${probabilityData.percentiles.p75}`} size="small" />
                    <Chip label={`P95: $${probabilityData.percentiles.p95}`} size="small" />
                </Stack>
            </Box>
        </Paper>
    );
};
```

#### C. Payoff Heatmap (3D Alternative)
```javascript
/**
 * NEW COMPONENT: webui/frontend/src/components/options/PayoffHeatmap.js
 * 
 * 2D heatmap showing P&L across price AND time
 * Easier to read than 3D surface
 */

const PayoffHeatmap = ({ positions, spotPrice }) => {
    // X-axis: Underlying price
    // Y-axis: Days to expiry
    // Color: P&L (green = profit, red = loss)
    
    return (
        <Paper>
            <Typography variant="h6">P&L Surface (Price vs. Time)</Typography>
            
            {/* Use recharts or custom canvas rendering */}
            <Box sx={{ width: '100%', height: 400 }}>
                {/* Render heatmap grid */}
                {heatmapData.map((row, timeIdx) => (
                    row.map((cell, priceIdx) => (
                        <HeatmapCell 
                            key={`${timeIdx}-${priceIdx}`}
                            value={cell.pnl}
                            color={cell.pnl > 0 ? 'green' : 'red'}
                            opacity={Math.abs(cell.pnl) / maxAbsPnl}
                        />
                    ))
                ))}
            </Box>
            
            {/* Interactive controls */}
            <Box sx={{ mt: 2 }}>
                <Slider 
                    label="Time Horizon" 
                    min={0} 
                    max={maxDaysToExpiry}
                    onChange={(value) => highlightTimeSlice(value)}
                />
            </Box>
        </Paper>
    );
};
```

#### D. Scenario Comparison Tool
```javascript
/**
 * NEW COMPONENT: webui/frontend/src/components/options/ScenarioComparison.js
 * 
 * Compare payoff under different market scenarios
 */

const ScenarioComparison = ({ positions }) => {
    const [scenarios, setScenarios] = useState([
        { id: 1, name: 'Base Case', priceChange: 0, volChange: 0 },
        { id: 2, name: 'Rally +10%', priceChange: 10, volChange: -5 },
        { id: 3, name: 'Crash -15%', priceChange: -15, volChange: 20 },
        { id: 4, name: 'Vol Spike', priceChange: 0, volChange: 50 }
    ]);
    
    return (
        <Paper>
            <Typography variant="h6">Scenario Analysis</Typography>
            
            {/* Scenario table */}
            <Table>
                <TableHead>
                    <TableRow>
                        <TableCell>Scenario</TableCell>
                        <TableCell>Price Change</TableCell>
                        <TableCell>Vol Change</TableCell>
                        <TableCell>Resulting P&L</TableCell>
                        <TableCell>ΔP&L from Base</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {scenarioResults.map((result) => (
                        <TableRow key={result.id}>
                            <TableCell>{result.name}</TableCell>
                            <TableCell>{result.priceChange}%</TableCell>
                            <TableCell>{result.volChange}%</TableCell>
                            <TableCell>
                                <Typography color={result.pnl > 0 ? 'success' : 'error'}>
                                    ${result.pnl.toFixed(2)}
                                </Typography>
                            </TableCell>
                            <TableCell>${result.deltaPnl.toFixed(2)}</TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
            
            {/* Visual comparison */}
            <ResponsiveContainer height={300}>
                <BarChart data={scenarioResults}>
                    <Bar dataKey="pnl" fill="#3b82f6" />
                    <ReferenceLine y={0} stroke="#666" />
                </BarChart>
            </ResponsiveContainer>
        </Paper>
    );
};
```

### 3.3 Enhanced Main Chart Features

**Additions to OptionsPayoffDiagram.js:**

```javascript
// Feature 1: Multiple time-horizon curves
const timeHorizonCurves = useMemo(() => {
    return [0, 7, 14, 30, 45].map(daysToExpiry => {
        return calculatePayoffCurve(positions, spotPrice, daysToExpiry);
    });
}, [positions, spotPrice]);

// Feature 2: Probability density overlay
const probabilityOverlay = useMemo(() => {
    // Lognormal distribution based on IV
    return calculateLognormalDensity(spotPrice, volatility, timeToExpiry);
}, [spotPrice, volatility, timeToExpiry]);

// Feature 3: Greeks as separate curve
const greeksCurve = useMemo(() => {
    return calculateGreeksOverPrice(positions, selectedGreek);
}, [positions, selectedGreek]);

// Feature 4: Risk zones highlighting
const riskZones = useMemo(() => {
    return identifyRiskZones(payoffData);
    // Example: { 
    //   maxLossZone: [85000, 88000],
    //   maxProfitZone: [95000, 105000],
    //   highGammaZone: [92000, 98000]
    // }
}, [payoffData]);

// Feature 5: Interactive annotations
const [annotations, setAnnotations] = useState([
    { price: spotPrice, label: 'Current', type: 'spot' },
    { price: 95000, label: 'Target', type: 'user' }
]);

// Feature 6: Brush/zoom with domain locking
const [zoomDomain, setZoomDomain] = useState(null);
const [focusRegion, setFocusRegion] = useState(null); // User can select region to analyze

// Chart rendering with all features:
return (
    <ComposedChart data={chartData}>
        {/* Background: Risk zones */}
        {riskZones.maxLossZone && (
            <ReferenceArea 
                x1={riskZones.maxLossZone[0]} 
                x2={riskZones.maxLossZone[1]}
                fill="red"
                fillOpacity={0.1}
                label="Max Loss Zone"
            />
        )}
        
        {/* Probability density (secondary Y-axis) */}
        <Area 
            dataKey="probability" 
            yAxisId="right"
            fill="blue"
            opacity={0.2}
        />
        
        {/* Multiple time horizon curves */}
        {timeHorizonCurves.map((curve, idx) => (
            <Line 
                key={idx}
                data={curve.data}
                dataKey="pnl"
                stroke={curve.color}
                strokeWidth={idx === 0 ? 3 : 1.5}
                strokeDasharray={idx === 0 ? '0' : '5 5'}
                name={`${curve.daysToExpiry} days to expiry`}
            />
        ))}
        
        {/* Greeks overlay (optional, toggled) */}
        {showGreeks && (
            <Line 
                data={greeksCurve}
                dataKey="value"
                yAxisId="right"
                stroke="purple"
                strokeWidth={1}
                name={`Portfolio ${selectedGreek.toUpperCase()}`}
            />
        )}
        
        {/* User annotations */}
        {annotations.map((ann, idx) => (
            <ReferenceLine 
                key={idx}
                x={ann.price}
                stroke={ann.type === 'spot' ? 'blue' : 'orange'}
                strokeDasharray="3 3"
                label={ann.label}
            />
        ))}
        
        {/* Breakeven points */}
        {breakevenPoints.map((be, idx) => (
            <ReferenceLine 
                key={idx}
                x={be}
                stroke="yellow"
                strokeDasharray="5 5"
                label={{ value: 'BE', position: 'top' }}
            />
        ))}
    </ComposedChart>
);
```

---

## Part 4: Data Validation & Edge Cases

### 4.1 Input Validation

```python
class DataValidator:
    """
    Validate all inputs before calculation
    """
    
    @staticmethod
    def validate_position(position: dict) -> tuple[bool, str]:
        """
        Returns: (is_valid, error_message)
        
        Checks:
        - Strike > 0
        - Premium >= 0
        - Time to expiry >= 0
        - Volatility > 0 and < 5.0 (500%)
        - Quantity != 0
        - Valid option type (call/put)
        - Valid side (buy/sell)
        """
        pass
    
    @staticmethod
    def validate_strategy(positions: list) -> tuple[bool, str]:
        """
        Strategy-level validation
        
        Checks:
        - Not empty
        - All positions have same underlying
        - Expiries are in the future
        - No duplicate legs
        - Position sizing is reasonable
        """
        pass
    
    @staticmethod
    def sanitize_greeks_input(greeks: dict) -> dict:
        """
        Handle NaN, Infinity, None in Greeks data
        """
        pass
```

### 4.2 Edge Case Handling

**Cases to handle:**

1. **Zero or negative time to expiry**
   - At expiry: Use intrinsic value only
   - Past expiry: Positions are expired (P&L is locked)

2. **Zero or negative volatility**
   - Use minimum floor (e.g., 5%)
   - Log warning

3. **Deep ITM/OTM options**
   - Delta approaches 1.0 or 0.0
   - Greeks calculations can be unstable

4. **Very short-dated options (< 1 hour)**
   - Use minutes instead of days
   - Higher gamma risk

5. **Extreme strikes (far from spot)**
   - Adjust price range dynamically
   - Don't show irrelevant price ranges

6. **Large position sizes**
   - Show warning about margin requirements
   - Display dollar-denominated Greeks

7. **Mixed expiries in strategy**
   - Show warning about expiry mismatch
   - Calculate separate expiry curves

8. **American vs European**
   - Add flag to distinguish
   - Use appropriate pricing model

9. **Contract multipliers**
   - BTC: 0.001 ($0.001 per $1 move)
   - ETH: varies
   - Standardize across all components

---

## Part 5: Performance Optimization

### 5.1 Backend Optimization

```python
# Use numpy for vectorized calculations
import numpy as np

class OptimizedPayoffCalculator:
    """
    Vectorized calculations for speed
    """
    
    @staticmethod
    def calculate_payoff_vectorized(
        positions: list,
        price_array: np.ndarray  # All prices at once
    ) -> np.ndarray:
        """
        Calculate payoff for all prices in parallel
        10-100x faster than loop
        """
        # Vectorized intrinsic value calculation
        strikes = np.array([p['strike'] for p in positions])
        # ... vectorized operations
        pass
```

### 5.2 Frontend Optimization

```javascript
// Use Web Workers for heavy calculations
const payoffWorker = new Worker('payoff-calculator.worker.js');

payoffWorker.postMessage({
    positions,
    priceRange: [minPrice, maxPrice],
    numPoints: 200
});

payoffWorker.onmessage = (e) => {
    const { payoffData, greeks, probability } = e.data;
    setChartData(payoffData);
};

// Memoization for expensive calculations
const memoizedPayoff = useMemo(() => {
    return calculatePayoff(positions, spotPrice, volatility);
}, [positions, spotPrice, volatility]); // Only recalc when these change

// Virtual scrolling for large datasets
import { FixedSizeList } from 'react-window';

// Debounce slider inputs
const debouncedCalculation = useMemo(
    () => debounce((value) => recalculatePayoff(value), 300),
    []
);
```

---

## Part 6: Testing & Validation

### 6.1 Unit Tests

```python
# webui/backend/tests/test_payoff_calculator.py

def test_long_call_payoff():
    """Test long call payoff at various prices"""
    position = {
        'option_type': 'call',
        'side': 'buy',
        'strike': 100,
        'premium': 5,
        'quantity': 1
    }
    
    # At strike: loss = premium
    assert calculate_payoff(position, 100) == -5
    
    # $10 above strike: profit = $10 - $5 = $5
    assert calculate_payoff(position, 110) == 5
    
    # Below strike: loss = premium
    assert calculate_payoff(position, 90) == -5

def test_iron_condor_payoff():
    """Test 4-leg iron condor"""
    positions = [
        # Short call spread
        {'type': 'call', 'side': 'sell', 'strike': 105, 'premium': 3, 'qty': 1},
        {'type': 'call', 'side': 'buy', 'strike': 110, 'premium': 1, 'qty': 1},
        # Short put spread
        {'type': 'put', 'side': 'sell', 'strike': 95, 'premium': 3, 'qty': 1},
        {'type': 'put', 'side': 'buy', 'strike': 90, 'premium': 1, 'qty': 1},
    ]
    
    # Max profit in the middle: $3 + $3 - $1 - $1 = $4
    assert calculate_strategy_payoff(positions, 100) == 4
    
    # Max loss at extremes: -($5 - $4) = -$1
    assert calculate_strategy_payoff(positions, 115) == -1
    assert calculate_strategy_payoff(positions, 85) == -1
    
    # Breakevens at $91 and $109
    assert abs(calculate_strategy_payoff(positions, 91)) < 0.1
    assert abs(calculate_strategy_payoff(positions, 109)) < 0.1

def test_greeks_accuracy():
    """Test Greeks against known values"""
    # Use benchmark values from academic sources
    pass
```

### 6.2 Integration Tests

```javascript
// webui/frontend/src/components/options/__tests__/OptionsPayoffDiagram.test.js

describe('OptionsPayoffDiagram', () => {
    test('renders payoff chart for single long call', () => {
        const positions = [{
            product_symbol: 'C-BTCUSD-100000-310126',
            size: 10,
            entry_price: 2000,
            mark_price: 2500
        }];
        
        const { container } = render(
            <OptionsPayoffDiagram positions={positions} />
        );
        
        expect(container.querySelector('.recharts-line')).toBeInTheDocument();
    });
    
    test('calculates correct breakeven for bull call spread', () => {
        const positions = [
            // Buy 95 call at $5
            { type: 'call', side: 'buy', strike: 95, premium: 5 },
            // Sell 105 call at $2
            { type: 'call', side: 'sell', strike: 105, premium: 2 }
        ];
        
        const { breakevens } = calculatePayoffMetrics(positions, 100);
        
        // Breakeven = lower strike + net debit
        // 95 + (5 - 2) = 98
        expect(breakevens[0]).toBeCloseTo(98, 1);
    });
    
    test('handles extreme volatility gracefully', () => {
        const positions = [{ /* ... */ }];
        
        // 200% IV should not crash
        expect(() => {
            calculatePayoff(positions, 100, { volatility: 2.0 });
        }).not.toThrow();
    });
});
```

### 6.3 Visual Regression Tests

```javascript
// Use Storybook + Chromatic for visual testing

export const LongCall = () => (
    <OptionsPayoffDiagram 
        positions={[MOCK_LONG_CALL_POSITION]}
    />
);

export const IronCondor = () => (
    <OptionsPayoffDiagram 
        positions={MOCK_IRON_CONDOR}
    />
);

export const ComplexStrategy = () => (
    <OptionsPayoffDiagram 
        positions={MOCK_COMPLEX_STRATEGY}
        showGreeks={true}
        showProbability={true}
    />
);
```

---

## Part 7: Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
**Goal:** Fix critical calculation issues and unify codebase

- [ ] **Task 1.1:** Create unified backend pricing engine
  - File: `webui/backend/options_strategy/pricing_engine.py`
  - Implement Black-Scholes-Merton with dividends
  - Add binomial tree for American options
  - Write comprehensive unit tests

- [ ] **Task 1.2:** Enhance IV calculator
  - Add multiple solving methods (Brent, bisection backup)
  - Handle edge cases (deep ITM/OTM, near expiry)
  - Build volatility surface interpolation

- [ ] **Task 1.3:** Complete Greeks calculator
  - Add all first-order Greeks (Δ, Γ, θ, ν, ρ)
  - Add second-order Greeks (Vanna, Charm, Vomma)
  - Implement portfolio-level aggregation

- [ ] **Task 1.4:** Fix multiplier inconsistencies
  - Audit all payoff calculations (3+ locations)
  - Standardize contract multiplier (0.001 for BTC/ETH)
  - Update both frontend and backend

- [ ] **Task 1.5:** Add comprehensive input validation
  - Validate all position data
  - Handle edge cases (zero time, negative values)
  - Add error messages for users

**Deliverable:** Robust calculation engine with 95%+ test coverage

---

### Phase 2: Risk Metrics (Week 3-4)
**Goal:** Add probability analysis and risk metrics

- [ ] **Task 2.1:** Implement Probability of Profit (PoP)
  - File: `webui/backend/options_strategy/probability_analyzer.py`
  - Lognormal distribution calculation
  - Monte Carlo simulation (10k+ runs)
  - Expected value calculation

- [ ] **Task 2.2:** Add Value-at-Risk (VaR) calculator
  - 95% and 99% confidence VaR
  - Conditional VaR (CVaR/Expected Shortfall)
  - Time-horizon VaR (1 day, 1 week, to expiry)

- [ ] **Task 2.3:** Build risk metrics calculator
  - Max profit/loss (handle unlimited cases)
  - Risk/reward ratio
  - Profit ranges with probabilities
  - Margin requirements

- [ ] **Task 2.4:** Create stress testing module
  - Predefined scenarios (market crash, vol spike, etc.)
  - Custom scenario builder
  - Greeks sensitivity analysis

**Deliverable:** Complete risk analysis suite with probability distributions

---

### Phase 3: Enhanced Visualization (Week 5-6)
**Goal:** Professional-grade UI matching industry standards

- [ ] **Task 3.1:** Enhance main payoff chart
  - File: `webui/frontend/src/components/options/OptionsPayoffDiagram.js`
  - Add multiple time-horizon curves (T-0, T-7, T-14, T-30)
  - Add probability density overlay
  - Implement risk zone highlighting
  - Add interactive annotations

- [ ] **Task 3.2:** Create Greeks Dashboard
  - File: `webui/frontend/src/components/options/GreeksDashboard.js`
  - Portfolio Greeks display
  - Greeks-over-price charts
  - Risk ladder visualization

- [ ] **Task 3.3:** Build Probability Analysis Panel
  - File: `webui/frontend/src/components/options/ProbabilityAnalysis.js`
  - PoP, Expected Value, VaR display
  - Probability distribution chart
  - Monte Carlo histogram
  - Percentiles (P5, P25, P50, P75, P95)

- [ ] **Task 3.4:** Create Payoff Heatmap component
  - File: `webui/frontend/src/components/options/PayoffHeatmap.js`
  - 2D heatmap (price x time)
  - Color-coded P&L zones
  - Interactive time slider

- [ ] **Task 3.5:** Build Scenario Comparison tool
  - File: `webui/frontend/src/components/options/ScenarioComparison.js`
  - Scenario table and charts
  - Custom scenario builder
  - Side-by-side comparison

**Deliverable:** Industry-standard visualization suite

---

### Phase 4: Advanced Features (Week 7-8)
**Goal:** Professional-grade features for advanced traders

- [ ] **Task 4.1:** Implement 3D surface view
  - Using WebGL or Three.js
  - P&L surface (price x time x P&L)
  - Rotate, zoom, pan controls

- [ ] **Task 4.2:** Add volatility smile visualization
  - Plot IV vs. Strike
  - Show skew metrics
  - Overlay strategy strikes

- [ ] **Task 4.3:** Create what-if simulator
  - Adjust any parameter (price, vol, time)
  - See instant impact on P&L and Greeks
  - Save scenarios for comparison

- [ ] **Task 4.4:** Add portfolio-level analysis
  - Combine options + futures
  - Delta hedging calculator
  - Portfolio Greeks
  - Correlation analysis

- [ ] **Task 4.5:** Build export functionality
  - Export charts as PNG/SVG
  - Export data as CSV/Excel
  - Generate PDF reports

**Deliverable:** Complete professional trading suite

---

### Phase 5: Performance & Polish (Week 9-10)
**Goal:** Production-ready optimization

- [ ] **Task 5.1:** Backend optimization
  - Vectorize calculations with NumPy
  - Cache expensive computations
  - Add request rate limiting

- [ ] **Task 5.2:** Frontend optimization
  - Use Web Workers for calculations
  - Implement memoization
  - Add loading states
  - Optimize re-renders

- [ ] **Task 5.3:** Testing & QA
  - Achieve 95%+ test coverage
  - Visual regression tests
  - Performance benchmarking
  - User acceptance testing

- [ ] **Task 5.4:** Documentation
  - API documentation
  - User guide with examples
  - Developer documentation
  - Video tutorials

**Deliverable:** Production-ready, performant system

---

## Part 8: Success Metrics

### Technical Metrics
- ✅ **Calculation Accuracy:** < 0.1% error vs. industry benchmarks
- ✅ **Performance:** < 100ms for payoff curve calculation (200 points)
- ✅ **Test Coverage:** > 95% code coverage
- ✅ **Reliability:** 99.9% uptime for calculation API

### User Experience Metrics
- ✅ **Load Time:** Chart renders in < 500ms
- ✅ **Responsiveness:** Slider updates in < 100ms
- ✅ **Mobile Support:** Fully responsive on tablets/phones

### Feature Completeness
- ✅ All common strategies supported (spreads, condors, butterflies, etc.)
- ✅ Greeks calculated for all positions
- ✅ Probability analysis available
- ✅ Multiple visualization modes
- ✅ Export functionality

---

## Part 9: Industry Benchmarks (What We're Competing With)

### Reference Platforms

1. **ThinkorSwim (TD Ameritrade)**
   - Features: Risk profile, Greeks, probability cone, Monte Carlo
   - Strengths: Very detailed, professional-grade
   - Our Goal: Match or exceed calculation accuracy

2. **Sensibull (India)**
   - Features: Clean UI, expiry + target curves, strategy builder
   - Strengths: User-friendly, visual clarity
   - Our Goal: Match UI simplicity, add more analytics

3. **OptionsPlay**
   - Features: AI-driven strategy suggestions, win probability
   - Strengths: Beginner-friendly
   - Our Goal: Similar probability displays

4. **IBKR (Interactive Brokers)**
   - Features: Risk graphs, volatility smile, scenario analysis
   - Strengths: Institutional-grade accuracy
   - Our Goal: Match calculation precision

5. **TradingView Options Module**
   - Features: Real-time Greeks, strategy analyzer
   - Strengths: Integration with charting
   - Our Goal: Better probability analysis

**Our Competitive Advantage:**
- ✅ Crypto-native (BTC/ETH focus)
- ✅ Real-time Delta Exchange integration
- ✅ Combined options + futures visualization
- ✅ Open-source and customizable
- ✅ No subscription required

---

## Part 10: Technical Specifications

### API Endpoints (Backend)

```python
# Enhanced API routes

@options_strategy_bp.route('/payoff/calculate', methods=['POST'])
def calculate_payoff():
    """
    Request:
    {
        "positions": [...],
        "price_range_pct": 25,
        "num_points": 200,
        "time_points": [0, 7, 14, 30],  # Multiple curves
        "include_greeks": true,
        "include_probability": true
    }
    
    Response:
    {
        "curves": [
            {
                "days_to_expiry": 0,
                "prices": [float],
                "payoffs": [float],
                "deltas": [float],
                "gammas": [float]
            }
        ],
        "probability": {
            "pop": float,
            "expected_value": float,
            "var_95": float,
            "distribution": [...]
        },
        "greeks": {
            "portfolio_delta": float,
            "portfolio_gamma": float,
            "portfolio_theta": float,
            "portfolio_vega": float
        },
        "risk_metrics": {
            "max_profit": float,
            "max_loss": float,
            "breakevens": [float],
            "risk_reward": float
        }
    }
    """
    pass

@options_strategy_bp.route('/greeks/portfolio', methods=['POST'])
def calculate_portfolio_greeks():
    """Calculate aggregated portfolio Greeks"""
    pass

@options_strategy_bp.route('/probability/analyze', methods=['POST'])
def analyze_probability():
    """Run Monte Carlo simulation and probability analysis"""
    pass

@options_strategy_bp.route('/stress-test', methods=['POST'])
def stress_test_strategy():
    """Run stress test scenarios"""
    pass
```

### Data Models

```python
# webui/backend/options_strategy/models.py

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class OptionPosition:
    """Single option leg"""
    symbol: str
    option_type: str  # 'call' or 'put'
    side: str  # 'buy' or 'sell'
    strike: float
    expiry_date: str  # ISO format
    quantity: int
    entry_price: float
    current_price: Optional[float] = None
    implied_volatility: Optional[float] = None
    greeks: Optional[dict] = None

@dataclass
class PayoffCurve:
    """Payoff curve at specific time"""
    days_to_expiry: float
    prices: List[float]
    payoffs: List[float]
    deltas: Optional[List[float]] = None
    gammas: Optional[List[float]] = None
    thetas: Optional[List[float]] = None

@dataclass
class ProbabilityAnalysis:
    """Probability and risk metrics"""
    probability_of_profit: float  # 0-1
    expected_value: float
    var_95: float
    cvar_95: float
    distribution: List[dict]  # [{price: float, probability: float, payoff: float}]
    percentiles: dict  # {p5, p25, p50, p75, p95}

@dataclass
class PortfolioGreeks:
    """Aggregated portfolio Greeks"""
    delta: float
    gamma: float
    theta: float  # per day
    vega: float
    rho: float
    dollar_delta: float
    dollar_gamma: float
```

---

## Part 11: Documentation Plan

### User Documentation

1. **User Guide: Payoff Diagram Basics**
   - How to read payoff charts
   - Understanding breakeven points
   - Interpreting max profit/loss

2. **User Guide: Greeks Explained**
   - What each Greek means
   - How to use Greeks for risk management
   - Portfolio Greeks interpretation

3. **User Guide: Probability Analysis**
   - Understanding PoP
   - Expected value vs. max profit
   - Value-at-Risk interpretation

4. **Strategy Examples**
   - Long call example with full analysis
   - Iron condor step-by-step
   - Calendar spread visualization
   - Butterfly spread breakdown

### Developer Documentation

1. **API Documentation**
   - All endpoint specifications
   - Request/response examples
   - Error codes and handling

2. **Calculation Reference**
   - Black-Scholes implementation details
   - Greeks formulas
   - Probability calculation methods

3. **Architecture Overview**
   - Component structure
   - Data flow diagrams
   - State management

4. **Contributing Guide**
   - How to add new strategies
   - Testing requirements
   - Code style guidelines

---

## Part 12: Future Enhancements (Post-MVP)

### Advanced Features (Phase 6+)

1. **Machine Learning Integration**
   - Predict optimal exit times
   - Suggest hedging strategies
   - Anomaly detection in Greeks

2. **Real-Time Alerts**
   - Price crosses breakeven
   - Greeks reach thresholds
   - Probability of profit drops below X%

3. **Backtesting**
   - Historical payoff analysis
   - Strategy performance over time
   - Win rate statistics

4. **Social Features**
   - Share strategies
   - Leaderboard of strategy performance
   - Strategy marketplace

5. **Mobile App**
   - Native iOS/Android app
   - Push notifications
   - Simplified mobile UI

6. **Voice Control**
   - "Show me the payoff for my position"
   - "What's my portfolio delta?"
   - "Calculate probability of profit"

---

## Part 13: Options & Futures Panel UI/UX Enhancements

### Current State Analysis

Both the Options Panel and Futures Panel are functional but suffer from:
- ❌ **Information Overload:** Too many columns (15+), overwhelming for users
- ❌ **Poor Visual Hierarchy:** No clear separation of critical vs. secondary info
- ❌ **Inconsistent Design:** Different patterns between Options and Futures panels
- ❌ **Limited Responsiveness:** Tables don't work well on smaller screens
- ❌ **Missing Context:** No quick access to position history or trade notes
- ❌ **Cluttered Controls:** Action buttons mixed with data display
- ❌ **Poor Grouping:** Related positions not visually grouped
- ❌ **No Quick Actions:** Too many clicks to perform common tasks
- ❌ **Limited Customization:** Users can't personalize their workspace
- ❌ **Weak Visual Feedback:** Unclear which positions need attention

### 13.1 Professional Trading Panel Design Principles

#### A. Information Architecture

**Three-Tier Information Hierarchy:**

1. **Primary (Always Visible):**
   - Symbol & Type (Call/Put, Long/Short)
   - Current P&L (with color coding)
   - Size & Entry Price
   - Quick Actions (Close, Add, Adjust)

2. **Secondary (Visible on Hover/Expand):**
   - Greeks (Delta, Gamma, Theta, Vega)
   - Bid/Ask spread
   - Volume & Open Interest
   - Time to Expiry

3. **Tertiary (On Demand):**
   - Trade history for this position
   - Transaction costs breakdown
   - Position notes/tags
   - Related orders

#### B. Visual Design Standards

**Color System:**
```javascript
const TRADING_COLORS = {
  // P&L Colors
  profit: {
    strong: '#10b981',    // > 20% profit
    moderate: '#34d399',  // 5-20% profit
    weak: '#6ee7b7'       // 0-5% profit
  },
  loss: {
    weak: '#fca5a5',      // 0-5% loss
    moderate: '#f87171',  // 5-20% loss
    strong: '#ef4444'     // > 20% loss
  },
  
  // Position Types
  options: {
    call: '#3b82f6',      // Blue for calls
    put: '#f59e0b'        // Orange for puts
  },
  futures: {
    long: '#10b981',      // Green for long
    short: '#ef4444'      // Red for short
  },
  
  // Status Indicators
  warning: '#f59e0b',     // Approaching limits
  danger: '#ef4444',      // Breached limits
  info: '#3b82f6',        // Informational
  success: '#10b981',     // Successful action
  
  // Time Urgency
  expiry: {
    immediate: '#ef4444', // < 1 day
    soon: '#f59e0b',      // 1-3 days
    medium: '#eab308',    // 3-7 days
    far: '#10b981'        // > 7 days
  }
};
```

**Typography Scale:**
```javascript
const TRADING_TYPOGRAPHY = {
  // P&L Display
  pnl: {
    fontSize: '1.25rem',
    fontWeight: 700,
    fontFamily: 'monospace'
  },
  
  // Critical Numbers (Strike, Entry)
  critical: {
    fontSize: '1rem',
    fontWeight: 600,
    fontFamily: 'monospace'
  },
  
  // Secondary Info
  secondary: {
    fontSize: '0.875rem',
    fontWeight: 400,
    color: 'text.secondary'
  },
  
  // Labels
  label: {
    fontSize: '0.75rem',
    fontWeight: 500,
    textTransform: 'uppercase',
    letterSpacing: '0.05em'
  }
};
```

### 13.2 Options Panel Enhancement

#### A. Card-Based Layout (Instead of Table)

**NEW DESIGN: Expandable Position Cards**

```javascript
/**
 * NEW COMPONENT: webui/frontend/src/components/options/PositionCard.js
 * 
 * Modern card-based position display
 */

const PositionCard = ({ position, onClose, onAdjust, onExpand }) => {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <Paper 
      elevation={2}
      sx={{
        p: 2,
        mb: 1.5,
        borderRadius: 2,
        border: `2px solid ${getBorderColor(position)}`,
        transition: 'all 0.2s',
        '&:hover': {
          boxShadow: 4,
          transform: 'translateY(-2px)'
        }
      }}
    >
      {/* COMPACT VIEW (Always Visible) */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        
        {/* Left: Symbol & Type */}
        <Box sx={{ flex: '0 0 200px' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <OptionTypeChip type={position.option_type} side={position.side} />
            <Typography variant="h6" fontWeight={600}>
              {position.strike}
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary">
            {formatExpiry(position.expiry)} • {position.days_to_expiry}d
          </Typography>
        </Box>
        
        {/* Center: Key Metrics */}
        <Box sx={{ flex: 1, display: 'flex', gap: 3 }}>
          {/* Size */}
          <MetricDisplay 
            label="Size"
            value={position.size}
            icon={<SizeIcon />}
          />
          
          {/* Entry */}
          <MetricDisplay 
            label="Entry"
            value={formatPrice(position.entry_price)}
            icon={<EntryIcon />}
          />
          
          {/* Current */}
          <MetricDisplay 
            label="Mark"
            value={formatPrice(position.mark_price)}
            change={getPercentChange(position)}
          />
        </Box>
        
        {/* Right: P&L & Actions */}
        <Box sx={{ flex: '0 0 250px', display: 'flex', alignItems: 'center', gap: 2 }}>
          {/* P&L Display */}
          <Box sx={{ textAlign: 'right', flex: 1 }}>
            <Typography 
              variant="h5" 
              fontWeight={700}
              color={position.unrealized_pnl > 0 ? 'success.main' : 'error.main'}
            >
              {formatPnL(position.unrealized_pnl)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {formatPnLPercent(position.unrealized_pnl_percent)}%
            </Typography>
          </Box>
          
          {/* Quick Actions */}
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Tooltip title="Close Position">
              <IconButton size="small" onClick={() => onClose(position)}>
                <CloseIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Adjust Size">
              <IconButton size="small" onClick={() => onAdjust(position)}>
                <AdjustIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title={expanded ? "Collapse" : "Expand"}>
              <IconButton size="small" onClick={() => setExpanded(!expanded)}>
                {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      </Box>
      
      {/* EXPANDED VIEW (Greeks, Orders, History) */}
      <Collapse in={expanded}>
        <Divider sx={{ my: 2 }} />
        
        <Grid container spacing={2}>
          {/* Greeks Panel */}
          <Grid item xs={12} md={6}>
            <Typography variant="overline" fontWeight={600}>
              Greeks
            </Typography>
            <Grid container spacing={1} sx={{ mt: 0.5 }}>
              <Grid item xs={3}>
                <GreekChip 
                  label="Δ" 
                  value={position.greeks?.delta} 
                  color="primary"
                />
              </Grid>
              <Grid item xs={3}>
                <GreekChip 
                  label="Γ" 
                  value={position.greeks?.gamma} 
                  color="secondary"
                />
              </Grid>
              <Grid item xs={3}>
                <GreekChip 
                  label="θ" 
                  value={position.greeks?.theta} 
                  color="warning"
                />
              </Grid>
              <Grid item xs={3}>
                <GreekChip 
                  label="ν" 
                  value={position.greeks?.vega} 
                  color="info"
                />
              </Grid>
            </Grid>
          </Grid>
          
          {/* Market Data */}
          <Grid item xs={12} md={6}>
            <Typography variant="overline" fontWeight={600}>
              Market Data
            </Typography>
            <Stack spacing={1} sx={{ mt: 0.5 }}>
              <DataRow label="Bid" value={position.best_bid} />
              <DataRow label="Ask" value={position.best_ask} />
              <DataRow label="IV" value={`${position.implied_volatility}%`} />
              <DataRow label="Volume" value={position.volume} />
            </Stack>
          </Grid>
          
          {/* Risk Controls */}
          <Grid item xs={12}>
            <Typography variant="overline" fontWeight={600}>
              Risk Controls
            </Typography>
            <Box sx={{ mt: 1, display: 'flex', gap: 2 }}>
              <SLTPIndicator position={position} />
              <MaxLossIndicator position={position} />
              <AutomationIndicator position={position} />
            </Box>
          </Grid>
          
          {/* Mini Payoff Chart */}
          <Grid item xs={12}>
            <Typography variant="overline" fontWeight={600}>
              Position Payoff
            </Typography>
            <MiniPayoffChart position={position} height={120} />
          </Grid>
        </Grid>
      </Collapse>
    </Paper>
  );
};
```

#### B. Smart Grouping & Filtering

```javascript
/**
 * NEW COMPONENT: webui/frontend/src/components/options/PositionGrouping.js
 * 
 * Intelligent grouping of positions
 */

const PositionGrouping = ({ positions }) => {
  const [groupBy, setGroupBy] = useState('expiry'); // 'expiry', 'strike', 'strategy', 'none'
  
  const groupedPositions = useMemo(() => {
    switch (groupBy) {
      case 'expiry':
        return groupByExpiry(positions);
      case 'strike':
        return groupByStrike(positions);
      case 'strategy':
        return detectStrategies(positions); // Auto-detect spreads, straddles, etc.
      default:
        return { 'All Positions': positions };
    }
  }, [positions, groupBy]);
  
  return (
    <Box>
      {/* Grouping Controls */}
      <Box sx={{ mb: 2, display: 'flex', gap: 1 }}>
        <Chip 
          label="By Expiry" 
          onClick={() => setGroupBy('expiry')}
          color={groupBy === 'expiry' ? 'primary' : 'default'}
        />
        <Chip 
          label="By Strike" 
          onClick={() => setGroupBy('strike')}
          color={groupBy === 'strike' ? 'primary' : 'default'}
        />
        <Chip 
          label="By Strategy" 
          onClick={() => setGroupBy('strategy')}
          color={groupBy === 'strategy' ? 'primary' : 'default'}
        />
        <Chip 
          label="No Grouping" 
          onClick={() => setGroupBy('none')}
          color={groupBy === 'none' ? 'primary' : 'default'}
        />
      </Box>
      
      {/* Grouped Display */}
      {Object.entries(groupedPositions).map(([group, positions]) => (
        <Accordion key={group} defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
              <Typography variant="h6">{group}</Typography>
              <Chip 
                label={`${positions.length} positions`} 
                size="small"
              />
              <Box sx={{ flex: 1 }} />
              <Typography 
                variant="h6" 
                color={getGroupPnL(positions) > 0 ? 'success.main' : 'error.main'}
              >
                {formatPnL(getGroupPnL(positions))}
              </Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            {positions.map(position => (
              <PositionCard key={position.id} position={position} />
            ))}
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  );
};
```

#### C. Advanced Filtering System

```javascript
/**
 * NEW COMPONENT: webui/frontend/src/components/options/AdvancedFilters.js
 * 
 * Comprehensive filtering for positions
 */

const AdvancedFilters = ({ positions, onFilterChange }) => {
  const [filters, setFilters] = useState({
    // Type filters
    showCalls: true,
    showPuts: true,
    showLong: true,
    showShort: true,
    
    // P&L filters
    minPnL: null,
    maxPnL: null,
    onlyProfit: false,
    onlyLoss: false,
    
    // Expiry filters
    expiries: [],
    maxDaysToExpiry: null,
    
    // Strike filters
    minStrike: null,
    maxStrike: null,
    atm: false,      // At-the-money only
    itm: false,      // In-the-money only
    otm: false,      // Out-of-the-money only
    
    // Greeks filters
    minDelta: null,
    maxDelta: null,
    
    // Risk filters
    hasStopLoss: null,
    hasMaxLoss: null,
    hasAutomation: null,
    
    // Text search
    searchText: ''
  });
  
  // Apply filters
  const filteredPositions = useMemo(() => {
    return positions.filter(pos => {
      // Type filters
      if (!filters.showCalls && isCall(pos)) return false;
      if (!filters.showPuts && isPut(pos)) return false;
      if (!filters.showLong && isLong(pos)) return false;
      if (!filters.showShort && isShort(pos)) return false;
      
      // P&L filters
      if (filters.onlyProfit && pos.unrealized_pnl <= 0) return false;
      if (filters.onlyLoss && pos.unrealized_pnl >= 0) return false;
      if (filters.minPnL && pos.unrealized_pnl < filters.minPnL) return false;
      if (filters.maxPnL && pos.unrealized_pnl > filters.maxPnL) return false;
      
      // Expiry filters
      if (filters.expiries.length > 0 && !filters.expiries.includes(getExpiry(pos))) return false;
      if (filters.maxDaysToExpiry && getDaysToExpiry(pos) > filters.maxDaysToExpiry) return false;
      
      // Moneyness filters
      if (filters.atm && !isATM(pos)) return false;
      if (filters.itm && !isITM(pos)) return false;
      if (filters.otm && !isOTM(pos)) return false;
      
      // Text search
      if (filters.searchText && !matchesSearch(pos, filters.searchText)) return false;
      
      return true;
    });
  }, [positions, filters]);
  
  return (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Typography variant="h6" gutterBottom>
        Filters ({filteredPositions.length}/{positions.length})
      </Typography>
      
      <Grid container spacing={2}>
        {/* Quick Filters */}
        <Grid item xs={12}>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <FilterChip 
              label="Calls"
              active={filters.showCalls}
              onChange={() => updateFilter('showCalls', !filters.showCalls)}
            />
            <FilterChip 
              label="Puts"
              active={filters.showPuts}
              onChange={() => updateFilter('showPuts', !filters.showPuts)}
            />
            <FilterChip 
              label="Long"
              active={filters.showLong}
              onChange={() => updateFilter('showLong', !filters.showLong)}
            />
            <FilterChip 
              label="Short"
              active={filters.showShort}
              onChange={() => updateFilter('showShort', !filters.showShort)}
            />
            <Divider orientation="vertical" flexItem />
            <FilterChip 
              label="Profit Only"
              active={filters.onlyProfit}
              onChange={() => updateFilter('onlyProfit', !filters.onlyProfit)}
              color="success"
            />
            <FilterChip 
              label="Loss Only"
              active={filters.onlyLoss}
              onChange={() => updateFilter('onlyLoss', !filters.onlyLoss)}
              color="error"
            />
          </Box>
        </Grid>
        
        {/* Search */}
        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            placeholder="Search symbol, strike..."
            value={filters.searchText}
            onChange={(e) => updateFilter('searchText', e.target.value)}
            InputProps={{
              startAdornment: <SearchIcon />
            }}
          />
        </Grid>
        
        {/* P&L Range */}
        <Grid item xs={12} md={6}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              label="Min P&L"
              type="number"
              value={filters.minPnL || ''}
              onChange={(e) => updateFilter('minPnL', e.target.value)}
              size="small"
            />
            <TextField
              label="Max P&L"
              type="number"
              value={filters.maxPnL || ''}
              onChange={(e) => updateFilter('maxPnL', e.target.value)}
              size="small"
            />
          </Box>
        </Grid>
        
        {/* Moneyness */}
        <Grid item xs={12}>
          <FormGroup row>
            <FormControlLabel
              control={<Checkbox checked={filters.atm} />}
              label="At-the-Money"
              onChange={(e) => updateFilter('atm', e.target.checked)}
            />
            <FormControlLabel
              control={<Checkbox checked={filters.itm} />}
              label="In-the-Money"
              onChange={(e) => updateFilter('itm', e.target.checked)}
            />
            <FormControlLabel
              control={<Checkbox checked={filters.otm} />}
              label="Out-of-the-Money"
              onChange={(e) => updateFilter('otm', e.target.checked)}
            />
          </FormGroup>
        </Grid>
        
        {/* Clear Filters */}
        <Grid item xs={12}>
          <Button 
            variant="outlined" 
            size="small"
            onClick={() => setFilters(DEFAULT_FILTERS)}
          >
            Clear All Filters
          </Button>
        </Grid>
      </Grid>
    </Paper>
  );
};
```

#### D. Quick Action Bar

```javascript
/**
 * NEW COMPONENT: webui/frontend/src/components/options/QuickActionBar.js
 * 
 * One-click access to common actions
 */

const QuickActionBar = ({ positions, onAction }) => {
  return (
    <Paper 
      sx={{ 
        p: 1.5, 
        mb: 2, 
        display: 'flex', 
        gap: 1.5,
        alignItems: 'center',
        bgcolor: 'background.default'
      }}
    >
      {/* Bulk Actions */}
      <Typography variant="overline" fontWeight={600}>
        Quick Actions:
      </Typography>
      
      <Button
        variant="outlined"
        size="small"
        startIcon={<CloseIcon />}
        onClick={() => onAction('close_all_profitable')}
        color="success"
      >
        Close All Profitable
      </Button>
      
      <Button
        variant="outlined"
        size="small"
        startIcon={<CloseIcon />}
        onClick={() => onAction('close_expiring_today')}
        color="warning"
      >
        Close Expiring Today
      </Button>
      
      <Button
        variant="outlined"
        size="small"
        startIcon={<WarningIcon />}
        onClick={() => onAction('set_stop_loss_all')}
      >
        Set Stop Loss (All)
      </Button>
      
      <Divider orientation="vertical" flexItem />
      
      {/* View Controls */}
      <ToggleButtonGroup size="small" exclusive>
        <ToggleButton value="cards">
          <ViewModuleIcon />
        </ToggleButton>
        <ToggleButton value="table">
          <ViewListIcon />
        </ToggleButton>
        <ToggleButton value="compact">
          <ViewCompactIcon />
        </ToggleButton>
      </ToggleButtonGroup>
      
      <Box sx={{ flex: 1 }} />
      
      {/* Export & Settings */}
      <Tooltip title="Export Positions">
        <IconButton size="small">
          <DownloadIcon />
        </IconButton>
      </Tooltip>
      
      <Tooltip title="Panel Settings">
        <IconButton size="small">
          <SettingsIcon />
        </IconButton>
      </Tooltip>
    </Paper>
  );
};
```

### 13.3 Futures Panel Enhancement

#### A. Unified Position Card (Options + Futures)

```javascript
/**
 * NEW COMPONENT: webui/frontend/src/components/futures/FuturesPositionCard.js
 * 
 * Consistent design with Options card but adapted for futures
 */

const FuturesPositionCard = ({ position, onClose, onAdjust }) => {
  return (
    <Paper 
      elevation={2}
      sx={{
        p: 2,
        mb: 1.5,
        borderRadius: 2,
        border: `2px solid ${position.side > 0 ? '#10b981' : '#ef4444'}`,
        transition: 'all 0.2s'
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        {/* Symbol & Direction */}
        <Box sx={{ flex: '0 0 180px' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chip 
              label={position.side > 0 ? 'LONG' : 'SHORT'}
              size="small"
              sx={{ 
                bgcolor: position.side > 0 ? '#10b981' : '#ef4444',
                color: 'white',
                fontWeight: 600
              }}
            />
            <Typography variant="h6" fontWeight={600}>
              {position.symbol}
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary">
            Perpetual
          </Typography>
        </Box>
        
        {/* Metrics */}
        <Box sx={{ flex: 1, display: 'flex', gap: 3 }}>
          <MetricDisplay 
            label="Size"
            value={Math.abs(position.size)}
            icon={<SizeIcon />}
          />
          <MetricDisplay 
            label="Entry"
            value={formatPrice(position.entry_price)}
          />
          <MetricDisplay 
            label="Mark"
            value={formatPrice(position.mark_price)}
            change={getPercentChange(position)}
          />
          <MetricDisplay 
            label="Liquidation"
            value={formatPrice(position.liquidation_price)}
            warning={isNearLiquidation(position)}
          />
        </Box>
        
        {/* P&L & Actions */}
        <Box sx={{ flex: '0 0 250px', display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box sx={{ textAlign: 'right', flex: 1 }}>
            <Typography 
              variant="h5" 
              fontWeight={700}
              color={position.unrealized_pnl > 0 ? 'success.main' : 'error.main'}
            >
              {formatPnL(position.unrealized_pnl)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              ROE: {formatPnLPercent(position.unrealized_pnl_percent)}%
            </Typography>
          </Box>
          
          {/* Quick Actions */}
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Tooltip title="Add to Position">
              <IconButton 
                size="small" 
                onClick={() => onAdjust(position, 'add')}
                color="success"
              >
                <AddIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Reduce Position">
              <IconButton 
                size="small" 
                onClick={() => onAdjust(position, 'reduce')}
                color="warning"
              >
                <RemoveIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Close Position">
              <IconButton 
                size="small" 
                onClick={() => onClose(position)}
                color="error"
              >
                <CloseIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      </Box>
    </Paper>
  );
};
```

#### B. Leverage & Risk Visualization

```javascript
/**
 * NEW COMPONENT: webui/frontend/src/components/futures/LeverageIndicator.js
 * 
 * Visual leverage and liquidation risk display
 */

const LeverageIndicator = ({ position }) => {
  const { leverage, liquidation_price, mark_price, side } = position;
  
  // Calculate distance to liquidation (% of price movement)
  const distanceToLiq = side > 0
    ? ((mark_price - liquidation_price) / mark_price) * 100
    : ((liquidation_price - mark_price) / mark_price) * 100;
  
  const riskLevel = 
    distanceToLiq < 5 ? 'critical' :
    distanceToLiq < 10 ? 'high' :
    distanceToLiq < 20 ? 'medium' : 'low';
  
  const riskColors = {
    critical: '#ef4444',
    high: '#f59e0b',
    medium: '#eab308',
    low: '#10b981'
  };
  
  return (
    <Box sx={{ p: 1.5, bgcolor: 'background.default', borderRadius: 1 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="caption" color="text.secondary">
          Leverage
        </Typography>
        <Typography variant="body2" fontWeight={600}>
          {leverage}x
        </Typography>
      </Box>
      
      {/* Liquidation Risk Bar */}
      <Box sx={{ mb: 0.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="caption" color="text.secondary">
            Distance to Liquidation
          </Typography>
          <Typography 
            variant="caption" 
            fontWeight={600}
            color={riskColors[riskLevel]}
          >
            {distanceToLiq.toFixed(2)}%
          </Typography>
        </Box>
        
        <LinearProgress 
          variant="determinate" 
          value={Math.min(distanceToLiq, 100)}
          sx={{
            height: 6,
            borderRadius: 3,
            bgcolor: 'rgba(0,0,0,0.1)',
            '& .MuiLinearProgress-bar': {
              bgcolor: riskColors[riskLevel]
            }
          }}
        />
      </Box>
      
      {/* Warning Messages */}
      {riskLevel === 'critical' && (
        <Alert severity="error" sx={{ mt: 1 }}>
          ⚠️ Critical: Position may be liquidated soon!
        </Alert>
      )}
      {riskLevel === 'high' && (
        <Alert severity="warning" sx={{ mt: 1 }}>
          Caution: Close to liquidation price
        </Alert>
      )}
    </Box>
  );
};
```

### 13.4 Combined Dashboard View

```javascript
/**
 * NEW COMPONENT: webui/frontend/src/components/trading/UnifiedTradingDashboard.js
 * 
 * Unified view of Options + Futures with portfolio-level metrics
 */

const UnifiedTradingDashboard = () => {
  const [activeTab, setActiveTab] = useState('all'); // 'all', 'options', 'futures'
  
  return (
    <Box>
      {/* Portfolio Summary Card */}
      <Paper sx={{ p: 3, mb: 3, bgcolor: 'primary.main', color: 'white' }}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={3}>
            <Typography variant="overline" sx={{ opacity: 0.8 }}>
              Total Portfolio Value
            </Typography>
            <Typography variant="h3" fontWeight={700}>
              $45,234.56
            </Typography>
          </Grid>
          
          <Grid item xs={12} md={3}>
            <Typography variant="overline" sx={{ opacity: 0.8 }}>
              Today's P&L
            </Typography>
            <Typography variant="h4" fontWeight={700} color="success.light">
              +$1,234.56 (+2.8%)
            </Typography>
          </Grid>
          
          <Grid item xs={12} md={3}>
            <Typography variant="overline" sx={{ opacity: 0.8 }}>
              Options P&L
            </Typography>
            <Typography variant="h4" fontWeight={700}>
              +$834.56
            </Typography>
            <Typography variant="caption">
              12 positions • 3 strategies
            </Typography>
          </Grid>
          
          <Grid item xs={12} md={3}>
            <Typography variant="overline" sx={{ opacity: 0.8 }}>
              Futures P&L
            </Typography>
            <Typography variant="h4" fontWeight={700}>
              +$400.00
            </Typography>
            <Typography variant="caption">
              2 positions
            </Typography>
          </Grid>
        </Grid>
        
        {/* Quick Stats */}
        <Grid container spacing={2} sx={{ mt: 2 }}>
          <Grid item>
            <Chip 
              label="Portfolio Delta: +0.45" 
              variant="outlined"
              sx={{ color: 'white', borderColor: 'white' }}
            />
          </Grid>
          <Grid item>
            <Chip 
              label="Portfolio Theta: -$45/day" 
              variant="outlined"
              sx={{ color: 'white', borderColor: 'white' }}
            />
          </Grid>
          <Grid item>
            <Chip 
              label="Margin Used: 45%" 
              variant="outlined"
              sx={{ color: 'white', borderColor: 'white' }}
            />
          </Grid>
          <Grid item>
            <Chip 
              label="3 Positions Expiring Today" 
              variant="outlined"
              sx={{ color: 'warning.light', borderColor: 'warning.light' }}
            />
          </Grid>
        </Grid>
      </Paper>
      
      {/* Tab Navigation */}
      <Tabs value={activeTab} onChange={(e, v) => setActiveTab(v)} sx={{ mb: 2 }}>
        <Tab label="All Positions" value="all" />
        <Tab label="Options Only" value="options" />
        <Tab label="Futures Only" value="futures" />
      </Tabs>
      
      {/* Position Display */}
      <Box>
        {(activeTab === 'all' || activeTab === 'options') && (
          <OptionsPositionList />
        )}
        
        {(activeTab === 'all' || activeTab === 'futures') && (
          <FuturesPositionList />
        )}
      </Box>
    </Box>
  );
};
```

### 13.5 Responsive Mobile Design

```javascript
/**
 * Mobile-Optimized Position Card
 */

const MobilePositionCard = ({ position }) => {
  return (
    <Paper sx={{ p: 2, mb: 1 }}>
      {/* Top Row: Symbol & P&L */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
        <Box>
          <Typography variant="h6" fontWeight={600}>
            {position.strike}
          </Typography>
          <Chip 
            label={position.option_type === 'call' ? 'CALL' : 'PUT'}
            size="small"
            sx={{ mt: 0.5 }}
          />
        </Box>
        <Box sx={{ textAlign: 'right' }}>
          <Typography 
            variant="h6" 
            fontWeight={700}
            color={position.unrealized_pnl > 0 ? 'success.main' : 'error.main'}
          >
            {formatPnL(position.unrealized_pnl)}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {formatPnLPercent(position.unrealized_pnl_percent)}%
          </Typography>
        </Box>
      </Box>
      
      {/* Details Grid */}
      <Grid container spacing={1}>
        <Grid item xs={6}>
          <Typography variant="caption" color="text.secondary">Size</Typography>
          <Typography variant="body2" fontWeight={600}>{position.size}</Typography>
        </Grid>
        <Grid item xs={6}>
          <Typography variant="caption" color="text.secondary">Entry</Typography>
          <Typography variant="body2" fontWeight={600}>{formatPrice(position.entry_price)}</Typography>
        </Grid>
        <Grid item xs={6}>
          <Typography variant="caption" color="text.secondary">Mark</Typography>
          <Typography variant="body2" fontWeight={600}>{formatPrice(position.mark_price)}</Typography>
        </Grid>
        <Grid item xs={6}>
          <Typography variant="caption" color="text.secondary">Expiry</Typography>
          <Typography variant="body2" fontWeight={600}>{position.days_to_expiry}d</Typography>
        </Grid>
      </Grid>
      
      {/* Actions */}
      <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
        <Button variant="outlined" size="small" fullWidth startIcon={<AddIcon />}>
          Add
        </Button>
        <Button variant="outlined" size="small" fullWidth color="error" startIcon={<CloseIcon />}>
          Close
        </Button>
      </Box>
    </Paper>
  );
};
```

### 13.6 Performance Enhancements

#### A. Virtual Scrolling for Large Lists

```javascript
import { FixedSizeList } from 'react-window';

const VirtualizedPositionList = ({ positions }) => {
  const Row = ({ index, style }) => {
    const position = positions[index];
    return (
      <div style={style}>
        <PositionCard position={position} />
      </div>
    );
  };
  
  return (
    <FixedSizeList
      height={600}
      itemCount={positions.length}
      itemSize={120}
      width="100%"
    >
      {Row}
    </FixedSizeList>
  );
};
```

#### B. Memoization & Optimization

```javascript
// Memoize expensive calculations
const PositionCard = React.memo(({ position }) => {
  // ... component implementation
}, (prevProps, nextProps) => {
  // Only re-render if these specific fields changed
  return (
    prevProps.position.unrealized_pnl === nextProps.position.unrealized_pnl &&
    prevProps.position.mark_price === nextProps.position.mark_price &&
    prevProps.position.size === nextProps.position.size
  );
});

// Debounce real-time updates
const useDebouncedPositions = (positions, delay = 500) => {
  const [debouncedPositions, setDebouncedPositions] = useState(positions);
  
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedPositions(positions);
    }, delay);
    
    return () => clearTimeout(timer);
  }, [positions, delay]);
  
  return debouncedPositions;
};
```

### 13.7 Implementation Priority

#### Phase 1: Core UI Improvements (Week 1-2)
- [ ] Replace table layout with card-based design
- [ ] Implement responsive mobile layout
- [ ] Add quick action bar
- [ ] Improve color scheme and typography

#### Phase 2: Smart Features (Week 3-4)
- [ ] Advanced filtering system
- [ ] Position grouping (expiry, strike, strategy)
- [ ] Bulk actions
- [ ] Column customization

#### Phase 3: Risk Visualization (Week 5-6)
- [ ] Leverage indicator for futures
- [ ] Greeks visualization in cards
- [ ] Mini payoff charts per position
- [ ] Risk alerts and warnings

#### Phase 4: Performance (Week 7-8)
- [ ] Virtual scrolling for large lists
- [ ] Memoization and optimization
- [ ] Web Workers for calculations
- [ ] Progressive loading

---

## Summary

This plan transforms the current basic payoff graph into an **industry-standard professional trading tool** through:

### ✅ Foundation
- Unified calculation engine (frontend + backend)
- Comprehensive Greeks suite (6 Greeks + portfolio-level)
- Industry-standard pricing models (Black-Scholes, Binomial Tree, Monte Carlo)

### ✅ Risk Analysis
- Probability of Profit (PoP)
- Expected value and VaR
- Stress testing and scenario analysis
- Risk/reward metrics

### ✅ Visualization
- Multiple time-horizon curves
- Probability density overlay
- Greeks dashboard
- Heatmap view
- 3D surface (optional)

### ✅ Professional Features
- Volatility smile visualization
- What-if simulator
- Scenario comparison
- Export functionality
- Portfolio-level analysis

### ✅ Quality
- 95%+ test coverage
- Performance optimization (< 100ms calculations)
- Comprehensive documentation
- Mobile-responsive design

**Timeline:** 10 weeks for full implementation  
**Result:** World-class options analysis tool for crypto derivatives

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Prioritize features** (MVP vs. nice-to-have)
3. **Assign resources** (developers, designers, QA)
4. **Start Phase 1** (Foundation) immediately
5. **Set up tracking** (GitHub project board, weekly reviews)

**Questions to Answer:**
- Which features are must-have for MVP?
- Do we need 3D visualization or is 2D sufficient?
- Should Monte Carlo be real-time or background job?
- What's the priority: accuracy or speed?
- Do we need mobile app or responsive web is enough?

---

**Document Version:** 1.0  
**Last Updated:** January 23, 2026  
**Author:** GitHub Copilot (Claude Sonnet 4.5)  
**Review Status:** Awaiting stakeholder review


---

## SOURCE FILE: PAYOFF_IMPROVEMENT_PLAN.md

# Options Payoff Diagram — Production-Grade Improvement Plan

**Date:** February 24, 2026  
**Author:** AI Copilot (post deep audit)  
**Scope:** OptionsPayoffDiagram.js (1,800 lines) + payoff_engine.py (594 lines)  
**Goal:** Fix incorrect blue "On Target Date" line, remove debug artifacts, make institutional grade  
**Pre-commit:** `451f93d10` (SSR branch)

---

## Problem Statement

The **blue "On Target Date" line** in the Payoff Graph is incorrect while the **green "On Expiry" line** is correct. Additionally, debug text is visible in production and the component needs robustness improvements.

---

## Root Cause Analysis

### BUG 1 (D12): Debug Text Visible in Production
- **Location:** `OptionsPayoffDiagram.js` line ~1468
- **Renders:** `Debug: 3 total alerts, 0 shown for expiry (2026-02-24).`
- **Fix:** Remove or gate behind `NODE_ENV === 'development'`

### BUG 2 (CRITICAL): Risk-Free Rate Mismatch — Root Cause of Wrong Blue Line
| Location | Risk-Free Rate |
|----------|---------------|
| Frontend `OptionsPayoffDiagram.js` line 191 | **`r = 0.05` (5%)** |
| Backend `payoff_engine.py` line 52 | **`r = 0.0` (0%)** |

**Impact:** The Black-Scholes formula uses `e^(-rT)` for discounting. With `r=0.05`:
- Call prices are inflated (higher `S·N(d1)`, lower `K·e^(-rT)·N(d2)`)
- Put prices are deflated
- `theoAtCurrentSpot ≠ markPrice`, creating a **baseline offset** that shifts the entire blue curve

**Why this is wrong:** For **crypto options** (BTC/ETH), the industry standard risk-free rate is **0%** — no carry cost, no dividends. Delta Exchange uses 0%. The 5% is a stock-market assumption.

### BUG 3: Blue Line Baseline Drift from IV Solver Inaccuracy
Even with the rate fixed, the IV solver (Newton-Raphson + bisection, lines 74-99) may converge to an IV where `theoAtCurrentSpot ≠ markPrice`. The projection formula:
```
targetPayoff = currentUnrealizedPnL + (theoAtThisPrice - theoAtCurrentSpot) * sign * size * 0.001
```
If `theoAtCurrentSpot ≠ markPrice`, there's a constant offset error on every point. The blue line won't pass through the known current P&L at spot.

**Fix:** Compute blue line directly as:
```
targetPayoff = (theoAtThisPrice - entryPrice) * sign * absSize * multiplier
```
This eliminates the intermediate `theoAtCurrentSpot` subtraction.

### BUG 4: ETH Contract Multiplier Hardcoded Wrong
Contract multiplier is hardcoded to `0.001` everywhere (lines 369, 399, 418). ETH positions use `0.01`.

**Impact:** ETH options P&L shown at **10x wrong** value.

---

## Current Architecture

```
OptionsPayoffDiagram.js (1,800 lines)
├── Black-Scholes model (normalCDF, normalPDF, bsPrice, impliedVol) — lines 1-99
├── parsedPositions useMemo — lines 168-280
├── chartData useMemo (payoff calculation) — lines 285-565
├── Alert fetching + state (7 useState hooks) — lines 150-165, 570-600
├── Zoom handlers — lines 610-736
├── Render: positions chips, metrics strip, chart, sliders, alerts — lines 770-1800
│
payoff_engine.py (594 lines) — backend, NOT used by frontend
├── Black-Scholes (duplicate of frontend)
├── Greeks calculation
├── Probability of Profit (PoP)
├── Price distribution
├── Strategy payoff API
```

---

## Implementation Phases

### Phase A: Critical Fixes (1-2 hours) — DO FIRST

| # | Fix | Lines | Risk |
|---|-----|-------|------|
| A1 | Change `riskFreeRate` from `0.05` → `0.0` | Line 191 | Low — corrects BS pricing |
| A2 | Simplify blue line formula to eliminate baseline drift | Lines 395-470 | Medium — changes projection math |
| A3 | Remove debug text (D12) | Line ~1468 | Zero — debug only |
| A4 | Detect asset from symbol, use correct multiplier (0.001 BTC, 0.01 ETH) | Lines 369, 399, 418, 476 | Low — data fix |

#### A1 Detail: Risk-Free Rate Fix
```js
// BEFORE (line 191):
const riskFreeRate = 0.05;

// AFTER:
const riskFreeRate = 0.0; // Crypto standard — 0% (no carry cost, matches Delta Exchange)
```

#### A2 Detail: Blue Line Formula Fix
```js
// BEFORE (current approach — drift-prone):
// 1. Calculate currentUnrealizedPnL from market data
// 2. Calculate theoAtCurrentSpot via BS
// 3. Calculate theoAtThisPrice via BS
// 4. projectedChange = (theoAtThisPrice - theoAtCurrentSpot) * sign * size * mult
// 5. targetPayoff = currentUnrealizedPnL + projectedChange
// Problem: if theoAtCurrentSpot ≠ markPrice, there's a constant offset

// AFTER (direct approach — no drift):
// For each position at each price point:
// theoAtThisPrice = BS(price, strike, remainingYears, r, iv, type)
// targetPayoff += (theoAtThisPrice - entryPrice) * sign * absSize * multiplier
// This computes the theoretical P&L directly — no intermediate subtraction
```

#### A3 Detail: Debug Text Removal
```js
// REMOVE this line entirely (or wrap in dev check):
<Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
  Debug: {activeAlerts.length} total alerts, {filteredAlerts.length} shown for expiry ({currentExpiryStr || 'all'}).
</Typography>
```

#### A4 Detail: Contract Multiplier Detection
```js
// Add helper at top of component:
const getMultiplier = (symbol) => {
  if (!symbol) return 0.001;
  return symbol.toUpperCase().includes('ETH') ? 0.01 : 0.001;
};

// Replace all hardcoded 0.001 in payoff calculations with:
const multiplier = getMultiplier(pos.symbol);
```

---

### Phase B: Accuracy & Robustness (2-3 hours)

| # | Improvement | Detail |
|---|------------|--------|
| B1 | NaN/Infinity guards | Wrap BS output in `isFinite()` checks; fallback to intrinsic |
| B2 | Input validation | Validate positions before processing (non-zero size, valid strike, etc.) |
| B3 | IV solver convergence check | If solver doesn't converge (theoAtSpot vs markPrice > 5%), use exchange-provided IV from `pos.greeks.iv` if available |
| B4 | Add Probability of Profit (PoP) | Port `calculate_probability_of_profit` from backend or call API endpoint |
| B5 | Error boundary | Wrap chart in React error boundary so calculation failures don't crash the panel |

---

### Phase C: UX Polish (2-3 hours)

| # | Improvement | Detail |
|---|------------|--------|
| C1 | Remove duplicate content | Bottom stats row (line ~1624) duplicates top metrics strip; bottom positions chips (line ~1640) duplicates top positions box |
| C2 | Add Greeks to tooltip | Show portfolio Δ, θ at hovered price point |
| C3 | Multi-expiry indicator | Visual badge showing which positions expire first vs later |
| C4 | Replace emoji alert icon | SVG path instead of 🔔 in chart `<text>` element |
| C5 | Expiry line dual-color | Red below zero, green above (currently always green) |

---

### Phase D: Component Extraction (3-4 hours)

| # | New File | Contents | Lines |
|---|----------|----------|-------|
| D1 | `payoffCalculator.js` | BS model, IV solver, payoff loop — pure functions, testable | ~200 |
| D2 | `usePayoffData.js` | Hook wrapping parsedPositions + chartData useMemos | ~300 |
| D3 | `usePayoffAlerts.js` | Hook for alert state + CRUD (7 useState + fetch) | ~80 |
| D4 | `PayoffAlertDialog.js` | Alert creation dialog JSX | ~120 |
| D5 | `PayoffControls.js` | Target price slider + date slider | ~150 |

**Result:** OptionsPayoffDiagram.js ~1,800 → ~500 lines (thin render shell)

---

### Phase E: Advanced Features (Implemented)

| # | Feature | Detail | Status |
|---|---------|--------|--------|
| E1 | Multi-target-date overlay | "Today" (cyan dashed) + "Mid-Expiry" (indigo dotted) lines alongside main blue target line | ✅ Done |
| E2 | Weighted IV for probability | Notional-weighted average IV used for probability distribution (more accurate than simple average) | ✅ Done |
| E3 | Probability distribution overlay | Faint violet bell curve (lognormal density) behind payoff lines with hidden secondary Y-axis | ✅ Done |
| E4 | Backend-computed payoff | `POST /payoff/calculate` endpoint accepting arbitrary legs, calling `calculate_payoff_api()` | ✅ Done |
| E5 | Scenario comparison mode | "Compare" toggle snapshots current P&L as baseline, overlays dashed gray lines when positions change | ✅ Done |

**E1 Details:** Two additional time-horizon lines rendered via reusable `calcProjectedPayoff` helper:
- **Today line** (cyan `#06b6d4`, dashed) — P&L if price moved to each level right now
- **Mid-expiry line** (indigo `#818cf8`, dotted) — P&L at 50% of time to nearest expiry
- Both togglable via "Time Decay" switch in header

**E2 Details:** `calculateWeightedIV()` in payoffCalculator.js weights IV by notional (|size| × strike × multiplier), then feeds into lognormal distribution. More accurate than simple average for mixed-size portfolios.

**E3 Details:** `createPriceDistribution()` returns a lognormal density function. Rendered as a faint `Area` on a hidden secondary Y-axis so it auto-scales without affecting payoff Y-domain. Togglable via "Probability" switch.

---

## Files Inventory

| Phase | File | Action |
|-------|------|--------|
| A | `OptionsPayoffDiagram.js` | Fix r=0, fix blue line formula, remove debug, fix multiplier |
| B | `OptionsPayoffDiagram.js` | Add guards, validation, error boundary |
| C | `OptionsPayoffDiagram.js` | Remove duplicates, enhance tooltip, dual-color line |
| D | **NEW** `payoffCalculator.js` | Extract pure math functions |
| D | **NEW** `usePayoffData.js` | Extract data hook |
| D | **NEW** `usePayoffAlerts.js` | Extract alert hook |
| E | `payoffCalculator.js` | Add `createPriceDistribution`, `calculateWeightedIV` |
| E | `OptionsPayoffDiagram.js` | Multi-date lines, probability overlay, toggle switches, scenario compare |
| E | **NEW** `PayoffControls.js` | Target price + date/time sliders |
| E | **NEW** `PayoffErrorBoundary.js` | React error boundary wrapping chart |
| E | `strategy_routes.py` | `POST /payoff/calculate` standalone endpoint |

---

## Testing Strategy

### After Phase A (Critical)
1. Open payoff diagram with existing BTC positions
2. Verify blue line passes through current market P&L at spot price
3. Verify green expiry line unchanged
4. Verify debug text gone
5. If ETH positions exist, verify correct P&L scale

### After Phase B (Robustness)
1. Test with deep OTM positions (IV solver edge case)
2. Test with expired positions (daysToExpiry = 0)
3. Test with closed positions (size = 0)
4. Verify no NaN/Infinity in chart

### After Phase C (UX)
1. Visual check — no duplicate information
2. Hover tooltip shows Greeks
3. Alert icons render correctly

### Smoke Test
```bash
cd webui/frontend && npm run build 2>&1 | tail -5
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Blue line formula change produces wrong values | Compare old vs new at 5 price points before committing |
| IV solver calibration breaks for edge cases | Add fallback to exchange-provided IV |
| ETH multiplier change surprises users | P&L values were already wrong — this fixes them |
| Component extraction breaks rendering | Extract one at a time, test after each |

---

## Approval

- [x] Phase A approved — critical fixes ✅
- [x] Phase B approved — robustness ✅
- [x] Phase C approved — UX polish ✅
- [x] Phase D approved — extraction ✅
- [x] Phase E — E1/E2/E3/E4/E5 all implemented ✅

**All phases A–E 100% complete. No remaining items.**


---

## SOURCE FILE: CONFIG_PANEL_VISUAL_COMPARISON.md

# Configuration Panel - Visual Comparison

## BEFORE (Old Accordion Design)
```
╔═══════════════════════════════════════════════════════════════╗
║  ⚙️  Configuration                    [Reset]  [Save Config]  ║
╠═══════════════════════════════════════════════════════════════╣
║                                                                ║
║  ▼ Grid Parameters                           [8 settings]  ▼  ║
║  ├─────────────────────────────────────────────────────────┤  ║
║  │ GRIDBOT_SYMBOL:     [BTCUSDT              ]             │  ║
║  │ GRIDBOT_REF:        [110000               ]             │  ║
║  │ GRIDBOT_STEP:       [1000                 ]             │  ║
║  │ (5 more fields...)                                      │  ║
║  └─────────────────────────────────────────────────────────┘  ║
║                                                                ║
║  ▶ Smart Gap Fill                            [3 settings]  ▶  ║ ← Collapsed
║  ▶ Risk Management                           [4 settings]  ▶  ║ ← Collapsed
║  ▶ Execution Safety                          [2 settings]  ▶  ║ ← Collapsed
║  ▶ Telegram Notifications                    [2 settings]  ▶  ║ ← Collapsed
║  (8 more collapsed sections...)                               ║
║                                                                ║
╚═══════════════════════════════════════════════════════════════╝

Problems:
❌ Must click each section to see settings
❌ Excessive vertical space wasted
❌ Hard to see what's changed
❌ Switches take full width
❌ No visual hierarchy
```

## AFTER (New Card Design)
```
╔═══════════════════════════════════════════════════════════════╗
║  ⚙️  GridBot Configuration               [Reset]  [Save]      ║
║  Edit, validate, and manage bot parameters                    ║
╠═══════════════════════════════════════════════════════════════╣
║                                                                ║
║  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  ║
║  ┃ 📊 Grid Geometry                        [8 settings] ━┃  ║ ← Green border
║  ┃─────────────────────────────────────────────────────────┃  ║
║  ┃ Symbol          Ref Price       Step Size              ┃  ║
║  ┃ [BTCUSDT  📋]   [110000   📋]   [1000     📋]          ┃  ║
║  ┃                                                         ┃  ║
║  ┃ Lot Size        Lower Bound     Upper Bound            ┃  ║
║  ┃ [3        📋]   [105000   📋]   [120000   📋]          ┃  ║
║  ┃                                                         ┃  ║
║  ┃ Max Open        Heartbeat (sec)                        ┃  ║
║  ┃ [15       📋]   [15       📋]                          ┃  ║
║  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛  ║
║                                                                ║
║  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  ║
║  ┃ 🔧 Smart Gap Fill                       [3 settings] ━┃  ║ ← Blue border
║  ┃─────────────────────────────────────────────────────────┃  ║
║  ┃ Enable Gap Fill             [  ON  ] ← Click to toggle ┃  ║
║  ┃                                                         ┃  ║
║  ┃ Order Type                  Max Levels                 ┃  ║
║  ┃ [auto      📋]              [5         📋]             ┃  ║
║  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛  ║
║                                                                ║
║  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  ║
║  ┃ ⚙️  Grid Behavior                       [4 settings] ━┃  ║ ← Orange border
║  ┃─────────────────────────────────────────────────────────┃  ║
║  ┃ Strict Grid      [ OFF ]   Dynamic Tick    [  ON  ]    ┃  ║
║  ┃                                                         ┃  ║
║  ┃ Snap Mode                   Tick Size                  ┃  ║
║  ┃ [nearest   📋]              [0.01      📋]             ┃  ║
║  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛  ║
║                                                                ║
║  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  ║
║  ┃ 🔒 Execution Safety (CRITICAL)          [2 settings] ━┃  ║ ← RED border
║  ┃─────────────────────────────────────────────────────────┃  ║
║  ┃ ⚠️  CRITICAL SETTINGS - AFFECTS REAL MONEY TRADING     ┃  ║
║  ┃                                                         ┃  ║
║  ┃ I Understand Live Trading                   [ OFF ]    ┃  ║
║  ┃ Execute Real Orders                         [ OFF ]    ┃  ║
║  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛  ║
║                                                                ║
║  (9 more card sections - all visible, no scrolling needed)    ║
║                                                                ║
║  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  ║
║  ┃ ⚠️  CRITICAL SAFETY NOTICE                              ┃  ║
║  ┃ • Configuration changes affect live trading immediately ┃  ║
║  ┃ • Verify all settings before saving                     ┃  ║
║  ┃ • Stop bot before modifying critical settings           ┃  ║
║  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛  ║
╚═══════════════════════════════════════════════════════════════╝

Improvements:
✅ All settings visible at once
✅ Compact 3-column grid layout
✅ Color-coded sections with icons
✅ Toggle chips instead of switches
✅ Copy buttons (📋) on every field
✅ Visual hierarchy with borders
✅ Changed fields highlighted in orange
✅ Critical sections in red
```

## Key Visual Changes

### Toggle Fields
```
OLD:                              NEW:
┌─────────────────────────┐      ┌─────────────────────────┐
│ Smart Gap Fill   [⚪─]  │  →   │ Smart Gap Fill  [ ON ]  │
└─────────────────────────┘      └─────────────────────────┘
    Full-width switch               Compact chip badge
```

### Input Fields
```
OLD:                              NEW:
┌─────────────────────────┐      ┌─────────────────────────┐
│ GRIDBOT_SYMBOL          │      │ Symbol          📋      │
│ [BTCUSDT           ]    │  →   │ [BTCUSDT  📋]          │
└─────────────────────────┘      └─────────────────────────┘
    Verbose label                   Clean label + copy
```

### Section Headers
```
OLD:                              NEW:
┌─────────────────────────┐      ┏━━━━━━━━━━━━━━━━━━━━━━┓
│ ▼ Grid Parameters    ▼  │      ┃ 📊 Grid Geometry      ┃
│    [8 settings]         │  →   ┃    [8 settings] ━     ┃
└─────────────────────────┘      ┗━━━━━━━━━━━━━━━━━━━━━━┛
    Accordion (collapsible)         Card (always visible)
    Gray background                 Color-coded border
```

## Layout Density Comparison

### OLD (Accordion Layout)
```
Section 1: ▼ Expanded    (300px height)
  └─ 8 fields in 3 columns

Section 2: ▶ Collapsed   (50px height)
Section 3: ▶ Collapsed   (50px height)
Section 4: ▶ Collapsed   (50px height)
...
Section 13: ▶ Collapsed  (50px height)

Total visible height: ~900px
Total with all expanded: ~3000px
```

### NEW (Card Layout)
```
Card 1: Grid Geometry    (180px height)
  └─ 8 fields in 3 columns

Card 2: Smart Gap Fill   (120px height)
  └─ 3 fields in 3 columns

Card 3: Grid Behavior    (120px height)
  └─ 4 fields in 3 columns

Card 4: Execution Safety (140px height)
  └─ 2 critical toggles

...
Card 13: Heartbeat       (200px height)

Total height: ~2200px (all visible)
Scrolling reduced: 25%
```

## Color Legend

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Section              │ Color    │ Border     ┃
┣━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━╋━━━━━━━━━━━┫
┃ Grid Geometry        │ 🟢 Green │ #4CAF50   ┃
┃ Smart Gap Fill       │ 🔵 Blue  │ #2196F3   ┃
┃ Grid Behavior        │ 🟠 Orange│ #FF9800   ┃
┃ Start Behavior       │ 🟣 Purple│ #9C27B0   ┃
┃ Order & Execution    │ 🔷 Cyan  │ #00BCD4   ┃
┃ Timing & Retries     │ 🔴 Orange│ #FF5722   ┃
┃ Health & Monitoring  │ 🟢 Lt Grn│ #8BC34A   ┃
┃ Emergency Limits     │ 🔴 Red   │ #F44336   ┃
┃ Execution Safety     │ 🔴 D.Red │ #D32F2F   ┃ ← CRITICAL
┃ Loss Limits          │ 🔴 Crimson│#C62828   ┃
┃ Margin & Liquidation │ 🟠 Dp Org│ #FF6F00   ┃
┃ Telegram             │ 🔵 Tg Blu│ #0088CC   ┃
┃ Heartbeat            │ 🔴 Pink  │ #E91E63   ┃
┗━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━┻━━━━━━━━━━━┛
```

## Interactive Features

### Copy Button Interaction
```
1. Initial State:        2. Hover:            3. Clicked:
┌─────────────┐         ┌─────────────┐      ┌─────────────┐
│ [Value  📋] │    →    │ [Value  📋] │  →   │ [Value  ✓ ] │
└─────────────┘         └─────────────┘      └─────────────┘
   Gray icon             Highlight             Green check
                         Tooltip:              "Copied!"
                         "Copy value"          (2 seconds)
```

### Toggle Chip Interaction
```
1. OFF State:           2. Hover:            3. Click → ON:
┌───────────┐          ┌───────────┐         ┌───────────┐
│  [ OFF ]  │    →     │  [ OFF ]  │    →    │  [ ON ]   │
└───────────┘          └───────────┘         └───────────┘
  Gray bg               Lighter bg            Green bg
  Gray text             White text            White text
```

### Change Detection
```
Original Field:         Modified Field:
┌─────────────┐         ┌─────────────┐
│ [110000  📋]│    →    │ [115000  📋]│
└─────────────┘         └─────────────┘
  White bg                Orange tint bg
  Normal border           Orange border
```

## Space Efficiency

### Grid Layout (Compact Sections)
```
╔═══════════════════════════════════════════╗
║ [Field 1]     [Field 2]     [Field 3]    ║  ← 3 columns
║ [Field 4]     [Field 5]     [Field 6]    ║
║ [Field 7]     [Field 8]                  ║
╚═══════════════════════════════════════════╝

vs. Old (2 columns):
╔═══════════════════════════════════════════╗
║ [Field 1]                [Field 2]       ║  ← 2 columns
║ [Field 3]                [Field 4]       ║
║ [Field 5]                [Field 6]       ║
║ [Field 7]                [Field 8]       ║
╚═══════════════════════════════════════════╝

Height savings: 33% for compact sections
```

---

**Visual Impact:** 🎨 Modern, clean, professional  
**UX Impact:** ⚡ Faster, smoother, more intuitive  
**Space Impact:** 📏 25% less scrolling required


---

## SOURCE FILE: tasks/BREAKEVEN_GAMMA_VISUAL_PLAN.md

# Breakeven Engine + Gamma Detector — WebUI Visualization Upgrade Plan

**Status:** ✅ COMPLETED — 2026-03-15
**Priority:** P1 (critical gap: gamma settings inaccessible from UI)
**Estimated total effort:** ~7.75 hours
**Files touched:** 9 (4 modify, 5 new)
**Phases:** 9 total (1, 2, 3, 4, 5, 6, 6.5, 7, 8)
**New dependencies:** None — all uses Recharts 2.9.0 (already installed) + MUI + SVG

> **Implementation complete.** All 9 phases delivered in a single session. 436 sealed tests pass (0 regressions). Frontend build successful, all bundle sizes within budget. One backend restart required to activate the `/pnl-curve` endpoint (deferred — session `mmm16mar26-1` was RUNNING at time of implementation).

---

## Section 1: Executive Summary

The MMM algorithm's Breakeven Engine and Gamma Detector are fully implemented in the backend and wired into the monitor heartbeat cycle. However, the WebUI visualization is incomplete in several critical ways: gamma detector parameters cannot be configured from the settings dialog, there is no P&L landscape chart showing where the portfolio goes underwater, and the two panels have no unified view showing their concentric-ring relationship.

This plan delivers 8 implementation phases that transform the existing minimal panels into a production-quality risk visualization suite. The crown jewel is a live P&L curve chart (`MMMRiskProfileChart.js`) that answers the operator question "how bad could it get if BTC moves X%?" in one glance. Secondary deliverables include a settings dialog fix (30 min, zero risk), a combined zone widget, and a distance history timeline.

All backend computation already exists. The plan does not re-implement any backend logic — only adds one API endpoint (Phase 2) and builds the frontend visualization layer on top of existing data.

---

## Section 2: Current State Audit

### Backend — Fully Implemented

| Component | File | Status |
|---|---|---|
| BreakevenEngine class + all methods | `mmm_breakeven_engine.py` | DONE |
| GammaDetector class + all methods | `mmm_gamma_detector.py` | DONE |
| Monitor Step 5.7 (breakeven wired) | `mmm_monitor.py` | DONE |
| Monitor Step 5.8 (gamma wired) | `mmm_monitor.py` | DONE |
| Cache invalidation — 8 pairs | `mmm_monitor.py:3318/19, 3909/10, 4078/79, 4185/86, 4612/13, 4803/04, 4938/39` + `mmm_api.py:3458/59` | DONE |
| `emit_heartbeat` breakeven_data + gamma_data kwargs | `mmm_websocket.py` | DONE |
| `emit_breakeven()` + `emit_gamma()` functions | `mmm_websocket.py` | DONE |
| DEFAULT_PARAMS — 7 gamma params + 8 breakeven params | `mmm_state.py` | DONE |
| HOT_RELOAD_PARAMS configured | `mmm_state.py` | DONE |
| PARAM_RULES — 7 gamma entries | `mmm_config.py` | DONE |
| PARAM_RULES — 8 breakeven entries | `mmm_config.py` | DONE |
| ACTIVITY_TYPES — gamma + breakeven types | `mmm_activity.py` | DONE |
| `/session/<id>/breakeven` endpoint | `mmm_api.py` | DONE |
| `/session/<id>/gamma` endpoint | `mmm_api.py` | DONE |
| `_compute_pnl_at_spot()` method | `mmm_breakeven_engine.py` | DONE |

### Backend — Gap

| Component | File | Status |
|---|---|---|
| `/session/<id>/pnl-curve` endpoint | `mmm_api.py` | **MISSING — Phase 2** |

> Note: `gamma_scan_steps` should be verified at `mmm_config.py` line ~201. It is listed in DEFAULT_PARAMS (`mmm_state.py`) but confirm PARAM_RULES entry exists before Phase 1.

### Frontend — Partially Implemented

| Component | File | Status |
|---|---|---|
| MMMBreakevenPanel — collapsible panel, horizontal band bar | `MMMBreakevenPanel.js` | EXISTS but minimal |
| MMMGammaPanel — collapsible panel, distance text | `MMMGammaPanel.js` | EXISTS but minimal |
| Both panels imported + rendered | `MMMDashboard.js:2130-2141` | DONE |
| `breakevenEngine` param group in settings | `MMMSettingsDialog.js` | DONE |

### Frontend — Gaps

| Component | File | Status |
|---|---|---|
| `gammaDetector` param group in settings | `MMMSettingsDialog.js` | **MISSING — Phase 1 (P0)** |
| P&L landscape chart | `MMMRiskProfileChart.js` | **MISSING — Phase 3** |
| Scaled band bar with gamma markers | `MMMBreakevenPanel.js` | **MISSING — Phase 4** |
| Proximity meter in gamma panel | `MMMGammaPanel.js` | **MISSING — Phase 5** |
| Combined zone widget (concentric rings) | `MMMCombinedZoneWidget.js` | **MISSING — Phase 6** |
| Distance history timeline | `MMMDistanceHistoryChart.js` | **MISSING — Phase 7** |
| Risk tab in dashboard | `MMMDashboard.js` | **MISSING — Phase 8** |

---

## Section 3: ATM Shield Integration Context

### Three-Layer Defense Model

The MMM algorithm implements three defensive layers that fire in sequence as BTC moves toward a strike:

```
Layer 1 — Gamma Detector (earliest warning)
  Fires when: spot within gamma_warning_distance_pct (default 3%) of nearest strike
  Action: observation-only signal, qualitative zone change
  Visual: amber on gamma panel

Layer 2 — Breakeven Engine (lot multiplier escalation)
  Fires when: spot within breakeven_warning_pct (default 2%) of breakeven line
  Action: breakeven_mult increases (1.0x → 3.0x), more lots sold on next adjustment
  Visual: amber → red on breakeven panel, multiplier chip changes

Layer 3 — ATM Shield (position retreat)
  Fires when: spot reaches ~0.5% from strike (shield_otm_threshold)
  Action: close threatened leg, reopen at new OTM strike
  Visual: shield event marker on timeline chart
```

### Shield v5 Interaction Matrix

| Tier | Shield Active? | Breakeven/Gamma Effect |
|---|---|---|
| T1/T2 | Yes — full shield | Normal: both BE and gamma react |
| T3/T4 | Partial — BLOCK_CE or BLOCK_PE only (not BLOCK_ALL) | Shield fires on one side only |
| BLOCK_ALL regime | Shield blocked | BE/gamma still compute but no leg can be sold |

### Visual Cues After Shield Fires

When a shield fires (position closed + retreat to new OTM strike), the following should be immediately visible on the charts:

1. **P&L Curve (Phase 3)**: The curve reshapes — the loss slope on the retreated side flattens because the new strike has more extrinsic value. The breakeven line moves farther from spot (band widens).

2. **Distance History (Phase 7)**: A vertical event marker labeled "Shield↑" or "Shield↓" appears at the exact timestamp. After the marker, the distance line jumps upward (safer).

3. **Combined Zone Widget (Phase 6)**: Gamma boundary marker shifts to new strike location, expanding the safe green zone.

4. **Breakeven Band (Phase 4)**: Lower or upper BE marker moves outward — the colored warning bands retract from spot.

The key insight for operators: shield fires appear as a **visible improvement** on every chart simultaneously. This validates the shield is working.

---

## Section 4: MMM Algo Benefit Analysis

### 4.1 Early Warning Pipeline — Timing Analysis

At typical BTC volatility (30% annualized IV), BTC moves approximately $300–$600/min during active sessions. Using $450/min as a baseline:

| Event | Distance from Strike | Time Before Strike | Distance from Breakeven |
|---|---|---|---|
| Gamma WARNING fires | 3.0% (~$2,700 on $90k BTC) | ~6 min | BE still safe (~5%) |
| Gamma DANGER fires | 1.5% (~$1,350) | ~3 min | BE still safe (~3.5%) |
| Breakeven WARNING fires | 2.0% from BE (~$1,800) | ~4 min | — |
| Breakeven DANGER fires | 1.0% from BE (~$900) | ~2 min | — |
| Breakeven CRITICAL fires | 0.5% from BE (~$450) | ~1 min | — |
| ATM Shield fires | ~0.5% from strike (~$450) | ~1 min | — |

**Key finding**: Gamma DANGER (1.5% from strike) fires approximately 90 seconds before Breakeven WARNING (2% from breakeven), assuming a typical strangle where strikes are ~3-4% OTM. This is the advance warning buffer that allows the algorithm to pre-position.

**Without gamma**: The algorithm's first quantitative escalation signal is Breakeven WARNING at T-4min.
**With gamma**: The algorithm receives a qualitative zone signal at T-6min and DANGER at T-3min, giving ~2 extra minutes of context before lots are committed.

### 4.2 Multiplier Cascade Mechanics

The combined lot multiplier is computed as:

```
final_lots = ceil(base_lots × gamma_mult × breakeven_mult × trend_mult)
             capped at: base_lots × max_combined_lot_multiplier (default 3.0x)
```

Example scenario at Breakeven DANGER zone (1.1% from BE):

| Factor | Value | Source |
|---|---|---|
| base_lots | 5 | session config |
| gamma_mult | 1.3x | T3-T2 aggressor premium logic |
| breakeven_mult | 1.6x | DANGER zone ramp (1.0x at warning → 3.0x at critical) |
| trend_boost | 1.0x | neutral trend |
| Raw result | ceil(5 × 1.3 × 1.6 × 1.0) = ceil(10.4) = 11 lots | — |
| Combined ceiling | 5 × 3.0 = 15 lots max | max_combined_lot_multiplier |
| Final | **11 lots** (ceiling not hit) | — |

At CRITICAL zone (0.4% from BE):

| Factor | Value |
|---|---|
| breakeven_mult | 3.0x (maximum) |
| Raw result | ceil(5 × 1.3 × 3.0) = ceil(19.5) = 20 lots |
| Combined ceiling | 5 × 3.0 = 15 lots |
| Final | **15 lots** (ceiling applied) |

The ceiling prevents runaway lot escalation in extreme scenarios while still ensuring aggressive defense at critical distances.

### 4.3 Phase 9: gamma_severity_multiplier_enabled

Currently `gamma_severity_multiplier_enabled` defaults to `false` and is NOT hot-reloadable (requires restart). This is intentional — it gates Phase 9 where gamma severity scores directly modulate lot multipliers.

When enabled (future):
- `gamma_severity_lower` / `gamma_severity_upper` (negative float, more negative = worse) provide per-side severity
- Severity multiplier will give asymmetric lot boosting: if lower gamma is worse than upper, sell more PE puts
- This directional intelligence complements the existing trend_boost

**Current value**: Even with `gamma_severity_multiplier_enabled=false`, the severity scores are computed and visible in the UI. Operators can use them for manual judgment before Phase 9 automation is trusted.

### 4.4 P&L Curve Business Value

The P&L curve answers the most critical operator question — "if BTC moves X%, how much do I lose?" — without requiring mental interpolation from premium levels.

Without the chart: operator must mentally combine multiple positions' deltas, gammas, and time decay into a scenario estimate. Error rate is high. Response time is slow.

With the chart: the visual slope of the curve immediately shows where loss acceleration begins (gamma kinks), where the portfolio crosses into loss (breakeven lines), and how much total loss is possible at any given spot.

The chart also provides **post-hoc validation**: after a session closes, the operator can compare the actual P&L path against the theoretical curve to assess whether the breakeven estimates were accurate.

### 4.5 Combined Ceiling Protection

The `max_combined_lot_multiplier` (default 3.0x) prevents cascading lot escalation in compound-risk scenarios:

- Gamma DANGER fires → gamma_mult = 1.2x
- Breakeven DANGER fires simultaneously → breakeven_mult = 1.6x
- Trend strong → trend_boost = 1.5x
- Raw: 1.2 × 1.6 × 1.5 = 2.88x — under ceiling
- If all three hit maximum simultaneously: 1.3 × 3.0 × 2.0 = 7.8x — ceiling cuts to 3.0x

The ceiling is the capital protection backstop that prevents the algorithm from selling more contracts than the account can safely hold.

---

## Section 5: Gap Analysis (Prioritized)

| # | Gap | Impact | Effort | Phase |
|---|---|---|---|---|
| 1 | Gamma detector settings not configurable from UI | **Critical** — users cannot tune gamma thresholds | 30 min | Phase 1 |
| 2 | No P&L curve API endpoint | **High** — blocks the most valuable visualization | 45 min | Phase 2 |
| 3 | No P&L landscape chart | **High** — no visual answer to "how bad if X% move?" | 90 min | Phase 3 |
| 4 | Breakeven band bar not proportionally scaled | **High** — misleading: 10% band looks same as 1% band | 60 min | Phase 4 |
| 5 | No gamma markers on breakeven bar | **High** — concentric ring relationship is invisible | (part of Phase 4) | Phase 4 |
| 6 | No combined zone widget | **Medium** — must switch between two panels to see risk | 60 min | Phase 6 |
| 7 | No gamma proximity meter | **Medium** — severity scores not visualized | 45 min | Phase 5 |
| 8 | No distance history timeline | **Medium** — cannot see how risk evolved during session | 75 min | Phase 7 |
| 9 | No Risk tab in dashboard | **Lower** — existing tabs are overloaded | 30 min | Phase 8 |

---

## Section 6: Implementation Phases

### Phase 1: Settings Dialog — Gamma Detector Group

**Priority:** P0 Critical
**Effort:** 30 min
**File:** `webui/frontend/src/components/mmm/MMMSettingsDialog.js`
**Risk:** Zero — pure UI addition, no backend change

**Problem:** `gammaDetector` param group is completely absent from `MMMSettingsDialog.js`. The 7 gamma parameters exist in backend state and PARAM_RULES but there is no way to change them from the UI. `gamma_detector_enabled` cannot even be toggled without a raw API call.

**Pre-check:** Before editing, verify `gamma_scan_steps` is present in `mmm_config.py` PARAM_RULES (expected ~line 201). If missing, add it there first.

**Implementation:**

Locate the `PARAM_GROUPS` object in `MMMSettingsDialog.js` (where `breakevenEngine` group is defined). Add a `gammaDetector` entry immediately after `breakevenEngine`:

```javascript
gammaDetector: {
  title: 'Gamma Detector',
  color: '#ff6f00',  // deep amber — distinct from breakeven blue (#1565c0)
  blurb: 'Portfolio curvature scanning — detects the option strikes where P&L loss rate begins to accelerate. Fires ~90 seconds before Breakeven WARNING at typical BTC velocity. Currently observation-only; Phase 9 will use severity scores for directional lot weighting.',
  subgroups: [
    {
      header: 'Enable',
      params: ['gamma_detector_enabled'],
    },
    {
      header: 'Zone Thresholds (% distance from spot to nearest gamma boundary)',
      params: ['gamma_warning_distance_pct', 'gamma_danger_distance_pct'],
    },
    {
      header: 'Scan Parameters',
      params: ['gamma_step_pct', 'gamma_scan_steps', 'gamma_detect_epsilon'],
    },
    {
      header: 'Phase 9 Gate',
      params: ['gamma_severity_multiplier_enabled'],
    },
  ],
},
```

**Tooltip strings to add** (add to the tooltips/descriptions map):

| Param | Tooltip Text |
|---|---|
| `gamma_detector_enabled` | Master switch for gamma boundary detection. When disabled, no gamma data is computed or emitted. Start with this OFF for first 3 sessions, then enable observation mode. |
| `gamma_warning_distance_pct` | Spot must be within this % of the nearest option strike to enter gamma WARNING zone. Default 3.0%. At $90k BTC, this is $2,700 from the nearest short strike. Fires ~6 min before ATM shield at typical velocity. |
| `gamma_danger_distance_pct` | Spot must be within this % of the nearest strike for gamma DANGER zone. Default 1.5%. Fires ~3 min before ATM shield. Breakeven is still likely SAFE at this point — this is the advance warning window. |
| `gamma_step_pct` | Step size for the second-difference (curvature) scan. Default 0.5%. Smaller = finer detection of gamma kinks, but more CPU per heartbeat. Do not set below 0.2%. |
| `gamma_scan_steps` | Number of steps to scan outward from spot in each direction. Default 40. At gamma_step_pct=0.5%, this scans 20% outward. Increase only if strikes are unusually far OTM. |
| `gamma_detect_epsilon` | Minimum second-difference magnitude to count as a gamma kink. Default 0.3. Lower = more sensitive (may flag noise). Higher = only strong curvature changes detected. |
| `gamma_severity_multiplier_enabled` | Phase 9 gate — when enabled, gamma severity scores directly modulate lot multipliers directionally (more PE lots when lower gamma is worse). NOT hot-reloadable. Requires backend restart. Do not enable until 10+ sessions of observation data collected. |

**Warning chip for `gamma_severity_multiplier_enabled`:** This param requires a restart. Render a warning chip alongside it — use the same pattern already used for non-hot breakeven params (look for existing restart-required UI pattern in the breakevenEngine subgroup). The chip should say "Requires Backend Restart" in red/amber.

---

### Phase 2: Backend P&L Curve API Endpoint

**Priority:** P1 High
**Effort:** 45 min
**File:** `webui/backend/routes/mmm/mmm_api.py`
**Risk:** Low — additive endpoint, no change to existing logic

**New endpoint:** `GET /api/mmm/session/<session_id>/pnl-curve`

**Query parameters:**

| Param | Type | Default | Max | Description |
|---|---|---|---|---|
| `n_points` | int | 100 | 200 | Number of price sample points in the curve |
| `range_pct` | float | 15.0 | 50.0 | Scan range as % of current spot (centered on spot) |

**Implementation:**

```python
@mmm_bp.route('/session/<session_id>/pnl-curve', methods=['GET'])
def get_pnl_curve(session_id: str):
    session = _get_session(session_id)
    if not session:
        return jsonify({'success': False, 'error': 'Session not found'}), 404

    n_points = min(int(request.args.get('n_points', 100)), 200)
    range_pct = min(float(request.args.get('range_pct', 15.0)), 50.0)

    engine = get_breakeven_engine()
    positions = engine._collect_open_positions(session)
    if not positions:
        return jsonify({
            'success': True,
            'spot': session.get('spot_price', 0),
            'points': [],
            'message': 'No positions to compute curve',
            'breakeven': None,
            'gamma': None,
            'positions_count': 0,
            'computed_at': datetime.utcnow().isoformat(),
        })

    spot = session.get('spot_price', 0)
    if not spot:
        return jsonify({'success': False, 'error': 'No spot price available'}), 422

    low = spot * (1 - range_pct / 100)
    high = spot * (1 + range_pct / 100)
    step = (high - low) / (n_points - 1)

    # Fetch current breakeven and gamma results (from cache or compute)
    be_result = engine.compute(session)  # returns BreakevenResult dict
    gamma_result = get_gamma_detector().compute(session)  # returns GammaResult dict

    # Build zone lookup from breakeven and gamma boundaries
    lower_be = be_result.get('lower_breakeven', 0)
    upper_be = be_result.get('upper_breakeven', float('inf'))
    lower_gamma = gamma_result.get('lower_gamma_boundary', 0)
    upper_gamma = gamma_result.get('upper_gamma_boundary', float('inf'))

    critical_pct = session.get('breakeven_critical_pct', 0.5) / 100
    danger_pct = session.get('breakeven_danger_pct', 1.0) / 100
    warning_pct = session.get('breakeven_warning_pct', 2.0) / 100

    def classify_zone(test_spot: float) -> str:
        if lower_gamma and test_spot < lower_gamma:
            return 'lower_gamma'
        if upper_gamma and test_spot > upper_gamma:
            return 'upper_gamma'
        if lower_be and test_spot < lower_be:
            # below breakeven — classify how far
            dist_pct = (lower_be - test_spot) / lower_be
            if dist_pct >= warning_pct: return 'below_lower_be'
            if dist_pct >= danger_pct: return 'lower_be_warning'
            if dist_pct >= critical_pct: return 'lower_be_danger'
            return 'lower_be_critical'
        if upper_be and test_spot > upper_be:
            dist_pct = (test_spot - upper_be) / upper_be
            if dist_pct >= warning_pct: return 'above_upper_be'
            if dist_pct >= danger_pct: return 'upper_be_warning'
            if dist_pct >= critical_pct: return 'upper_be_danger'
            return 'upper_be_critical'
        # Inside breakeven — classify proximity
        lower_dist = (test_spot - lower_be) / test_spot if lower_be else 1.0
        upper_dist = (upper_be - test_spot) / test_spot if upper_be else 1.0
        nearest_dist = min(lower_dist, upper_dist)
        if nearest_dist < critical_pct: return 'lower_be_critical' if lower_dist < upper_dist else 'upper_be_critical'
        if nearest_dist < danger_pct: return 'lower_be_danger' if lower_dist < upper_dist else 'upper_be_danger'
        if nearest_dist < warning_pct: return 'lower_be_warning' if lower_dist < upper_dist else 'upper_be_warning'
        return 'safe'

    points = []
    for i in range(n_points):
        test_spot = low + i * step
        pnl = engine._compute_pnl_at_spot(positions, test_spot, session)
        points.append({
            'spot': round(test_spot, 2),
            'pnl': round(pnl, 4),
            'zone': classify_zone(test_spot),
        })

    return jsonify({
        'success': True,
        'spot': spot,
        'points': points,
        'breakeven': be_result,
        'gamma': gamma_result,
        'positions_count': len(positions),
        'computed_at': datetime.utcnow().isoformat(),
    })
```

**Zone field values** (all valid values for the `zone` field in each point):

- `"below_lower_be"` — well below lower breakeven (spot < lower_be by > warning_pct)
- `"lower_be_warning"` — within warning zone of lower BE
- `"lower_be_danger"` — within danger zone of lower BE
- `"lower_be_critical"` — within critical zone of lower BE
- `"safe"` — inside breakeven band, not near any threshold
- `"upper_be_warning"` — within warning zone of upper BE
- `"upper_be_danger"` — within danger zone of upper BE
- `"upper_be_critical"` — within critical zone of upper BE
- `"above_upper_be"` — well above upper breakeven
- `"lower_gamma"` — below lower gamma boundary
- `"upper_gamma"` — above upper gamma boundary

**Error handling:**
- Session not found → 404 with `{'success': false, 'error': 'Session not found'}`
- No spot price → 422 with error message
- No positions → 200 with empty points array and `message` field
- `_compute_pnl_at_spot` exception → log error, return 500

**Performance note:** 100 points × typical position count (~6-12) = ~600-1200 `_compute_pnl_at_spot` calls per request. This is on-demand only (not streaming). Acceptable for a UI button click. Do not add to heartbeat.

---

### Phase 3: MMMRiskProfileChart.js — P&L Landscape

**Priority:** P1 High
**Effort:** 90 min
**File:** `webui/frontend/src/components/mmm/MMMRiskProfileChart.js` (NEW)
**Depends on:** Phase 2 (pnl-curve endpoint)

**Purpose:** The crown jewel visualization. Shows the full P&L landscape of the portfolio across a range of BTC prices, with breakeven and gamma boundaries marked.

**Props:**

```jsx
MMMRiskProfileChart({
  sessionId,       // string — used to fetch curve data
  breakeven,       // BreakevenResult dict from heartbeat
  gamma,           // GammaResult dict from heartbeat
  session,         // session object (for param access)
})
```

**Chart library:** Recharts (already used throughout the dashboard — do not add new dependencies).

**Chart spec:**

- Height: 400px
- X-axis: BTC spot price (format: `$XX,XXX`)
- Y-axis: Portfolio P&L in USD (format: `$X.XX` with sign)
- Chart type: `ComposedChart` with `Area` and `ReferenceLine`/`ReferenceArea` overlays

**Area layers (stacked):**
```
Area 1: pnl > 0 → fill='#4caf50' opacity=0.3 (green profit zone)
Area 2: pnl < 0 → fill='#f44336' opacity=0.3 (red loss zone)
```
Use two separate `Area` components with `baseValue={0}` — one for positive values only, one for negative values only. The Recharts `<Area>` component supports this via a `type="monotone"` with the data filtered or using two separate datasets.

Alternative: single dataset with two colored areas using Recharts `defs` and `linearGradient` — evaluate during implementation.

**Reference lines (vertical):**

| Element | Color | Style | Label |
|---|---|---|---|
| Lower breakeven | `#f44336` | solid | `BE↓` at top |
| Upper breakeven | `#f44336` | solid | `BE↑` at top |
| Lower gamma boundary | `#ff9800` | dashed | `γ↓` at top |
| Upper gamma boundary | `#ff9800` | dashed | `γ↑` at top |
| Current spot | `#ffffff` | solid, strokeWidth=2 | `●SPOT` animated |

**Reference areas (zone shading):**

| Zone | X Range | Fill | Opacity |
|---|---|---|---|
| Gamma safe zone | `[lower_gamma, upper_gamma]` | `#ff9800` (amber) | 0.04 |
| Lower danger zone | `[lower_be, lower_gamma]` | `#ff5722` (deep orange) | 0.06 |
| Upper danger zone | `[upper_gamma, upper_be]` | `#ff5722` (deep orange) | 0.06 |

**Zero reference line:** Horizontal `ReferenceLine y={0}` with `stroke='#ffffff'` `strokeDasharray='4 4'` `opacity=0.5`.

**Custom tooltip:**
```jsx
const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const { spot, pnl, zone } = payload[0].payload;
  return (
    <Box sx={{ bgcolor: '#1e1e2e', p: 1, border: '1px solid #444', borderRadius: 1 }}>
      <Typography variant="caption">Spot: ${spot.toLocaleString()}</Typography>
      <Typography variant="caption" sx={{ color: pnl >= 0 ? '#4caf50' : '#f44336', display: 'block' }}>
        P&L: {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
      </Typography>
    </Box>
  );
};
```

**Data loading logic:**

```javascript
const [curveData, setCurveData] = useState(null);
const [loading, setLoading] = useState(false);
const [error, setError] = useState(null);

const fetchCurve = useCallback(async () => {
  if (!sessionId) return;
  setLoading(true);
  try {
    const res = await fetch(`/api/mmm/session/${sessionId}/pnl-curve?n_points=100&range_pct=15`);
    const data = await res.json();
    if (data.success) setCurveData(data);
    else setError(data.error || 'Failed to load curve');
  } catch (e) {
    setError(e.message);
  } finally {
    setLoading(false);
  }
}, [sessionId]);
```

**Refresh triggers:** Listen to socket events `mmm_adjustment`, `mmm_shift`, `mmm_breakeven` (these indicate positions changed). On each event, call `fetchCurve()`. Also fetch on mount and when `sessionId` changes.

Do NOT refresh on every heartbeat — the curve is expensive and heartbeat is every 2s. Refresh only on structural position changes.

**Loading state:** MUI `Skeleton` component at 400px height with chart-like shimmer.

**Error state:** Centered text "Unable to load P&L curve — {error}" with a Retry button.

**No positions state:** Centered text "No open positions — P&L curve unavailable" with a muted chart icon.

**Header:**
```jsx
<Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
  <Typography variant="subtitle2">P&L Risk Profile</Typography>
  <Chip size="small" label={breakeven?.zone || 'UNKNOWN'} color={zoneColor(breakeven?.zone)} />
  <Typography variant="caption" sx={{ color: '#888', ml: 'auto' }}>
    {curveData?.positions_count || 0} positions
  </Typography>
  <IconButton size="small" onClick={fetchCurve} title="Refresh curve">
    <RefreshIcon fontSize="small" />
  </IconButton>
</Box>
```

---

### Phase 4: Enhanced MMMBreakevenPanel.js Redesign

**Priority:** P1 High
**Effort:** 60 min
**File:** `webui/frontend/src/components/mmm/MMMBreakevenPanel.js` (MODIFY)

**Problem with current design:** The horizontal band bar uses fixed 10%/90% positions for breakeven markers regardless of actual price ratios. A session with BE boundaries 1% from spot looks identical to one with BE boundaries 10% from spot. This makes the visualization misleading.

**Fix:** Replace the fixed-position bar with a properly proportional linear scale.

**Props update:**
```jsx
MMMBreakevenPanel({ breakeven, gamma })
// gamma is optional — pass from parent; gamma markers shown only if gamma.enabled is true
```

**Update parent `MMMDashboard.js`** to pass `gamma` prop when rendering `MMMBreakevenPanel`.

**New scaled band bar specification (280px wide):**

The full bar represents the price range `[spot × (1 - view_range), spot × (1 + view_range)]` where `view_range = max(band_width_pct × 2, 10%) / 100`.

Price-to-position mapping:
```javascript
const priceToPos = (price) => {
  const pct = (price - rangeMin) / (rangeMax - rangeMin);
  return Math.max(0, Math.min(100, pct * 100)); // clamp to 0-100%
};
```

**Background color bands (CSS linear-gradient):**

Compute pixel positions for: `lower_be`, `upper_be`, and the critical/danger/warning offsets from each.

```
Left → Right:
  [0% → lower_be_critical_pos]:     #b71c1c (deep red, below BE)
  [lower_be_critical_pos → lower_be_danger_pos]:   #d32f2f (critical zone)
  [lower_be_danger_pos → lower_be_warning_pos]:    #e64a19 (danger zone)
  [lower_be_warning_pos → lower_be_pos]:           #f57c00 (warning zone)
  [lower_be_pos → upper_be_pos]:    #2e7d32 (safe zone, green)
  [upper_be_pos → upper_be_warning_pos]:           #f57c00
  [upper_be_warning_pos → upper_be_danger_pos]:    #e64a19
  [upper_be_danger_pos → upper_be_critical_pos]:   #d32f2f
  [upper_be_critical_pos → 100%]:   #b71c1c
```

All positions are in % of bar width, computed dynamically from actual prices.

**Marker overlays (absolute-positioned within bar container):**

- Lower BE: red `|` line at `priceToPos(lower_be)%`, 2px wide, full height + label `BE↓` below
- Upper BE: red `|` line at `priceToPos(upper_be)%`
- Lower gamma: orange dashed `|` at `priceToPos(lower_gamma_boundary)%` (only if gamma provided and gamma.enabled)
- Upper gamma: orange dashed `|` at `priceToPos(upper_gamma_boundary)%`
- Current spot: white filled circle (8px diameter) at `priceToPos(spot)%`, vertically centered, with colored border matching current breakeven zone color

**New header row:**
```
🎯 Breakeven Band     [SAFE]   [1.0x multiplier]   [▼ expand]
```

Zone badge: MUI `Chip` with color mapping:
- SAFE → success (green)
- WARNING → warning (amber)
- DANGER → error (orange-red)
- CRITICAL → error (red, pulsing animation)

Multiplier chip: shows `breakeven.multiplier + 'x'`, color matches zone.

**Distance labels below bar:**
```
↙ Lower: {distance_lower_pct}% (${(spot - lower_be).toFixed(0)})    ↗ Upper: {distance_upper_pct}% (${(upper_be - spot).toFixed(0)})
```

**Narrow band warning:** If `breakeven.is_narrow_band === true`, show an amber alert below the bar: "Band narrowing — breakeven boundaries converging".

**Collapsed state (default):** Show only the header row with the zone badge and multiplier chip. Expand button shows the full bar.

---

### Phase 5: Enhanced MMMGammaPanel.js Redesign

**Priority:** P2 Medium
**Effort:** 45 min
**File:** `webui/frontend/src/components/mmm/MMMGammaPanel.js` (MODIFY)

**New design additions (keep existing collapsed panel skeleton, add inside it):**

**Proximity meter:** A symmetric horizontal bar (240px) showing:
- Left side: lower gamma distance %
- Center: SPOT (labeled)
- Right side: upper gamma distance %
- Color: green (SAFE) → amber (WARNING) → red (DANGER) for each side independently

The meter has two halves. Each half's fill color is determined by whether that side's distance is within `gamma_danger_distance_pct`, `gamma_warning_distance_pct`, or beyond.

```
Left half (lower side):        Right half (upper side):
 ◄────────── 2.1% ──────[SPOT]────── 2.3% ──────────►
   [green/amber/red fill]           [green/amber/red fill]
```

**Severity indicator:**

The `gamma_severity_lower` and `gamma_severity_upper` values are negative floats (more negative = worse curvature). Normalize for display:

```javascript
// Severity bar: 0 to 100% width where -1000 = 100% width
const severityToWidth = (s) => Math.min(100, Math.abs(s) / 10);
```

Show as two small horizontal bars labeled "Lower Curvature" and "Upper Curvature" — wider = worse. Color matches gamma zone for that side.

**"Leading Indicator" badge:**

```jsx
<Tooltip title="Gamma boundaries are CLOSER to spot than breakeven boundaries. Gamma DANGER fires ~90 seconds before Breakeven WARNING at typical BTC velocity — giving the algorithm advance context before lot multipliers engage.">
  <Chip size="small" label="Leading Indicator" icon={<ElectricBoltIcon />} sx={{ bgcolor: '#ff6f00', color: '#fff', fontSize: '0.65rem' }} />
</Tooltip>
```

Show this badge only when `gamma.enabled === true` and `gamma.observation_only === true`.

**Phase 9 indicator:** When `gamma_severity_multiplier_enabled === false` (default), show a muted chip "Phase 9: Inactive" with a tooltip explaining what Phase 9 will do.

**Observation-only mode visual:** When `gamma.observation_only === true`, show a subtle banner: "Observation mode — severity scores computed, not yet used for lot sizing".

---

### Phase 6: MMMCombinedZoneWidget.js — Concentric Risk Rings

**Priority:** P2 Medium
**Effort:** 60 min
**File:** `webui/frontend/src/components/mmm/MMMCombinedZoneWidget.js` (NEW)

**Purpose:** A compact widget that shows both breakeven and gamma boundaries in a single horizontal scale — the concentric ring mental model rendered as a 1D visualization.

**Props:**
```jsx
MMMCombinedZoneWidget({ breakeven, gamma })
```

**Dimensions:** 100% width × 120px height (responsive).

**Layout:**

```
[BE lower]──[γ lower]──────────────[SPOT]──────────────[γ upper]──[BE upper]

◄──RED──────►◄──AMBER──►◄────────GREEN────────►◄──AMBER──►◄──RED──────►

  ←5.4%←      ←2.1%←                                →2.3%→     →4.8%→
```

**Zone color regions** (using absolute-positioned divs or SVG):

| Region | Color | Hex |
|---|---|---|
| Beyond lower BE (leftmost) | Deep red | `#b71c1c` |
| Lower BE to lower gamma | Amber warning | `#f57c00` |
| Lower gamma to SPOT | Green safe | `#2e7d32` |
| SPOT to upper gamma | Green safe | `#2e7d32` |
| Upper gamma to upper BE | Amber warning | `#f57c00` |
| Beyond upper BE (rightmost) | Deep red | `#b71c1c` |

**Markers:**

- `[BE lower]` `[BE upper]`: solid red vertical lines with price labels above
- `[γ lower]` `[γ upper]`: dashed orange vertical lines with price labels above
- `[SPOT]`: white filled circle, 10px diameter, with current price label below

**Distance labels:**

Row of 4 percentage labels below the bar, positioned at their respective markers:
```
5.4%     2.1%          ●          2.3%     4.8%
```

**Merge alert:** If lower gamma boundary is closer to spot than breakeven CRITICAL zone threshold (i.e., gamma boundary has merged with or passed the critical zone), show a red pulsing alert:

```jsx
{gammaCloserThanCritical && (
  <Alert severity="error" sx={{ mt: 0.5, py: 0, fontSize: '0.7rem' }}>
    Gamma boundary inside critical zone — extreme caution
  </Alert>
)}
```

**Combined zone summary chip:** Single chip showing the worst zone across both systems:
```jsx
const worstZone = pickWorst(breakeven?.zone, gamma?.gamma_zone);
<Chip label={`Combined: ${worstZone}`} color={zoneChipColor(worstZone)} size="small" />
```

**When gamma is disabled:** Render only the breakeven boundaries with a muted note "Gamma: disabled".

---

### Phase 6.5: MMMHealthRadar.js — Portfolio Health Spider Chart

**Priority:** P2 Medium
**Effort:** 45 min
**File:** `webui/frontend/src/components/mmm/MMMHealthRadar.js` (NEW)
**Depends on:** Nothing — all data already in heartbeat payload
**Risk:** Zero — uses Recharts `RadarChart` (already in recharts 2.9.0, no new dependencies)

#### Design Analysis: Why Concentric Circles Were Rejected

The originally proposed "Risk Radar" (concentric circles: center=spot, inner ring=gamma, outer ring=breakeven) was analyzed and rejected for the following reasons:

1. **Dimensionality mismatch**: BTC options risk is 1-dimensional — price moves up or down on a number line. Mapping 1D linear data to 2D polar coordinates wastes the entire angular (θ) dimension. The circle becomes a semicircle with a dot, which carries no more information than a horizontal bar. Phase 6 (CombinedZoneWidget) already shows the same spatial relationship more accurately and readably on a linear scale.

2. **Exact distance is harder to read radially**: Humans compare lengths more accurately on linear scales than on arcs. The concentric-circle design makes it harder, not easier, to judge "how close is spot to the gamma ring?"

3. **Redundant with Phase 6**: Both designs answer the question "where is spot relative to gamma and breakeven?" Phase 6 answers it on a linear scale; the concentric-circle design answers it on an arc. Same information, Phase 6 is more readable.

4. **Custom SVG vs. Recharts convention**: Concentric circles require custom SVG/Canvas. The rest of the dashboard uses Recharts. Breaking this convention adds maintenance burden.

#### What IS Worth Adding: A True 5-Axis Health Spider Chart

A Recharts `RadarChart` with 5 independent axes — each representing a different risk dimension — adds genuinely NEW information that no other panel shows:

| Axis | Data Source | Normalization | 0.0 = worst | 1.0 = best |
|---|---|---|---|---|
| **Breakeven Safety** | `breakeven.nearest_distance_pct` / `breakeven_warning_pct` | clamped 0-1 | spot at BE | spot far from BE |
| **Gamma Safety** | `gamma.nearest_distance_pct` / `gamma_warning_distance_pct` | clamped 0-1 | spot at γ boundary | spot far from γ |
| **Margin Health** | `(100 - margin.utilization_pct) / 100` | direct | margin at 100% | margin at 0% |
| **Band Width** | `breakeven.band_width_pct` / `breakeven_narrow_band_threshold` | clamped 0-1 | band width = 0 | band width ≥ threshold |
| **Regime Health** | mapped from `regime.action` string | see below | BLOCK_ALL | NORMAL |

**Regime health mapping:**
```javascript
const REGIME_SCORE = {
  'NORMAL': 1.0,
  'ACTION_BLOCK_DANGEROUS_SIDE': 0.65,
  'ACTION_BOOST_SAFE_SIDE': 0.85,
  'BLOCK_CE_SELLS': 0.6,
  'BLOCK_PE_SELLS': 0.6,
  'BLOCK_ALL_SELLS': 0.15,
};
```

**The value of this design**: When all 5 axes are healthy, the spider web polygon is large and symmetric (a "fat pentagon"). When any single dimension is stressed, that axis collapses — the polygon becomes asymmetric/lopsided. Operators immediately see WHICH dimension is under stress without reading any numbers.

**Example visual states:**

```
ALL SAFE: fat symmetric pentagon  MARGIN STRESS: lopsided on Margin axis
  Breakeven                          Breakeven
   1.0                                  0.9
   ╱───╲                              ╱───╲
  ╱     ╲                            ╱     ╲
Regime  Gamma                    Regime  Gamma
 0.9    0.8                       0.8    0.7
  ╲     ╱                            ╲   ╱
   ╲───╱                              ╲╱ ← Margin collapsed
Margin  Band                      Margin  Band
 0.9    0.8                        0.1    0.8
```

#### Component Spec

**Props:**
```jsx
MMMHealthRadar({ breakeven, gamma, heartbeat, session })
// heartbeat: full heartbeat object (for margin and regime data)
// session: for param defaults when heartbeat is unavailable
```

**Chart library:** Recharts `RadarChart` (zero new dependencies — recharts 2.9.0 already installed).

**Chart dimensions:** 200 × 200px. Compact — designed to sit beside other widgets in a 2-column layout.

**Data shape for Recharts:**
```javascript
const radarData = [
  { subject: 'Breakeven', value: beSafetyScore, fullMark: 1 },
  { subject: 'Gamma',     value: gammaSafetyScore, fullMark: 1 },
  { subject: 'Margin',    value: marginHealthScore, fullMark: 1 },
  { subject: 'BandWidth', value: bandHealthScore, fullMark: 1 },
  { subject: 'Regime',    value: regimeHealthScore, fullMark: 1 },
];
```

**Color logic:** The filled polygon changes color based on the MINIMUM score (weakest axis):
```javascript
const minScore = Math.min(...radarData.map(d => d.value));
const fillColor = minScore > 0.7 ? '#4caf50'   // green — all healthy
               : minScore > 0.4 ? '#ff9800'    // amber — stressed
               : '#f44336';                     // red — critical
```

**Recharts component structure:**
```jsx
<RadarChart cx="50%" cy="50%" outerRadius="80%" width={200} height={200} data={radarData}>
  <PolarGrid stroke="rgba(255,255,255,0.12)" />
  <PolarAngleAxis dataKey="subject" tick={{ fill: '#9e9e9e', fontSize: 10 }} />
  <PolarRadiusAxis angle={30} domain={[0, 1]} tick={false} axisLine={false} />
  <Radar name="Health" dataKey="value" stroke={fillColor} fill={fillColor} fillOpacity={0.3} />
</RadarChart>
```

**Update strategy:** Every heartbeat (Recharts re-renders in ~0.1ms for a 5-point polygon — negligible cost).

**Header:**
```
🕸 Portfolio Health    [Overall: SAFE / WARNING / CRITICAL]
```
Show the overall health as a single chip (worst of all 5 axes).

**Edge cases:**
- Gamma disabled (`gamma.enabled === false`): set `gammaSafetyScore = 0.5` (neutral, not penalizing) and show a muted label "Gamma: off"
- No breakeven data: `beSafetyScore = 0.5` neutral
- No margin data: `marginHealthScore = 0.5` neutral
- No positions: all scores = 0.5, show "No positions — health unavailable" overlay

**What to NOT do:**
- Do not replace Phase 6 (CombinedZoneWidget) with this — they show different things. CombinedZoneWidget shows WHERE spot is spatially relative to boundaries; HealthRadar shows HOW HEALTHY each risk dimension is on a normalized scale.
- Do not animate the polygon — Recharts handles smooth transitions automatically via React re-renders.

**Placement in Risk tab:** Render side-by-side with the CombinedZoneWidget in a 2-column Grid layout (each 50% width on desktop, 100% on mobile). This keeps the top of the Risk tab compact before the full P&L chart.

---

### Phase 7: MMMDistanceHistoryChart.js — Zone Timeline

**Priority:** P2 Medium
**Effort:** 75 min
**File:** `webui/frontend/src/components/mmm/MMMDistanceHistoryChart.js` (NEW)

**Purpose:** Time-series chart showing how risk proximity evolved throughout the session. Answers "was the portfolio safe all session, or did it come close?" without needing to read activity logs.

**Props:**
```jsx
MMMDistanceHistoryChart({ sessionId, breakeven, gamma, heartbeatHistory })
// heartbeatHistory: array of historical heartbeat snapshots, managed by parent
```

**Data management:**

The parent component (MMMDashboard or the Risk tab) maintains a rolling buffer:

```javascript
const [heartbeatHistory, setHeartbeatHistory] = useState([]);
const MAX_HISTORY = 200;

// On each mmm_heartbeat socket event:
const onHeartbeat = (data) => {
  if (!data.breakeven || !data.gamma) return;
  setHeartbeatHistory(prev => {
    const entry = {
      time: new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' }),
      timestamp: Date.now(),
      lower_be_pct: data.breakeven.distance_lower_pct,
      upper_be_pct: data.breakeven.distance_upper_pct,
      lower_gamma_pct: data.gamma.lower_distance_pct,
      upper_gamma_pct: data.upper_distance_pct,
      be_zone: data.breakeven.zone,
      gamma_zone: data.gamma.gamma_zone,
    };
    const next = [...prev, entry];
    return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next;
  });
};
```

**Chart specification (Recharts `LineChart`):**

- Height: 250px
- X-axis: `time` field (HH:mm), every 10th tick shown
- Y-axis: % distance (0–15%), labeled as `{v}%`

**Lines:**

| Line | Data key | Color | Style |
|---|---|---|---|
| Lower BE distance | `lower_be_pct` | `#f44336` | dashed |
| Upper BE distance | `upper_be_pct` | `#f44336` | solid |
| Lower γ distance | `lower_gamma_pct` | `#ff9800` | dashed |
| Upper γ distance | `upper_gamma_pct` | `#ff9800` | solid |

**Threshold reference lines (horizontal):**

| Line | Y value | Color | Style | Label |
|---|---|---|---|---|
| BE warning | `breakeven_warning_pct` (2.0) | `#f57c00` | dashed | `Warning` |
| BE danger | `breakeven_danger_pct` (1.0) | `#f44336` | dashed | `Danger` |
| Gamma warning | `gamma_warning_distance_pct` (3.0) | `#ff9800` | dotted | `γ Warning` |

These thresholds should be read from the `session` params — they may be non-default.

**Event markers (vertical reference lines):**

Listen for these socket events and record their timestamps in a separate `events` array:

| Socket Event | Label | Color |
|---|---|---|
| `mmm_shield_fired` | `Shield↑` or `Shield↓` | `#e91e63` (pink) |
| `mmm_shift` | `Shift` | `#9c27b0` (purple) |
| `mmm_adjustment` | (no label, too frequent) | — |

Render events as `ReferenceLine x={timestamp}` with a rotated label at the top.

**Empty state:** "Collecting data — distance history populates from session heartbeats." Show after mount if history is empty.

**Note:** This component does NOT fetch historical data from the backend. It only accumulates data during the current browser session. If the page is refreshed, history resets. This is intentional — adding backend persistence is a future enhancement.

---

### Phase 8: Dashboard Layout Integration

**Priority:** P3 Lower
**Effort:** 30 min
**File:** `webui/frontend/src/components/mmm/MMMDashboard.js` (MODIFY)

**Approach:** Add a new "Risk" tab to the session detail tab strip alongside Overview, P&L, Activity (and Settings if present).

**Tab strip change:**

Locate the `<Tabs>` component in the session detail section. Add:
```jsx
<Tab label="Risk" value="risk" />
```

**Risk tab content:**

```jsx
{activeTab === 'risk' && (
  <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
    <MMMCombinedZoneWidget breakeven={session.breakeven} gamma={session.gamma} />
    <Divider />
    <MMMRiskProfileChart
      sessionId={session.session_id}
      breakeven={session.breakeven}
      gamma={session.gamma}
      session={session}
    />
    <Divider />
    <MMMDistanceHistoryChart
      sessionId={session.session_id}
      breakeven={session.breakeven}
      gamma={session.gamma}
      heartbeatHistory={heartbeatHistory}
    />
  </Box>
)}
```

**Overview tab:** Keep existing MMMBreakevenPanel and MMMGammaPanel, but:
1. Update `MMMBreakevenPanel` call to also pass `gamma`:
   ```jsx
   <MMMBreakevenPanel breakeven={session.breakeven} gamma={session.gamma} />
   ```
2. The gamma panel remains standalone on Overview.

**Heartbeat history state:** Add `heartbeatHistory` state at the dashboard level (or session detail level) and wire the `mmm_heartbeat` socket event to populate it. Pass `heartbeatHistory` down to `MMMDistanceHistoryChart`.

**Imports:** Add imports for all 3 new components at the top of `MMMDashboard.js`:
```javascript
import MMMRiskProfileChart from './MMMRiskProfileChart';
import MMMCombinedZoneWidget from './MMMCombinedZoneWidget';
import MMMDistanceHistoryChart from './MMMDistanceHistoryChart';
```

---

## Section 7: Consolidated Visual Layout Specification

```
SESSION DETAIL VIEW
════════════════════

TABS: [Overview] [Risk ← NEW] [P&L] [Positions] [Activity] [Settings]

══ OVERVIEW TAB ══════════════════════════════════════════════════════

 [Trigger Gauges — existing]

 ┌─ Enhanced MMMBreakevenPanel ─────────────────────────────────────┐
 │  🎯 Breakeven Band    [🟢 SAFE]   [1.0x]          [▼ expand]    │
 │  ┌──────────────────────────────────────────────────────────┐    │
 │  │ ░░░░░░[─BE─][──γ──────────────●──────────────γ──][─BE─]░ │    │
 │  │   BE↓   γ↓                 $90k               γ↑   BE↑  │    │
 │  │  $82k  $87k                                  $93k  $98k  │    │
 │  └──────────────────────────────────────────────────────────┘    │
 │   ↙ Lower: 5.4% ($4,860)              ↗ Upper: 5.3% ($4,770)    │
 └──────────────────────────────────────────────────────────────────┘

 ┌─ Enhanced MMMGammaPanel ─────────────────────────────────────────┐
 │  ⚡ Gamma Boundaries  [🟢 SAFE] [Leading Indicator] [▼ expand]  │
 │  ├─────────── 2.1% ────────[●SPOT]──────── 2.3% ───────────┤    │
 │  Lower curvature: ██░░░░░░░░  Upper curvature: ███░░░░░░░░  │    │
 │  [Observation mode — severity scores not yet used for sizing]    │
 └──────────────────────────────────────────────────────────────────┘

══ RISK TAB (NEW) ════════════════════════════════════════════════════

 ┌─ Row 1: 2-column layout ───────────────────────────────────────────────────────┐
 │                                                                                  │
 │  ┌─ Combined Zone Rings ─────────────────┐  ┌─ Portfolio Health ─────────────┐  │
 │  │ [BE↓]─[γ↓]──────[●]──────[γ↑]─[BE↑] │  │  🕸 Portfolio Health [🟢 SAFE]  │  │
 │  │ ◄─RED─►◄AMBER►◄─GREEN──►◄AMBER►◄─RED►│  │         Breakeven               │  │
 │  │  5.4%   2.1%           2.3%   4.8%   │  │          1.0                    │  │
 │  │        [Combined: 🟢 SAFE]            │  │   Regime ╱──────╲ Gamma         │  │
 │  └───────────────────────────────────────┘  │     0.9 ╱        ╲ 0.8         │  │
 │                                             │         ╲        ╱             │  │
 │  NOTE: Left = spatial "WHERE is spot"       │   Band   ╲──────╱ Margin       │  │
 │  Right = dimensional "HOW HEALTHY is each"  │     0.8              0.9        │  │
 │  These answer complementary questions.      │  [fat pentagon = all healthy]   │  │
 │                                             └────────────────────────────────┘  │
 └────────────────────────────────────────────────────────────────────────────────┘

 ┌─ P&L Risk Profile ───────────────────────────────────────────────┐
 │  📈 P&L Risk Profile    [🟢 SAFE]    6 positions    [↻ Refresh]   │
 │                                                                    │
 │  $20 ─                                                             │
 │  $10 ─  ╔════════╗                             ╔════════╗          │
 │   $5 ─  ║        ╚═══════════━━━━━━━━━━━═══════╝        ║          │
 │   $0 ─ ─╫───────────────────────────────────────────────╫─ - - - │
 │  -$5 ─  ║               ●SPOT                            ║          │
 │ -$15 ─  ╚════╗                                     ╔════╝          │
 │ -$25 ─       ╚════════╗                   ╔════════╝               │
 │       $75k  $80k  $85k BE↓ γ↓ $90k γ↑ BE↑ $95k  $100k  $105k    │
 └──────────────────────────────────────────────────────────────────┘

 ┌─ Distance History ───────────────────────────────────────────────┐
 │  15% ····γ Warning············································     │
 │  10%    ─────────────────────────────────────────────────────     │
 │   5% BE upper ──────────────────────────────────                  │
 │       ────────────────────────────────────────── Warning──        │
 │   3% γ upper ─────────────────────────────────                    │
 │   2%                                          ───Danger──         │
 │   1%    BE lower ────────────────────────────              ↑Shield│
 │   0% ────────────────────────────────────────────────────────     │
 │      10:00  10:15  10:30  10:45  11:00  11:15  11:30  11:45       │
 └──────────────────────────────────────────────────────────────────┘
```

**Color reference for all new UI elements:**

| Element | Hex | Usage |
|---|---|---|
| Breakeven SAFE | `#2e7d32` | Safe zone band, SAFE chip |
| Breakeven WARNING | `#f57c00` | Warning band, threshold line |
| Breakeven DANGER | `#e64a19` | Danger band, threshold line |
| Breakeven CRITICAL | `#d32f2f` | Critical band, pulsing chip |
| Breakeven beyond | `#b71c1c` | Leftmost/rightmost bar regions |
| Gamma boundary | `#ff9800` | Gamma markers (dashed), gamma panel color |
| Gamma DANGER | `#ff6f00` | Deep amber, settings group accent |
| Shield event | `#e91e63` | Shield timeline markers |
| Strike shift event | `#9c27b0` | Shift timeline markers |
| Spot marker | `#ffffff` | Current spot circle on all bars |

---

## Section 8: MMM Algo Deep Benefit Analysis

### 8.1 Early Warning Pipeline — Detailed Scenario

```
Scenario: BTC at $90,000. Short CE strike at $93,000 (3.3% OTM). BTC rising at $450/min.

T-0: Start. Both panels green. Combined widget shows all-green.
  BE boundaries: $82,500 / $98,000  (8.3% / 8.9% from spot)
  γ boundaries:  $86,700 / $93,000  (3.7% / 3.3% from spot)

T-3min: BTC reaches $91,350 ($450 × 3min). γ upper distance = 1.65% → DANGER fires.
  → MMMGammaPanel turns red-amber.
  → Distance history shows γ upper line crossing the danger threshold.
  → Breakeven is still SAFE (upper BE at $98,000, still 7.3% away).
  → Algorithm: NO lot change yet. Operator has advance context.

T-5min: BTC reaches $92,250. γ upper distance = 0.81% → well inside DANGER.
  BE upper distance dropping: $98,000 - $92,250 = $5,750 = 6.2%. Still SAFE.
  → Risk tab combined widget: γ = DANGER, BE = SAFE. Combined = WARNING.

T-7min: BTC reaches $93,150. Upper BE: $98,000 - $93,150 = $4,850 = 5.2%. Still SAFE.
  ATM Shield: ~0.5% from $93,000 strike → Shield fires.
  → Close CE leg at $93,000. Reopen CE at $94,500 (+1.5% OTM).
  → Cache invalidated. New curve computed.

T-7.5min (post-shield): New γ upper boundary = $94,500. Distance = 1.45% from $93,150.
  BE upper recalculated with new OTM premium → widens to $100,000 (7.3%).
  → Risk tab P&L chart RESHAPES. The right side slope flattens visibly.
  → Distance history shows a "Shield↑" vertical marker, then γ line jumps outward.
  → Both panels return to green/amber from red.

NET RESULT: The visual timeline tells the complete story. No log parsing needed.
```

### 8.2 Multiplier Cascade — Detailed Mechanics

The lot size formula in `mmm_engine.py`:

```
final_lots = min(
  ceil(base_lots × gamma_mult × breakeven_mult × trend_mult),
  base_lots × max_combined_lot_multiplier
)
```

Zones and their multiplier ramps:

| BE Zone | Distance | breakeven_mult range |
|---|---|---|
| SAFE | > warning_pct | 1.0x |
| WARNING | danger_pct to warning_pct | 1.0x → 1.5x (linear ramp) |
| DANGER | critical_pct to danger_pct | 1.5x → 2.5x (linear ramp) |
| CRITICAL | < critical_pct | 2.5x → 3.0x (linear ramp to min distance) |

The P&L chart directly shows WHY multipliers escalate: the visible slope of the loss curve steepens as spot approaches BE. The algorithm is responding to that slope.

### 8.3 P&L Curve as Operator Decision Tool

The P&L curve provides answers to questions operators currently cannot easily answer:

| Question | Without chart | With chart |
|---|---|---|
| "If BTC drops 5%, what's my loss?" | Mental math over 6+ positions | Read Y-axis at spot-5% |
| "Is the portfolio symmetric?" | Compare upper/lower BE distances | Visual — does curve have equal slopes? |
| "Is loss acceleration starting?" | Not detectable without gamma | See the kink where γ boundary is |
| "Did the shield improve my situation?" | Check activity log | Chart reshapes visibly after shield |
| "How much buffer before critical?" | Compute from each position | Distance from current spot to red zone |

### 8.4 Phase 9 Readiness Signal

When `gamma_severity_multiplier_enabled` is enabled (Phase 9), the gamma severity scores:

- `gamma_severity_lower` ≈ second derivative of P&L at lower boundary (negative)
- `gamma_severity_upper` ≈ second derivative of P&L at upper boundary (negative)

The score magnitude tells how FAST the loss accelerates at each boundary. A severity of -800 means $800 of additional loss per 1% of additional price movement, per unit of portfolio size.

Phase 9 will use the severity asymmetry: if `abs(gamma_severity_lower) >> abs(gamma_severity_upper)`, the lower side has worse curvature, meaning more PE lot selling is warranted. This is directional intelligence that goes beyond the current symmetric lot sizing.

**Phase 9 prerequisites (not in this plan — future work):**
1. 10+ sessions of severity data to calibrate thresholds
2. Severity normalization per portfolio size
3. A/B testing framework to compare P&L with/without severity multiplier

The severity bars in the gamma panel (Phase 5) begin collecting operator intuition for these values before Phase 9 is automated.

---

## Section 9: File Change Map

| File | Change Type | Priority | Phase | Effort |
|---|---|---|---|---|
| `webui/frontend/src/components/mmm/MMMSettingsDialog.js` | Modify — add gammaDetector param group | P0 Critical | 1 | 30 min |
| `webui/backend/routes/mmm/mmm_api.py` | Modify — add `/pnl-curve` endpoint | P1 High | 2 | 45 min |
| `webui/frontend/src/components/mmm/MMMRiskProfileChart.js` | New file | P1 High | 3 | 90 min |
| `webui/frontend/src/components/mmm/MMMBreakevenPanel.js` | Modify — scaled bar + gamma markers | P1 High | 4 | 60 min |
| `webui/frontend/src/components/mmm/MMMGammaPanel.js` | Modify — proximity meter + severity bars | P2 Medium | 5 | 45 min |
| `webui/frontend/src/components/mmm/MMMCombinedZoneWidget.js` | New file | P2 Medium | 6 | 60 min |
| `webui/frontend/src/components/mmm/MMMHealthRadar.js` | New file — 5-axis spider chart | P2 Medium | 6.5 | 45 min |
| `webui/frontend/src/components/mmm/MMMDistanceHistoryChart.js` | New file | P2 Medium | 7 | 75 min |
| `webui/frontend/src/components/mmm/MMMDashboard.js` | Modify — Risk tab + new component wiring | P3 Lower | 8 | 30 min |

**Total estimated effort:** ~7.75 hours (single focused session)

**New dependency added:** None. `RadarChart`, `PolarGrid`, `PolarAngleAxis`, `PolarRadiusAxis`, `Radar` are all in recharts 2.9.0 (already installed). Import them from `'recharts'` — same as other chart components.

**No backend files other than `mmm_api.py` need changes.** All computation already exists. The backend work is purely one additive endpoint.

---

## Section 10: Implementation Sequencing Rules

1. **Phase 1 first** (Settings dialog): Standalone, zero risk, 30 min. Unblocks operators from tuning gamma params. No dependency on any other phase.

2. **Phase 2 second** (API endpoint): Standalone backend change. No frontend dependency. Do before any chart work.

3. **Phase 3 after Phase 2** (P&L chart): Depends on the `/pnl-curve` endpoint existing. Can be built with a mock endpoint during development but should be tested against the real endpoint.

4. **Phases 4 and 5 in parallel with Phase 3**: Panel redesigns have no dependency on the new API endpoint. Can be developed independently and merged.

5. **Phase 6 after Phase 4** (Combined widget): Needs the price-to-position scaling logic to be stable — extract it as a shared utility `priceToBarPct(price, rangeMin, rangeMax)` during Phase 4 so Phase 6 can reuse it.

5.5. **Phase 6.5 in parallel with Phase 6** (Health Radar): Has zero dependency on any other phase. All data comes from the heartbeat payload. The only imports needed are Recharts components. Can be built, tested, and merged completely independently.

6. **Phase 7 in parallel with Phases 6/6.5**: Distance history chart has no dependency on Phases 4-6. Only needs socket data.

7. **Phase 8 last** (Dashboard layout): Wires all new components together. Must be done after all components are built and tested individually.

**Shared utility to extract during Phase 4:**

```javascript
// webui/frontend/src/components/mmm/mmmChartUtils.js (NEW — small utility)
export const priceToBarPct = (price, rangeMin, rangeMax) => {
  if (rangeMax <= rangeMin) return 50;
  return Math.max(0, Math.min(100, ((price - rangeMin) / (rangeMax - rangeMin)) * 100));
};

export const zoneToColor = (zone) => ({
  SAFE: '#2e7d32',
  WARNING: '#f57c00',
  DANGER: '#e64a19',
  CRITICAL: '#d32f2f',
}[zone] || '#888');

export const zoneToMuiColor = (zone) => ({
  SAFE: 'success',
  WARNING: 'warning',
  DANGER: 'error',
  CRITICAL: 'error',
}[zone] || 'default');
```

Both Phase 4 (MMMBreakevenPanel) and Phase 6 (MMMCombinedZoneWidget) use `priceToBarPct`. Extracting it prevents code duplication.

---

## Section 11: Open Questions for Operator

These questions should be answered before or during Phase 8 to avoid rework:

**Q1: Risk tab vs. Overview coexistence**

> Should the enhanced breakeven/gamma panels on Overview be replaced by a link to the Risk tab, or should both exist?
>
> Recommendation: Keep Overview panels for quick glance (compact, always visible), keep Risk tab for deep analysis (full charts). The Overview panels become the "summary" and the Risk tab becomes the "detail view". Implement this way unless operator prefers otherwise.

**Q2: P&L curve refresh strategy**

> Should the P&L curve auto-refresh on every adjustment event (`mmm_adjustment`, `mmm_shift`), or should it be manual (Refresh button only)?
>
> Recommendation: Auto-refresh on `mmm_shift` and `mmm_breakeven` events (structural position changes), but NOT on `mmm_adjustment` (too frequent). Add a visible "Stale — click to refresh" indicator if last fetch was > 60 seconds ago. Manual refresh button always available.

**Q3: Gamma DANGER → ATM Shield modulation (Phase 9 precursor)**

> Could gamma DANGER zone eventually be used to modulate ATM Shield sensitivity — e.g., when gamma is in DANGER, lower the shield OTM threshold from 0.5% to 0.3% (fire earlier)?
>
> This is a Phase 9 question. The current plan does not implement this. But Phase 5's severity display and Phase 7's distance history will provide the empirical data needed to decide. Recommend: collect 10 sessions of data showing gamma-to-shield timing, then decide.

**Q4: gamma_detector_enabled default change**

> Currently `gamma_detector_enabled = false` in DEFAULT_PARAMS. After 3 sessions with observation data confirming the detector works, should the default be changed to `true`?
>
> Recommendation: Yes, but only after:
> - Phase 1 is deployed (so it can be toggled from UI)
> - 3 complete sessions with gamma enabled manually
> - Severity scores reviewed for reasonableness
> - No unexpected performance impact on heartbeat cycle observed

**Q5: Historical curve data persistence**

> The MMMDistanceHistoryChart currently only accumulates data within the current browser session (no backend persistence). Should backend persistence be added later?
>
> Recommendation: Defer. The activity log already records zone transitions. A future enhancement could rebuild the history chart from activity log data on component mount. Not in scope for this plan.

---

---

## Section 12: Risk Radar Design Analysis (Concentric Circle Concept — Full Evaluation)

This section documents the complete feasibility analysis of the proposed "Risk Radar" (concentric circles), explains why it was rejected in its original form, and documents the adapted design (Phase 6.5 Health Radar) that was adopted instead.

### 12.1 Feasibility Assessment

**Can it be implemented with existing heartbeat data?** Yes — all fields are already in the payload:
- `breakeven.distance_lower_pct`, `breakeven.distance_upper_pct` → outer ring radii
- `gamma.lower_distance_pct`, `gamma.upper_distance_pct` → inner ring radii
- `breakeven.zone`, `gamma.gamma_zone` → ring colors

No new backend work needed for either design.

### 12.2 Mathematical Mapping — Concentric Circle Design

For the concentric-circle design, the radial mapping would be:

```
inner_ring_radius = f(gamma_distance_pct)
outer_ring_radius = f(breakeven_distance_pct)

f(pct) = BASE_RADIUS × min(pct / MAX_DISPLAY_PCT, 1.0)

where BASE_RADIUS ≈ 80px (outer ring) and inner = 0.5 × outer
```

**The problem**: Both directions (lower and upper) collapse to a single ring radius, losing the asymmetry information. A 2.1% lower gamma distance and 2.3% upper gamma distance map to the same ring, hiding that the lower side is slightly more dangerous. To show asymmetry, you'd need a half-ring per side — at which point you have a bar chart drawn as a semicircle, which is harder to read than just a bar.

### 12.3 Rendering Approach Comparison

| Approach | Pros | Cons | Verdict |
|---|---|---|---|
| Pure SVG | Full control, crisp at any size, no dependencies | 150-200 lines of manual SVG code, breaks Recharts convention | ❌ Reject |
| Canvas | Fastest for animation | Complex React integration, accessibility issues, no MUI theming | ❌ Reject |
| Recharts `PolarRadiusAxis` | Native integration | Recharts polar API is designed for spider charts, NOT concentric circles — would require workarounds | ❌ Reject |
| Recharts `RadarChart` (5 axes) | Native integration, zero new deps, already in recharts 2.9.0 | Only for multi-dimensional data, NOT concentric circles | ✅ **Adopt (adapted design)** |

### 12.4 Why the Concentric Circle Design Was Rejected

**Core reason: Dimensionality mismatch**

BTC options risk is **strictly 1-dimensional**. BTC spot price can only go up or down — there is no second spatial dimension. The gamma boundary and breakeven boundary are both points on a number line (price axis), not rings around a center in 2D space.

Mapping 1D → 2D polar coordinates:
- The radius dimension (r) carries information: distance from spot to boundary
- The angular dimension (θ) carries **no information** for this data
- The result is a semicircle with markers — equivalent visual information to a horizontal bar, harder to read

This is not a design preference — it's a mathematical property of the data. Any circular visualization of 1D options risk must either waste the angular dimension (misleading) or map a non-existent second dimension (fabricated).

**Specific problems:**

1. **Can't compare distances accurately in radial form**: Given inner ring at r=40px and outer ring at r=80px, humans cannot accurately judge that inner=50% of outer. On a linear bar, this is immediately apparent.

2. **Angular positioning is arbitrary**: Would the lower gamma boundary be at 180° (left) and upper at 0° (right)? Or both at 270°/90°? Any choice is arbitrary because angle has no meaning in the model.

3. **Strike markers as angles**: The proposal mentions showing option strikes as "angular markers." This would require mapping a strike price to an angle — but angle represents nothing in the model, so this mapping would be completely arbitrary and potentially confusing.

4. **Redundant with Phase 6**: CombinedZoneWidget already shows spatial proximity on a linear scale, which is the correct representation for 1D data.

### 12.5 Why the Health Radar (Phase 6.5) Was Adopted

The adopted design turns the "radar" metaphor into a genuine **multi-dimensional health monitor** — which is exactly what spider charts are designed for.

**5 dimensions that are genuinely independent:**
1. Breakeven safety — distance to portfolio loss
2. Gamma safety — distance to loss acceleration zone
3. Margin health — exchange margin utilization
4. Band width health — convergence of breakeven boundaries
5. Regime health — algo's current trading restrictions

These 5 dimensions can be stressed or healthy independently:
- A session can have good breakeven safety but poor margin health (over-capitalized position)
- A session can have good gamma safety but a BLOCK_ALL regime (vol spike)
- A session can have narrow band width but still be far from breakeven (low net premium collected)

The spider chart shows all 5 simultaneously. The "lopsided polygon" pattern tells operators which dimension is the bottleneck. This genuinely cannot be seen from any other panel.

### 12.6 Update Strategy

Health Radar: every heartbeat (~0.1ms Recharts re-render for 5-point polygon, negligible).

Concentric circle design (if it were adopted): same — every heartbeat for distance recalculation.

No performance difference between the two designs. Both are safe for heartbeat-rate updates.

### 12.7 Potential Pitfalls of Phase 6.5 Health Radar

1. **Normalization sensitivity**: If `breakeven_warning_pct` is set to a very large value (e.g., 15%), the Breakeven Safety axis is almost always near 1.0 (safe), giving a false impression. Mitigation: cap the normalization denominator at a reasonable value (e.g., 10%).

2. **Neutral defaults for missing data**: When gamma is disabled, setting `gammaSafetyScore = 0.5` is correct but could be confusing — a user might think gamma=0.5 is a real measurement. Mitigation: show a muted "γ: off" label on the Gamma axis tick.

3. **Regime string matching**: The `regime.action` strings must match exactly. If backend adds new action strings, the `REGIME_SCORE` mapping will return `undefined → 0.5`. The `?? 0.5` fallback handles this gracefully.

4. **Band width when one breakeven is missing**: `band_width_pct` is `null` when only one boundary exists. Use `0.5` as neutral in this case (not penalizing a healthy one-sided portfolio).

5. **Spider chart with 5 axes is unfamiliar to some operators**: Add a "?" icon with a tooltip explaining each axis and its meaning. This is especially important for the Band Width and Regime axes which are less intuitive.

### 12.8 Summary Verdict

| Concept | Feasibility | Information Value | Implementation Cost | Verdict |
|---|---|---|---|---|
| Concentric circle radar | ✅ Feasible | ❌ Redundant with Phase 6 | Medium (custom SVG) | **REJECTED** |
| Portfolio threat gauge (speedometer) | ✅ Feasible | ⚠️ Marginal (collapses 5D to 1D) | Low (SVG arc) | Not adopted |
| 5-axis health spider chart | ✅ Feasible | ✅ Genuinely new information | Low (Recharts, 120 lines) | **ADOPTED as Phase 6.5** |

---

*Plan updated 2026-03-15 with Risk Radar analysis and Phase 6.5 Health Radar adoption.*
*Total phases: 9 (Phases 1, 2, 3, 4, 5, 6, 6.5, 7, 8). Total new/modified files: 9.*


---

## SOURCE FILE: analysis/VISUAL_ANALYSIS_RESULTS.md

# 📊 VISUAL ANALYSIS RESULTS
**Generated:** November 7, 2025

---

## ✅ VISUALIZATIONS CREATED & OPENED IN BROWSER

### 1. **Race Condition Timeline** 
📁 `analysis/race_condition_timeline.html`

**What it shows:**
- Interactive timeline of ALL order events
- Color-coded by event type:
  - 🟢 **GREEN** = BUY orders
  - 🔴 **RED** = SELL orders  
  - 🔵 **BLUE** = Fills
  - 🟠 **ORANGE** = Throttle activations
  - 🟣 **PURPLE** = TP orders

**Time Gap Analysis:**
- Shows seconds between consecutive events
- **RED WARNING** = < 10 seconds (CRITICAL)
- **ORANGE WARNING** = < 30 seconds (needs throttle)
- **GRAY** = > 30 seconds (OK)

**Key Finding:**
```
⚠️  WARNING: 2 orders placed < 30s apart!
   - 16:45:13: BUY @ $99,000 (+1.0s)
   - 16:45:18: BUY @ $99,000 (+5.0s)
```
→ **This is the duplicate order bug BEFORE throttle was added**

---

### 2. **Performance Report Dashboard**
📁 `analysis/performance_report.html`

**What it shows:**

1. **Health Score Card**
   - Overall bot health (0-100)
   - Color-coded: Green = Good, Orange = Fair, Red = Issues

2. **Process Status**
   - Bot online/offline
   - PID, Uptime
   - Restart count

3. **Resource Usage**
   - Memory consumption
   - CPU usage

4. **Activity Charts** (Interactive bars):
   - Orders placed
   - Fills executed
   - Throttle activations ⚠️
   - WebSocket reconnects
   - Warnings
   - Errors

5. **Recommendations**
   - Auto-generated based on stats
   - Highlights issues needing attention

---

## 🔍 CURRENT FINDINGS (From Analysis)

### Recent Activity (Last 1000 log lines):
```
✅ BUY Orders: 2
✅ SELL Orders: 0
✅ Fills: 2
⚠️ Throttle Events: 0
⚠️ WebSocket Reconnects: [count shown in report]
```

### Critical Issues Detected:

**1. RACE CONDITION (Nov 7, 16:45)**
- Two duplicate BUY orders at $99,000
- Placed only **5 seconds apart**
- This was BEFORE throttle implementation
- ✅ **FIXED** with 30s throttle mechanism

**2. THROTTLE NOT YET ACTIVATED**
- 0 throttle events in recent logs
- This is because:
  - Bot was recently restarted
  - Not enough time has passed
  - No rapid order attempts yet
- ⏳ **PENDING VERIFICATION** - needs 24h monitoring

---

## 🎯 WHAT TO LOOK FOR IN THE VISUALS

### In Timeline (race_condition_timeline.html):
1. **Look for RED time gaps** - These are < 10s apart (BAD)
2. **Look for ORANGE gaps** - These are < 30s apart (should see THROTTLE)
3. **Check sequence** - Fill → TP → Next Order should have gaps
4. **After Nov 7 20:12** - Should see throttle activations

### In Performance Report (performance_report.html):
1. **Health Score** - Should be 80+ (Green)
2. **Throttle bar** - Should show > 0 after 24 hours
3. **Errors bar** - Should be minimal
4. **WebSocket reconnects** - Track if increasing
5. **Recommendations** - Follow any warnings

---

## 📈 HOW TO USE GOING FORWARD

### Daily Monitoring:
```bash
# Refresh both visualizations
python3 generate_visual_timeline.py
python3 generate_performance_report.py
```

### Real-Time Monitoring:
```bash
# Watch for throttle in action
./analyze_throttle.sh   # Then choose 'y' for real-time

# See this pattern in logs:
# 🚦 THROTTLE: Last BUY order was 15.2s ago (min: 30s)
# ✅ BUY order placed @ $99,000 (ID: ...)
```

### Profiling Performance:
```bash
# Quick 30-second profile
./profile_bot.sh   # Choose option 1

# Real-time CPU monitoring
sudo /Users/ssr/Library/Python/3.9/bin/py-spy top --pid $(pgrep -f "gridbot-live")
```

---

## 🚀 NEXT ACTIONS

1. **Manual TP Placement** (YOU)
   - Place TP orders for 3 orphaned positions
   - Check Delta Exchange UI for entry prices

2. **Bot Restart** (YOU)
   ```bash
   pm2 restart gridbot-live
   ```

3. **Monitor for 24 Hours** (AUTOMATIC)
   - Visualizations auto-refresh
   - Watch for THROTTLE activations
   - Verify no duplicate orders

4. **Daily Check**
   ```bash
   # Run these each morning:
   python3 generate_visual_timeline.py
   python3 generate_performance_report.py
   ./detect_race_conditions.sh
   ```

---

## 📁 ALL VISUALIZATION FILES

Located in: `~/Projects/WorkingBot/analysis/`

**Generated files:**
- `race_condition_timeline.html` - Event timeline
- `performance_report.html` - Health dashboard
- `flame_*.svg` - Performance flame graphs (when py-spy works)

**Auto-refresh:**
- Timeline: Every 30 seconds
- Performance: Every 60 seconds

---

## ✅ VERIFICATION CHECKLIST

After bot restart with throttle:

- [ ] Open both HTML files in browser
- [ ] See THROTTLE events appearing in timeline (within 24h)
- [ ] Health score stays above 80
- [ ] No RED time gaps (< 10s)
- [ ] All ORANGE gaps (< 30s) should have THROTTLE marker
- [ ] Orders placed show proper 30s+ spacing

---

## 🎨 VISUAL LEGEND

**Timeline Colors:**
- 🟢 = BUY order placed
- 🔴 = SELL order placed
- 🔵 = Fill executed
- 🟠 = THROTTLE activated (30s enforcement)
- 🟣 = TP order placed

**Time Gap Colors:**
- 🔴 Red flash = < 10s (CRITICAL - should not happen)
- 🟠 Orange = 10-30s (WARNING - throttle should activate)
- ⚪ Gray = > 30s (NORMAL)

**Health Score:**
- 🟢 80-100 = Excellent
- 🟡 60-79 = Fair
- 🔴 < 60 = Needs attention

---

**These visualizations update in real-time** - keep browser tabs open!


---

