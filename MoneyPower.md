This algorithm that I am going to plan is called "Money Power". This strategy is for the DTE selected by the user. Mostly 0DTE but he can select any expiry that he wants by using webUI. This is not a momentum based strategy. This strategy is based on time decays as well as power of money and mathematical calculations.
This is not very complex strategy, it has very simple rules for calculations. 
Let's say on some expiry the user has sold 
10 lots of X strike CE at 100 premium so the total premium collected is  10*100 = 1000.
at the same time the user has sold 10 lots of Y strike PE at 100 premium so the total premium collected is 10*100 = 1000.

So the total premium collected is 2000. 
This strategy will do adjustment after every 5 minutes or the time defined by the user. He will have hot reload option to change the time of adjustment or trigger the adjustment instantly. But the algo keeps on going on and on until the expiry or until the user stops it.
The adjustment will be done by selling the same strike CE and PE that he has sold.
The algo will not trigger any adjustment if both CE and PE are below the entry price in our example below 100.
The algo will trigger the adjustment if any of the CE or PE is above the entry price in our example above 100. 
If for 5 minutes any of the CE or PE is above the entry price then the algo will trigger the adjustment automatically.
For example if CE is at 120, so PE will be obviously below 100, so the algo will do the following calculations:
CE premium value = 120*10 = 1200
PE premium value = 100*10 = 1000
so the difference is 200.
Now algo will look at the price of PE options let's say it is trading at 80, so the algo will calculate how many lots of PE we can sell more to cover the difference of 200.
So the algo will calculate 200/80 = 2.5 lots (round up to the nearest lot size) so it will sell 3 lots of PE at 80 to cover the difference of 200.
After this adjustment 
CE position collected premium = 100*10 = 1000
CE position loss = 20*10 = 200
This loss is covered by the premium collected from selling 3 lots of PE at 80 which is 80*3 = 240.
So after this adjustment the loss in CE position is covered by the premium collected from selling 3 lots of PE at 80.

Now we don't care anymore about going the CE to 120 because we have already covered the loss by selling more PE.
Now the algo will keep monitoring CE and PE price and will not trigger any adjustment if CE is below 120 and PE is below 80.

Let's say after 5 minutes CE is at 130 and PE is at 70, so the algo will do the following calculations:
CE premium value = 100*10 = 1000
CE position loss = 20*10 = 200  already covered by selling 3 lots of PE at 80 which is 240.
The new loss in CE position is (130-120)*10 = 100.
Now the algo will look at the price of PE options let's say it is trading at 70, so the algo will calculate how many lots of PE we can sell more to cover the difference of 100.
So the algo will calculate 100/70 = 1.42 lots (round up to the nearest lot size) so it will sell 2 lots of PE at 70 to cover the difference of 100.
After this adjustment               
CE position collected premium = 100*10 = 1000
CE position loss = 30*10 = 300 already covered by selling 3 lots of PE at 80 which is 240 and selling 2 lots of PE at 70 which is 140 so total premium collected from selling PE is 240 + 140 = 380 which is more than the loss of 300 in CE position.
total premium collected from PE = 100*10 + 80*3 + 70*2 = 1000 + 240 + 140 = 1380. 
Now the possible loss of CE positions is completely covered by the premium collected from selling PE options.
Now the algo will keep monitoring CE and PE price and will not trigger any adjustment if CE is below 130 and PE is below 70.
If after 5 minutes CE is at 140 and PE is at 60, so the algo will do the following calculations:
CE premium value = 100*10 = 1000
CE position loss = 40*10 = 400 already covered by selling 3 lots of PE at 80 which is 240 and selling 2 lots of PE at 70 which is 140 so total premium collected from selling PE is 240 + 140 = 380.
The new loss in CE position is (140-130)*10 = 100.
Now the algo will look at the price of PE options let's say it is trading at 60, so the algo will calculate how many lots of PE we can sell more to cover the difference of 100.
So the algo will calculate 100/60 = 1.66 lots (round up to the nearest lot size) so it will sell 2 lots of PE at 60 to cover the difference of 100.
After this adjustment               
CE position collected premium = 100*10 = 1000
CE position loss = 40*10 = 400 already covered by selling 3 lots of PE at 80 which is 240 and selling 2 lots of PE at 70 which is 140 and selling 2 lots of PE at 60 which is 120 so total premium collected from selling PE is 240 + 140 + 120 = 500 which is more than the loss of 400 in CE position.
total premium collected from PE = 100*10 + 80*3 + 70*2 + 60*2 = 1000 + 240 + 140 + 120 = 1500. 
Now the possible loss of CE positions is completely covered by the premium collected from selling PE options.
Now the algo will keep monitoring CE and PE price and will not trigger any adjustment if CE is below 140 and PE is below 60.
This process will keep on going on and on until the expiry or until the user stops it.

