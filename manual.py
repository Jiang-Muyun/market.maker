import time
import json
import ccxt

userConfigPath = 'local/james.json'
userConfig = json.load(open(userConfigPath, 'r'))
API_KEY, API_SEC = userConfig['API_KEY'], userConfig['API_SEC']

ftx = ccxt.ftx({
    'apiKey': API_KEY,
    'secret': API_SEC,
    'enableRateLimit': True,
    'headers': {'FTX-SUBACCOUNT': 'Grid'}
    }
)

# res = ftx.create_order('APE/USD', 'market', 'buy', 4, price=None)
# res = ftx.create_order('LUNA/USD', 'market', 'buy', 0.5, price=None)
# res = ftx.create_order('FTT/USD', 'market', 'buy', 1, price=None)
# print(res)

