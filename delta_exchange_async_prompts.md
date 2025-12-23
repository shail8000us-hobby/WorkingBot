# Delta Exchange Async Information Request Templates

## Template 1: WebSocket API Deep Dive

```
I'm implementing production-ready async WebSocket connection for Delta Exchange (India region: wss://socket.india.delta.exchange).

Please provide comprehensive documentation on:

1. **Message Types & Structure**
   - Complete list of all message types (heartbeat, pong, success, error, etc.)
   - Full JSON structure for each message type
   - Required vs optional fields
   - Example payloads for each type

2. **Connection Lifecycle**
   - Exact sequence of connection → authentication → subscription
   - Authentication message format and HMAC signature requirements
   - Success/failure response formats
   - Connection timeout specifications

3. **Heartbeat & Keep-Alive**
   - Server heartbeat interval and timeout specifications
   - Ping/pong message format
   - How to enable heartbeat monitoring
   - What happens on heartbeat timeout

4. **Error Handling**
   - Complete list of error codes and meanings
   - Error message structure
   - Recommended recovery actions for each error type
   - Rate limiting details

5. **Subscription Management**
   - Public vs private channel authentication requirements
   - Subscription confirmation message format
   - Unsubscription process
   - Maximum number of concurrent subscriptions

6. **Performance & Limits**
   - Message rate limits
   - Connection limits per API key
   - Recommended ping/heartbeat intervals
   - Buffer sizes and queue management recommendations

7. **Reconnection Strategy**
   - Recommended backoff strategy
   - State preservation during reconnection
   - Automatic resubscription handling
   - Circuit breaker recommendations

Please provide production-ready code examples for each section using Python asyncio and websockets library.
```

---

## Template 2: Authentication Troubleshooting

```
I'm having issues with Delta Exchange WebSocket authentication for private channels.

Current setup:
- Region: India (wss://socket.india.delta.exchange)
- Library: Python websockets + asyncio
- Signature method: HMAC-SHA256

Please provide:

1. **Exact Authentication Flow**
   - Step-by-step authentication sequence
   - Exact JSON message format for auth request
   - How to construct signature (method + timestamp + path format)
   - Expected success response
   - Common authentication errors and causes

2. **Private Channel Subscriptions**
   - When can I subscribe to private channels (before/after auth)?
   - Do I need to resubscribe after reconnection?
   - Error messages for unauthorized subscriptions
   - How to verify authentication success before subscribing

3. **Troubleshooting**
   - How to debug "subscription forbidden on this channel. Unauthorized user"
   - How to verify API key permissions
   - How to test authentication in isolation

Please include working Python code examples with proper error handling.
```

---

## Template 3: Message Queue & Backpressure

```
I'm implementing message queue management for Delta Exchange WebSocket connection.

Please provide best practices for:

1. **Message Queue Design**
   - Recommended queue sizes for different message types
   - Priority queue vs single queue approach
   - When to drop messages vs block
   - Memory management strategies

2. **Backpressure Handling**
   - How to detect slow consumer
   - Strategies for handling queue overflow
   - Impact of dropped messages on trading logic
   - Flow control recommendations

3. **Message Processing**
   - Should I process messages synchronously or async?
   - Separate queues for control vs data messages?
   - Message ordering guarantees
   - Handling duplicate messages

4. **Performance Optimization**
   - Message batching strategies
   - Async iteration patterns
   - Zero-copy techniques if applicable
   - CPU vs I/O bound considerations

Please include production-ready Python asyncio code with proper error handling.
```

---

## Template 4: Circuit Breaker & Resilience

```
I need production-ready error recovery for Delta Exchange WebSocket.

Please provide implementation guidance for:

1. **Circuit Breaker Pattern**
   - Failure threshold recommendations
   - Circuit open duration
   - Half-open state testing strategy
   - Metrics to track

2. **Exponential Backoff**
   - Initial delay recommendations
   - Maximum delay cap
   - Jitter strategy (additive vs multiplicative)
   - When to reset backoff counter

3. **Error Classification**
   - Transient vs permanent errors
   - Which errors should trigger reconnect
   - Which errors should open circuit breaker
   - Which errors should alert operators

4. **Health Monitoring**
   - Key metrics to track
   - Alert thresholds
   - Health check implementation
   - Graceful degradation strategies

Please include Python code using asyncio with proper state management.
```

---

## Template 5: Performance Monitoring

```
I need comprehensive monitoring for Delta Exchange WebSocket connection.

Please provide:

1. **Key Performance Indicators**
   - What metrics should I track?
   - Acceptable ranges for each metric
   - Warning and critical thresholds
   - How to calculate message rate, latency, uptime

2. **Connection Health Metrics**
   - How to measure connection quality
   - Indicators of degraded performance
   - When to proactively reconnect
   - Network-level vs application-level metrics

3. **Business Metrics**
   - Trade execution metrics
   - Order lifecycle tracking
   - Position update latency
   - Data freshness verification

4. **Observability Implementation**
   - Log structure and levels
   - Metrics collection approach
   - How to correlate events
   - Dashboard design recommendations

Please include Python code for metrics collection and health checks.
```

---

## Template 6: Production Deployment

```
I'm deploying Delta Exchange async bot to production.

Please provide production readiness checklist and guidance for:

1. **Environment Configuration**
   - Production vs testnet configuration
   - Environment variable structure
   - Secrets management
   - Configuration validation

2. **Resource Management**
   - Memory usage expectations
   - CPU usage patterns
   - File descriptor limits
   - Database connection pooling

3. **Graceful Shutdown**
   - Signal handling (SIGTERM, SIGINT)
   - Task cancellation order
   - In-flight request handling
   - State persistence during shutdown

4. **High Availability**
   - Single instance vs multi-instance deployment
   - State synchronization between instances
   - Failover strategies
   - Zero-downtime deployment

5. **Monitoring & Alerting**
   - Critical alerts to configure
   - Log aggregation setup
   - Metrics dashboards
   - On-call runbooks

Please include Docker configuration, systemd service files, and monitoring setup code.
```

---

## How to Use These Templates

1. **Copy the relevant template** based on what information you need
2. **Customize the template** with your specific context (current implementation, issues, etc.)
3. **Submit to Delta Exchange support** or documentation
4. **Update `async_context.md`** with the received information
5. **Implement the recommendations** systematically

---

## Information Already Obtained

✅ WebSocket URL for India region  
✅ HMAC authentication signature format  
✅ Public vs private channel authentication flow  
✅ Basic message types (heartbeat, pong, success, subscriptions, error)  
✅ Subscription message format  
✅ Recommended heartbeat interval (30s) and timeout (35s)  
✅ Circuit breaker pattern recommendations  
✅ Message queue management strategies  
✅ Task lifecycle management patterns  
✅ Connection statistics tracking approach  

---

## Information Still Needed (Use Templates Above)

⏳ Complete error code reference  
⏳ Rate limiting specifications  
⏳ Maximum concurrent connections per API key  
⏳ Message ordering guarantees  
⏳ Duplicate message handling  
⏳ State preservation during reconnection  
⏳ Performance benchmarks and SLAs  
⏳ Production deployment best practices from Delta Exchange  

---

**Last Updated:** November 12, 2025  
**Maintained By:** GitHub Copilot  
**Project:** WorkingBot - AsyncGridBot
