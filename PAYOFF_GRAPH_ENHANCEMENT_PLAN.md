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
