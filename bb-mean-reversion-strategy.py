"""
Author: www.backtest-rookies.com

MIT License

Copyright (c) 2018 backtest-rookies.com

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


import backtrader as bt
import datetime
import os.path
import sys


class BBMRStrategy(bt.Strategy):
    """
    Source: https://backtest-rookies.com/2018/02/23/backtrader-bollinger-mean-reversion-strategy/

    This is a simple mean reversion bollinger band strategy.

    Entry Criteria:
        - Long:
            - Price closes below the lower band
            - Stop Order entry when price crosses back above the lower band
        - Short:
            - Price closes above the upper band
            - Stop order entry when price crosses back below the upper band
    Exit Criteria
        - Long/Short: Price touching the median line
    """

    params = (
        ("period", 20),
        ("stddev", 2),
        ("debug", True)
    )

    def log(self, txt, dt=None, tm=None, doprint=False):
        """ Logging function for this strategy """
        if self.params.debug or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            tm = tm or self.datas[0].datetime.time(0)
            print('%s %s, %s' % (dt.isoformat(), tm.isoformat(), txt))

    def print_ohlc(self):
        txt = list()
        dtfmt = '%Y-%m-%dT%H:%M'
        txt.append('%s' % self.data.datetime.datetime(0).strftime(dtfmt))
        txt.append('{}'.format(self.data.open[0]))
        txt.append('{}'.format(self.data.high[0]))
        txt.append('{}'.format(self.data.low[0]))
        txt.append('{}'.format(self.data.close[0]))
        txt.append('{}'.format(self.data.volume[0]))
        self.log(', '.join(txt))

    def __init__(self):
        self.boll = bt.indicators.BollingerBands(period=self.p.period, devfactor=self.p.stddev)
        self.bar_executed = None

        self.entry_order = None
        self.profit_order = None

    def next(self):

        # self.print_ohlc();

        if self.entry_order:
            if self.entry_order.status in [self.entry_order.Accepted]:
                self.broker.cancel(self.entry_order)
            self.entry_order = None

        if self.profit_order:
            self.broker.cancel(self.profit_order)
            self.profit_order = None

        if not self.position:

            if self.data.close > self.boll.lines.top:
                self.log('SIGNAL:ENTRY Sell :  Close %.2f, BB Top %.2f' % (self.data.close[0], self.boll.lines.top[0]))
                self.entry_order = self.sell(exectype=bt.Order.Stop, price=self.boll.lines.top[0], transmit=True)
            if self.data.close < self.boll.lines.bot:
                self.log('SIGNAL:ENTRY Buy :  Close %.2f, BB Bot %.2f' % (self.data.close[0], self.boll.lines.bot[0]))
                self.entry_order = self.buy(exectype=bt.Order.Stop, price=self.boll.lines.bot[0], transmit=True)
        else:
            if self.position.size > 0:
                self.log('SIGNAL:EXIT, SELL :  BB Mid %.2f' % (self.boll.lines.mid[0]))
                self.profit_order = self.sell(exectype=bt.Order.Limit, price=self.boll.lines.mid[0], transmit=True)
            else:
                self.log('SIGNAL:EXIT, BUY :  BB Mid %.2f' % (self.boll.lines.mid[0]))
                self.profit_order = self.buy(exectype=bt.Order.Limit, price=self.boll.lines.mid[0], transmit=True)

    def notify_order(self, order):

        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        if order.status in [order.Expired]:
            self.log('BUY EXPIRED')

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    'BUY EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                    (order.executed.price,
                     order.executed.value,
                     order.executed.comm), doprint=True)

            else:  # Sell
                self.log('SELL EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                         (order.executed.price,
                          order.executed.value,
                          order.executed.comm), doprint=True)

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
            return

        if self.entry_order:
            if self.entry_order.status in [self.entry_order.Completed]:
                self.log('ENTRY ORDER EXECUTED')
                # self.entry_order = None

        if self.profit_order:
            if self.profit_order.status in [self.profit_order.Completed]:
                self.log('PROFIT ORDER EXECUTED')
                self.profit_order = None

    def notify_trade(self, trade):

        if not trade.isclosed:
            return

        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' % (trade.pnl, trade.pnlcomm), doprint=True)

        if trade.isclosed:
            dt = self.data.datetime.datetime()
            current_bar_idx = len(trade.data)
            trade_open_bar_idx = (trade.baropen - current_bar_idx)
            trade_close_bar_idx = (trade.barclose - current_bar_idx)
            trade_open_dt = bt.num2date(self.data.datetime[trade_open_bar_idx])
            trade_close_dt = bt.num2date(self.data.datetime[trade_close_bar_idx])

            self.log('Trade Stats - Open: %s, Close: %s, Bars: %d PnL: %.2f \n'
                     % (trade_open_dt, trade_close_dt, trade.barlen, trade.pnl), doprint=True)


def get_data(file_name, start_date=None, end_date=None, volume=5):
    base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    data = bt.feeds.GenericCSVData(
        dataname=os.path.join(base_path, 'data/' + file_name + '.txt'),
        fromdate=start_date,
        todate=end_date,
        timeframe=bt.TimeFrame.Minutes,
        dtformat='%Y%m%d %H%M%S',
        separator=';',
        datetime=0,
        time=-1,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=volume,
        openinterest=-1)

    return data


if __name__ == '__main__':
    # Variable for our starting cash
    startcash = 500000

    # Create an instance of cerebro
    cerebro = bt.Cerebro()

    # Add our strategy
    cerebro.addstrategy(BBMRStrategy, period=20, debug=False)

    # data = get_data('NIFTY1902', datetime.datetime(2019, 1, 29, 9, 15, 0), datetime.datetime(2019, 2, 4, 13, 30, 0))
    data = get_data('NIFTY1902', start_date=datetime.datetime(2019, 1, 29, 9, 15, 0), end_date=datetime.datetime(2019, 2, 28, 15, 30, 0))

    # Add the data to Cerebro
    # cerebro.adddata(data)

    # Resample 1min to 15mins
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Minutes, compression=60, boundoff=-15)

    cerebro.broker.setcash(startcash)

    # Add a sizer
    # cerebro.addsizer(bt.sizers.FixedSize, stake=1)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=15)

    # Set the commission - 0.1% ... divide by 100 to remove the %
    # cerebro.broker.setcommission(commission=0.01)
    cerebro.broker.setcommission(commission=75, margin=35000.0, mult=75.0)

    # Run over everything
    cerebro.run()

    # Get final portfolio Value
    portvalue = cerebro.broker.getvalue()
    pnl = portvalue - startcash

    # Print out the final result
    print('Final Portfolio Value: INR {}'.format(round(portvalue, 2)))
    print('P/L: INR {}'.format(round(pnl, 2)))

    # Finally plot the end results
    cerebro.plot(style='bar', volume=False)