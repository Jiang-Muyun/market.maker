import os
import time
import json
import datetime

def bold(x):       return '\033[1m'  + str(x) + '\033[0m'
def dim(x):        return '\033[2m'  + str(x) + '\033[0m'
def italicized(x): return '\033[3m'  + str(x) + '\033[0m'
def underline(x):  return '\033[4m'  + str(x) + '\033[0m'
def blink(x):      return '\033[5m'  + str(x) + '\033[0m'
def inverse(x):    return '\033[7m'  + str(x) + '\033[0m'
def gray(x):       return '\033[90m' + str(x) + '\033[0m'
def red(x):        return '\033[91m' + str(x) + '\033[0m'
def green(x):      return '\033[92m' + str(x) + '\033[0m'
def yellow(x):     return '\033[93m' + str(x) + '\033[0m'
def blue(x):       return '\033[94m' + str(x) + '\033[0m'
def magenta(x):    return '\033[95m' + str(x) + '\033[0m'
def cyan(x):       return '\033[96m' + str(x) + '\033[0m'
def white(x):      return '\033[97m' + str(x) + '\033[0m'

# ------------------------------ Timing -----------------------------------------

def macOS_Notify(title, text):
    os.system("""
              osascript -e 'display notification "{}" with title "{}"'
              """.format(text, title))

class AutoDelay():
    def __init__(self, note='', totelSeconds = 1, show=True):
        self.totelSeconds = totelSeconds
        self.note = note
        self.show = show

    def __enter__(self):
        self.t_start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        delta = time.time()-self.t_start
        if delta < self.totelSeconds:
            sleepSec = self.totelSeconds - delta
            if self.show:
                print(self.note, yellow('wait:%.3fs'%(sleepSec)))
            time.sleep(sleepSec)
        else:
            sleepSec = 0
            if self.show:
                print(self.note, yellow('cost:%.3fs'%(delta)))

class Tick():
    def __init__(self, name='', silent=False):
        self.name = name
        self.silent = silent

    def __enter__(self):
        self.t_start = time.time()
        if not self.silent:
            print('%s ' % (self.name), end='', flush=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.t_end = time.time()
        self.delta = self.t_end-self.t_start
        self.fps = 1/self.delta

        if not self.silent:
            print(yellow('[%.3fs]' % (self.delta), ), flush=True)

class Tock():
    def __init__(self, name=None, report_time=True):
        self.name = '' if name == None else name+':'
        self.report_time = report_time

    def __enter__(self):
        self.t_start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.t_end = time.time()
        self.delta = self.t_end-self.t_start
        self.fps = 1/self.delta
        if self.report_time:
            print(yellow(self.name)+cyan('%.3fs'%(self.delta)), end=' ', flush=True)
        else:
            print(yellow('.'), end='', flush=True)

def now(fmt = "%Y-%m-%d %H:%M:%S"):
    return str(datetime.datetime.now().strftime(fmt))

def fmtPrice(price, priceDecimal):
    priceFmt = '%%.%df'%(priceDecimal)
    return priceFmt%(price)

def fmtQty(qty, qtyDecimal):
    qtyFmt = '%%.%df'%(qtyDecimal)
    return qtyFmt%(qty)