This is the adjustment when market was going in one direction which was up. 
Now we have the following open position:
- Sold 10 lots of X strike CE at 100 premium
- Sold 10 lots of Y strike PE at 100 premium
- Sold 3 lots of Y strike PE at 80 premium
- Sold 2 lots of Y strike PE at 70 premium
- Sold 2 lots of Y strike PE at 60 premium

So the average price of CE position is 100 and the average price of PE position is (100*10 + 80*3 + 70*2 + 60*2) / (10 + 3 + 2 + 2) = 1500 / 17 = 88.23.    
Now if the market starts going down and PE price starts increasing and CE price starts decreasing, the algo will trigger the adjustment only when PE price is above the average price of the additional PE position, which is 84.28. This protects the additional risk created by selling PE options at 80, 70, and 60 to cover CE losses. To do this, the algo will sell more CE options.

Let's say after 5 minutes PE price reaches 100. 
So the algo will do the following calculations:
additional PE position loss = (100 - 84.28) * 7 = 115.96
Now the algo will look at the price of CE options and calculate how many lots of CE we can sell to cover the loss of 115.96 in additional PE position.
Let's say CE price is at 90, so the algo will calculate 115.96 / 90 = 1.28 lots (round up to the nearest lot size) so it will sell 2 lots of CE at 90 to cover the loss of 115.96 in additional PE position.
After this adjustment 
CE position collected premium = 100*10 + 90*2 = 1000 + 180 = 1180
PE position collected premium = 100*10 + 80*3 + 70*2 + 60*2 = 1500
now algo will keep monitoring the CE and PE prices for next 5 minutes and if after 5 minutes let's say PE price is at 120 and CE price is at 80, so the algo will do the following calculations:
PE position loss in original PE position = (120 - 100) * 10 = 200
PE side loss in additional PE position created to cover the CE position loss = (120 - 100) * 7 = 140 
so total loss in PE position is 200 + 140 = 340.
Now the algo will look at the price of CE options and calculate how many lots of CE we can sell to cover the loss of 340 in PE position.   
Let's say CE price is at 80, so the algo will calculate 340 / 80 = 4.25 lots (round up to the nearest lot size) so it will sell 5 lots of CE at 80 to cover the loss of 340 in PE position.
After this adjustment
CE position collected premium = 100*10 + 90*2 + 80*5 = 1180 + 400 = 1580
PE position collected premium = 100*10 + 80*3 + 70*2 + 60*2 = 1500
now the algo will keep monitoring the CE and PE prices for next 5 minutes and if after 5 minutes the CE price is below 80 and PE price is below 120, so the algo will not trigger any adjustment because the loss in PE position is already covered by the premium collected from selling CE options.
Let's say after 5 minutes CE price is at 70 and PE price is at 130, so the algo will do the following calculations:
PE position loss in original PE position = (130 - 120) * 10 = 100
PE side loss in additional PE position created to cover the CE position loss = (130 - 120) * 7 = 70 
so total loss in PE position is 100 + 70 = 170.
Now the algo will look at the price of CE options and calculate how many lots of CE we can sell to cover the loss of 170 in PE position.           
Let's say CE price is at 70, so the algo will calculate 170 / 70 = 2.42 lots (round up to the nearest lot size) so it will sell 3 lots of CE at 70 to cover the loss of 170 in PE position.
After this adjustment
CE position collected premium = 100*10 + 90*2 + 80*5 + 70*3 = 1580 + 210 = 1790
PE position collected premium = 100*10 + 80*3 + 70*2 + 60*2 = 1500
now the algo will keep monitoring the CE and PE prices for next 5 minutes and if after 5 minutes the CE price is below 70 and PE price is below 130, so the algo will not trigger any adjustment because the loss in PE position is already covered by the premium collected from selling CE options.
This process will keep on going on and on until the expiry or until the user stops it.
now we have following postions:
- Sold 10 lots of X strike CE at 100 premium  
