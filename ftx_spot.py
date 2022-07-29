import os
import hmac
import json
import random
import time
import math
import asyncio
import argparse
import uuid
import ccxt
import websockets
import traceback
from utils import red, green, blue, cyan, yellow, gray, now, Tick, Tock

LOGPATH = 'local/%s.log'%(now('%Y-%m'))
def logError(text):
    text = '%d [ERROR %s %s] %s'%(int(time.time()), now(), args.pair, text)
    print(red(text))
    with open(LOGPATH, 'a+') as fp:
        fp.write(text+'\n')

def logInfo(text):
    text = '%d %s'%(int(time.time()), text)
    print(now(), text)
    with open(LOGPATH, 'a+') as fp:
        fp.write(text+'\n')

def logOnly(text):
    print(gray(now() + ' ' + text))

def snap_to_grid(num, distance):
    _ = num % distance
    if _ > distance /2:
        num += (distance - _)
    else:
        num -= _
    return num

class FTX_Spot:

    def __init__(self, symbol, subaccount, API_KEY, API_SEC):
        self.symbol = symbol # baseCurrency/quoteCurrency
        self.subaccount = subaccount
        self.echo = True
        self.API_KEY = API_KEY
        self.API_SEC = API_SEC

        self.init_symbol(symbol)
        self.t_lastReq = time.time()
        self.ftx = ccxt.ftx({
            'apiKey': API_KEY,
            'secret': API_SEC,
            'enableRateLimit': True,
            'headers': {'FTX-SUBACCOUNT': subaccount}
            }
        )

    def init_symbol(self, symbol):
        os.makedirs('/tmp/FTX_INFO', exist_ok=True)
        cache = '/tmp/FTX_INFO/%s.json'%(symbol.replace('/', ''))
        if not os.path.exists(cache):
            ftx = ccxt.ftx()
            FTX_Ticker = ftx.fetch_ticker(symbol)['info']
            with open(cache, 'w') as fp:
                json.dump(FTX_Ticker, fp, indent=4)
        else:
            with open(cache, 'r') as fp:
                FTX_Ticker = json.load(fp)
        
        self.baseCurrency = FTX_Ticker['baseCurrency']
        self.COIN = self.baseCurrency
        self.quoteCurrency = FTX_Ticker['quoteCurrency']
        self.USD = self.quoteCurrency
        self.priceIncrement = float(FTX_Ticker['priceIncrement'])
        self.sizeIncrement = float(FTX_Ticker['sizeIncrement'])
        self.minProvideSize = float(FTX_Ticker['minProvideSize'])

        if self.sizeIncrement >= 1:
            self.qtyDecimal = 1
        else:
            self.qtyDecimal = math.ceil(abs(math.log10(self.sizeIncrement)))
        self.qtyFmt = '%%.%df'%(self.qtyDecimal)
    
        self.priceDecimal = math.ceil(abs(math.log10(self.priceIncrement)))
        self.priceFmt = '%%.%df'%(self.priceDecimal)
    
    def fmtQty(self, qty):
        qty = float(qty)
        if qty < self.minProvideSize:
            raise ValueError('qty < minProvideSize')
        quotient = qty // self.sizeIncrement
        qty = quotient * self.sizeIncrement
        return self.qtyFmt % (qty)
    
    def fmtPrice(self, price):
        price = float(price)
        quotient = price // self.priceIncrement
        price = quotient * self.priceIncrement
        return self.priceFmt % (price)

    def WS_LOGIN(self):
        t = int(time.time() * 1000)
        LOGIN = {'op': 'login', 'args': {
                'key': self.API_KEY,
                'subaccount' : self.subaccount,
                'sign': hmac.new(self.API_SEC.encode(), f'{t}websocket_login'.encode(), 'sha256').hexdigest(),
                'time': t,
        }}
        return LOGIN
    
    def WS_SUBSCRIBE(self):
        return {"op": "subscribe", "channel": "orders"}
    
    def WS_PING(self):
        return {'op': 'ping'}

    def assure_200ms_limit(self):
        while time.time() - self.t_lastReq < 0.2:
            time.sleep(0.05)
        self.t_lastReq = time.time()

    def limit_order(self, side, qty, price):
        self.assure_200ms_limit()
        price = self.fmtPrice(price)
        if self.echo:
            logOnly('Place order %s %s %s %s'%(side, self.symbol, qty, price))
        try:
            params = {'clientId':'bot-%s'%(str(uuid.uuid4())[24:])}
            res = self.ftx.create_order(self.symbol, 'limit', side, qty, price=price, params=params)
            return res['info']
        except Exception as err:
            logError('limit_order %s %s'%(self.symbol, str(err)))
            return None

    def cancel_order(self, oid):
        self.assure_200ms_limit()
        try:
            return self.ftx.cancel_order(oid)
        except Exception as err:
            logError('Cancel order error %s'%(str(err)))
            return None

    def cancel_all_orders(self):
        self.assure_200ms_limit()
        return self.ftx.cancel_all_orders(symbol=self.symbol)

    def fetch_ticker(self):
        self.assure_200ms_limit()
        return self.ftx.fetch_ticker(self.symbol)['info']

    def fetch_open_orders(self):
        self.assure_200ms_limit()
        return self.ftx.fetch_open_orders(self.symbol)

    def fetch_balance(self):
        self.assure_200ms_limit()
        return self.ftx.fetch_balance()


