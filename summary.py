import time
from utils import now, yellow, green
import datetime
LOGPATH = 'local/%s.log'%(now('%Y-%m'))

def timestamp_2_str(timestamp, fmt = "%Y-%m-%d"):
    return str(datetime.datetime.fromtimestamp(timestamp).strftime(fmt))

sold_buf = []
balance = {}
total_earn, total_cnt = 0, 0
for line in open(LOGPATH, 'r'):
    timestamp = line[:11]
    line = line[11:].strip()
    if line.startswith('Sold'):
        _, sym, price, qty, earn = line.split(' ')
        total_earn += float(earn)
        total_cnt += 1
        sold_buf.append((int(timestamp), sym, price, qty, earn))
    
#     if line.startswith('Balance'):
#         _, usd, eth = line.split(' ')
#         usd = float(usd)
#         if eth in balance.keys():
#             balance[eth].append(usd - balance[eth][0])
#         else:
#             balance[eth] = [usd]

start_time = sold_buf[0][0]
d_earn = 0
d_cnt = 0
d_vol = 0
d_count = 1

for timestamp, sym, price, qty, earn in sold_buf:
    d_vol += float(price) * float(qty)
    if (timestamp - start_time)/60/60/24 > 1:
        d_count += 1
        s_time = timestamp_2_str(start_time)
        print(yellow(s_time), '%4d'%(d_cnt), green("$%.2f"%(d_earn)), '%.3f, %.0f'%(d_earn/d_cnt, d_vol))
        start_time =  timestamp
        d_earn = 0
        d_cnt = 0
        d_vol = 0

    d_earn += float(earn)
    d_cnt += 1

s_time = timestamp_2_str(start_time)
print(yellow(s_time) + '*%4d'%(d_cnt), green("$%.2f"%(d_earn)), '%.3f, %.0f'%(d_earn/d_cnt, d_vol))

print('total earn: $%.1f, per day $%.1f, per month $%.1f'%(total_earn, total_earn/d_count, total_earn/d_count*30))
print('total match: %d, per day %.0f'%(total_cnt, total_cnt/d_count))
print('avg earn per match: %.3f'%(total_earn/total_cnt))