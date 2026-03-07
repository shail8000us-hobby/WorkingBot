In this file I am going to logic and algoritham rules of new algo execution. This will be used as a reference for implementation and testing.
Following will be the entry rules for the algo execution:
A. This algo will be dedicated to BTC option only for now. We will add support for other assets in future.
B. This will be designed and coded as per delta exchange india rules and API. 
C. This will be designed to work with both CE and PE options.
D. This will be designed to work with both buy and sell orders.
E. This will be designed to work with multiple rounds of execution, by using autoloop mechanism. The number of rounds and quantity ratio will be configurable by user.
F. This will be designed to handle partial fills and cancellations gracefully, by using polling mechanism to check order status before starting next round.
G. This will be designed to provide clear progress indicators for each round and each order, so that user can monitor the execution and intervene if needed.
H. This will be designed to log detailed execution flow for debugging and audit purposes.
I. This will be designed to have a "Stop" button that allows user to gracefully halt the execution after current round completes.
J. This will be designed to have a maximum of 2-second delay between rounds, to allow for API calls and status updates.
K. The expiry date for the options will be determined based on user input and available strikes, and will be passed to the API for order placement.
L. This algo strategy will be designed to run automatically without user intervention after it starts, until all rounds are completed or user stops it.
M. This will be designed to handle the mid price order type for better fill probability, this will execute multiple rounds of orders by using autoloop mechanism as per the rules. Since delta exchange india does not have enough liquidity so we will execute multiple rounds of orders by using autoloop mechanism. This will be the strict rule that next round of auto-loop will only start after all orders in the current round are confirmed filled, this will prevent any race conditions and ensure proper execution flow. 
N. 