async def check_websocket(exchange, websocket):
    try:
        raw_message = await asyncio.wait_for(websocket.recv(), timeout=0.02)
    except asyncio.TimeoutError:
        return

    if raw_message == None:
        return
    message = json.loads(raw_message)

    if message['type'] in ['pong']:
        return
    if message['type'] in ['subscribed', 'unsubscribed']:
        logOnly('websocket recv: %s'%(message))
        return
    elif message['type'] == 'info':
        logOnly('websocket info type message: %s'%(message))
        return
    elif message['type'] == 'error':
        logError('websocket error type message: %s'%(message))
        raise Exception(message)

    if message['channel'] == 'orders':

        order = message['data']
        if order['market'] != exchange.symbol:
            return
        
        if order['clientId'] == None or not order['clientId'].startswith('bot'):
            logInfo('Found FILLED order not placed by me %s'%(str(order)))
            return

        if order['status'] == 'closed' and order['avgFillPrice'] != None:
            mkt = order['market']
            last_price = float(order['price'])
            last_price = snap_to_grid(last_price, args.distance)
            if order['side'] == 'buy':
                logInfo('Bought %s %s %s'%(mkt, order['price'], order['size']))
                exchange.limit_order('sell', args.qty, last_price + args.distance)
            else:
                earn = float(order['size']) * args.distance
                logInfo('Sold %s %s %s %.3f'%(mkt, order['price'], order['size'], earn))
                exchange.limit_order('buy', args.qty, last_price - args.distance)
    
    elif message['channel'] == 'orderbook':
        pass
    elif message['channel'] == 'trades':
        pass
    elif message['channel'] == 'ticker':
        pass
    elif message['channel'] == 'fills':
        pass

async def curr_orders_scan(exchange, websocket):
    open_orders = []
    for order in exchange.fetch_open_orders():
        order = order['info']
        if order['clientId'] == None or not order['clientId'].startswith('bot'):
            logError('Found OPEN order not placed by me. %s'%(str(order)))
            # exchange.cancel_order(order['id'])
            continue
        open_orders.append([order['id'], order['side'], float(order['price'])])

    open_orders.sort(key= lambda x: x[2], reverse=True)
    sells, buys = [], []
    for oid, label, price in open_orders:
        if label == 'sell':
            sells.append([oid, label, price])
        else:
            buys.append([oid, label, price])

    num_holes = 0
    super_large_gap = False
    for i in range(len(open_orders)-1):
        _, _, price1 = open_orders[i]
        _, _, price2 = open_orders[i+1]
        reletive_distance = abs(price1-price2)
        if reletive_distance > 1.5 * args.distance:
            num_holes += 1
            if num_holes >= 2:
                logError('Found more %s holes, distance %.4f'%(num_holes, reletive_distance))
                
        if reletive_distance > 2.5 * args.distance:
            super_large_gap = True
            logError('Found super large gap, distance %.4f'%(reletive_distance))

    if num_holes >= 2 or super_large_gap:
        logError('Grid state error, cancel all orders')
        exchange.cancel_all_orders()
        open_orders = []
        sells,buys = [], []

    # init all !
    if len(sells) == 0 or len(buys) == 0:
        exchange.cancel_all_orders()
        price_str = exchange.fetch_ticker()['price']
        last_price = snap_to_grid(float(price_str), args.distance)
        for i in range(1, args.numOpenOrders + 1):
            exchange.limit_order('sell', args.qty, last_price + i*args.distance)
            await check_websocket(exchange, websocket)
            exchange.limit_order('buy' , args.qty, last_price - i*args.distance)
            await check_websocket(exchange, websocket)
    else:    
        # cancel extra orders
        while len(sells) > args.numOpenOrders + args.numExtraOrders:
            to_cancel = sells.pop(0)
            logOnly('cancel order %s'%(str(to_cancel)))
            exchange.cancel_order(to_cancel[0])
            await check_websocket(exchange, websocket)

        while len(buys) > args.numOpenOrders + args.numExtraOrders:
            to_cancel = buys.pop(-1)
            logOnly('cancel order %s'%(str(to_cancel)))
            exchange.cancel_order(to_cancel[0])
            await check_websocket(exchange, websocket)

        # add not enough orders
        while len(sells) < args.numOpenOrders:
            order = exchange.limit_order('sell', args.qty, sells[0][2] + args.distance)
            await check_websocket(exchange, websocket)
            if order is not None:
                sells.insert(0, [order['id'], order['side'], float(order['price'])])
            else:
                break

        while len(buys) < args.numOpenOrders:
            order = exchange.limit_order('buy', args.qty, buys[-1][2] - args.distance)
            await check_websocket(exchange, websocket)
            if order is not None:
                buys.insert(len(buys), [order['id'], order['side'], float(order['price'])])
            else:
                break

