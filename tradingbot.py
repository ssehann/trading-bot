from lumibot.brokers import Alpaca # this is out broker
from lumibot.backtesting import YahootDataBacktesting # framework for testing
from lumibot.strategies.strategy import Strategy # this is actual trading bot
from lumibot.traders import Trader # gives deployment capability
from datetime import datetime
from alpaca_trade_api import REST
from timedelta import Timedelta
from util.finbert import estimate_sentiment

API_KEY = ""
API_SECRET = ""
BASE_URL = ""

# dictionary storing your Alpaca credentials 
ALPACA_CREDS = {
    "API_KEY": API_KEY,
    "API_SECRET": API_SECRET,
    "PAPER": True
}


class MLTrader(Strategy):
    def initialize(self, symbol:str="SPY", cash_at_risk:float=.5): 
        '''
        sets up initial parameters and connect to the Alpaca API
        '''
        # symbol = unique identifier for a stock or other security
        # by default, set to SPDR S&P 500 ETF Trust
        self.symbol = symbol
        
        # sleeptime = how often your strategy should check for new trading opportunities
        self.sleeptime = "24H"
        
        # last_trade = keeps track of the most recent trade action your strat has taken
        self.last_trade = None

        # cash_at_risk = what portion of your available cash to allocate for each trade
        self.cash_at_risk = cash_at_risk

        self.api = REST(base_url=BASE_URL, key_id=API_KEY, secret_key=API_SECRET)

    def position_sizing(self):
        '''
        determine number of shares to buy by dividing the portion of cash at risk by the stock price
        '''
        cash = self.get_cash()
        last_price = self.get_last_price(self.symbol)
        quantity = round(cash * self.cash_at_risk / last_price) 

        return cash, last_price, quantity
    
    def get_dates(self):
        '''
        helper for get_news: need dynamic date based on when we're trading 
        '''
        today = self.get_datetime() # this represents the "end"
        three_days_prior = today - Timedelta(days=3) # this represents the "start"
        return today.strftime("%Y-%m-%d"), three_days_prior.strftime("%Y-%m-%d") # return as a string

    def get_news_sentiment(self):
        '''
        fetch and analyze sentiment of news headlines for the stock symbol within the given date range.
        '''
        today, three_days_prior = self.get_dates()
        news = self.api.get_news(symbol=self.symbol, start=three_days_prior, end=today)
        news = [e.__dict__["raw"]["headline"]for e in news]
        probability, sentiment = estimate_sentiment(news)

        return probability, sentiment 

    def on_trading_iteration(self): 
        '''
        execute trading logic based on sentiment and trading conditions
        '''

        # get available cash, stock price, and number of shares to buy
        cash, last_price, quantity = self.position_sizing()
        # get sentiment data - we only want to trade on strong positive or strong negative sentiment
        news_probability, news_sentiment = self.get_news_sentiment()

        if cash > last_price: # make sure we have enough cash
            if news_sentiment == "positive" and news_probability > 0.999:
                # buy new shares & sell existing shares if the last trade was a sell.
                if self.last_trade == "sell":
                    self.sell_all()
                order = self.create_order(
                    self.symbol,
                    quantity,
                    "buy",
                    type="bracket",
                    take_profit_prcie = last_price * 1.20,
                    stop_loss_price=last_price*.95
                )
                self.submit_order(order)
                self.last_trade = "buy"
            elif news_sentiment == "negative" and news_probability > 0.999:
                # sell all shares & sell existing shares if the last trade was a buy
                if self.last_trade == "buy":
                    self.sell_all()
                order = self.create_order(
                    self.symbol,
                    quantity,
                    "sell",
                    type="bracket",
                    take_profit_prcie = last_price * 0.8,
                    stop_loss_price=last_price*1.05
                )
                self.submit_order(order)
                self.last_trade = "sell"


start_date = datetime(2021, 1, 1)
end_date = datetime(2023, 12, 31)
broker = Alpaca(ALPACA_CREDS)
strategy = MLTrader(name='mlstrat', broker=broker, 
                    parameters={'symbol':"SPY",
                                'cash_at_risk':.5})

# set up backtesting to how well our strategy is doing
strategy.backtest(
    YahootDataBacktesting,
    start_date,
    end_date,
    parameters={'symbol':"SPY", 'cash_at_risk':.5}
)