async def main_loop(exchange):

    async with websockets.connect('wss://ftx.com/ws/') as websocket:
        logOnly('Send login msg')
        await websocket.send(json.dumps(exchange.WS_LOGIN()))
        logOnly('Send subscribe msg')
        await websocket.send(json.dumps(exchange.WS_SUBSCRIBE()))

        last_ping = time.time()
        last_check = time.time() - 1000
        while True:
            if time.time() - last_ping > 15:
                await websocket.send(json.dumps(exchange.WS_PING()))
                last_ping = time.time()
            
            if time.time() - last_check > 90:
                await curr_orders_scan(exchange, websocket)
                last_check = time.time()

            await check_websocket(exchange, websocket)

def estimate(init_price, qty, distance):
    init_price, qty = float(init_price), float(qty)
    print()
    curr, hold, spent = init_price, 0, 0
    buf = []
    for i in range(600):
        curr = curr + distance
        if curr > init_price *2:
            break
        hold = hold - qty
        spent = spent + curr*qty
        if i % 25 == 0:
            buf.append(' %+.2f%%, %.2f, %.2f, $%.1f\n'%((curr/init_price-1)*100, curr, hold, spent))
    buf.reverse()
    buf.append('%.2f%%\n'%(distance / init_price*100))
    curr, hold, spent = init_price, 0, 0
    for i in range(600):
        curr = curr - distance
        if curr < 0:
            break
        hold = hold + qty
        spent = spent - curr*qty
        if i % 25 == 0:
            buf.append(' %+.2f%% %.2f, %.2f, $%.1f\n'%((curr/init_price-1)*100, curr, hold, spent))

    for b in buf:
        print(b)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Grid Trading Bot')
    parser.add_argument('-u', '--username', type=str, default='default')
    parser.add_argument('-s', '--subaccount', type=str, default=None)
    parser.add_argument('-p', '--pair', type=str, default='BTC/USD')
    parser.add_argument('-d', '--distance', type=float, default=2.0)
    parser.add_argument('-q', '--qty', type=str, default='0.001')
    parser.add_argument('-n', '--numOpenOrders', type=int, default=6) # single side
    parser.add_argument('-N', '--numExtraOrders', type=int, default=4) # single side
    args = parser.parse_args()

    userConfigPath = 'local/%s.json'%(args.username)
    userConfig = json.load(open(userConfigPath, 'r'))

    exchange = FTX_Spot(args.pair, args.subaccount, userConfig['API_KEY'], userConfig['API_SEC'])
    exchange.cancel_all_orders()
    estimate(exchange.fetch_ticker()['price'], args.qty, args.distance)


    while True:
        time.sleep(random.random())
        try:
            asyncio.run(main_loop(exchange))
        except Exception as err:
            logError('asyncio error %s'%(str(err)))
            # with open('local/error.log', 'a+') as fp:
            #     fp.write(str(err)+'\n')
            #     fp.write(traceback.format_exc()+'\n')
            time.sleep(30 * random.random())