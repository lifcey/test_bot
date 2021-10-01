import config
from binance.client import Client

from datetime import datetime
import pandas as pd
import schedule
import time


#Initialise the client
client = Client(config.api_key, config.api_secret)


balance=10000.0
position_buy=0.0
position_sell=0.0
comission=0.0005 # 1=100%, 0.001=0.1%


FRST_COIN = 'DOGE'
SCND_COIN = 'USDT'
PAIR = f'{FRST_COIN}/{SCND_COIN}'
PAIR_BNC = f'{FRST_COIN}{SCND_COIN}'
AMOUNT = 20000 # Количество в DOGE с учетом плеча. Т.е. если у нас 100$, плечо 10, курс 0.25, то 100 * 10 / 0.25 = 4000

TIMEFRAME = '3m'
TREND_LIMIT = 100
PERIOD = 3

def tr(df):

    df['previous_close'] = df['close'].shift(1)
    df['high-low'] = df['high'] - df['low']
    df['high-pc'] = abs(df['high'] - df['previous_close'])
    df['low-pc'] = abs(df['low'] - df['previous_close'])
    tr = df[['high-low', 'high-pc', 'low-pc']].max(axis=1)
    return tr

def atr(df, period=14):
    df['tr'] = tr(df)
    the_atr = df['tr'].rolling(period).mean()
    return the_atr


def supertrend(df, prev_in_uptrend, period=14, atr_multiplier=3):
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = atr(df, period=period)
    df['upperband'] = hl2 + atr_multiplier * df['atr']
    df['lowerband'] = hl2 - atr_multiplier * df['atr']
    # Необходимо запоминать как минимум последнее значение каждого запроса истории
    # Иначе каждый новый запрос начинается не так как надо
    df['in_uptrend'] = prev_in_uptrend

    for current in range(1, len(df.index)):
        previous = current -1

        if df['close'][current] > df['upperband'][previous]:
            df['in_uptrend'][current] = True
        elif df['close'][current] < df['lowerband'][previous]:
            df['in_uptrend'][current] = False
        else:
            df['in_uptrend'][current] = df['in_uptrend'][previous]

            if df['in_uptrend'][current] and df['lowerband'][current] < df['lowerband'][previous]:
                df['lowerband'][current] = df['lowerband'][previous]

            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df['upperband'][current] = df['upperband'][previous]
    return df


is_in_long_position = False
current_order = {}


'''Закрывает любую текущую позицию'''
def close_current_order(df):

    global is_in_long_position
    global position_buy, position_sell, balance

    if (is_in_long_position):
        print("Мы в длинной позиции, поэтому закрываем длинные позиции")
        position_buy=AMOUNT*df['close'][my_index]
        print(f'Продаем лонг: {position_buy}')
        balance = balance + (1-comission)*position_buy
        position_buy=0
        print('-----------------------------------------------------------------------------------------------')
        print(f'balance: {balance}')
    else:
        print("Мы в короткой позиции, поэтому закрываем короткие позиции")
        position_sell=AMOUNT*df['close'][my_index]
        print(f'Откупаем шорт: {position_sell}')
        balance = balance - (1+comission)*position_sell
        position_sell=0
        print('-----------------------------------------------------------------------------------------------')
        print(f'balance: {balance}')
    print('-----------------------------------------------------------------------------------------------')


'''Выдает сигналы покупать или продавать'''
def check_buy_sell_signals(df,my_prev_index,my_index):

    global is_in_long_position
    global position_buy, position_sell, balance
    
    last_row_index = my_index
    prev_row_index = my_prev_index
 
    if not df['in_uptrend'][prev_row_index] and df['in_uptrend'][last_row_index]:
        print('{0} long/short_signal: {1}'.format(df['timestamp'][my_index],df['in_uptrend'][last_row_index]))
        print("Функция check_buy_sell_signals() - Сигнал на ПОКУПКУ")

        if not is_in_long_position:
            close_current_order(df)
            print("Выставляем заявку в ЛОНГ")
            position_buy=AMOUNT*df['open'][my_index]
            print(f'position_buy: {position_buy}')
            print()
            balance=balance-(1+comission)*position_buy
            is_in_long_position = True
        else:
            print('already in long position, nothing to do')
            print()


    if df['in_uptrend'][prev_row_index] and not df['in_uptrend'][last_row_index]:
        print('{0} long/short_signal: {1}'.format(df['timestamp'][my_index],df['in_uptrend'][last_row_index]))
        print("Функция check_buy_sell_signals() - Сигнал на ПРОДАЖУ")

        if is_in_long_position:
            close_current_order(df)
            print("ВЫСТАВЛЯЕМ ЗАЯВКУ В ШОРТ")
            position_sell=AMOUNT*df['open'][my_index]
            print(f'position_sell: {position_sell}')
            print()
            balance = balance + (1-comission)*position_sell
            is_in_long_position = False
        else:
            print('already in short position, nothing to do')
            print()


pd.set_option('display.max.rows', None)


def init_bot():
    global current_order
    global is_in_long_position
    global position_buy, position_sell, balance
    global prev_in_uptrend
    #print(f'Fetching new bars for {datetime.now().isoformat()}')

    df = pd.DataFrame(candles , columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    supertrend_data = supertrend(df, prev_trend, period=PERIOD)
    #last_row_index = len(df.index) - 1
    #print(df['in_uptrend'][last_row_index])
    #close_current_order(df) ???????????????????????????????????????????????????????????????????????????????

    if df['in_uptrend'][0]:#[last_row_index]:
        position_buy=AMOUNT*df['high'][0]
        balance=balance-(1+comission)*position_buy
        is_in_long_position = True
        print('{0} long/short_signal: {1}'.format(df['timestamp'][0],df['in_uptrend'][0]))
        print(f'position_buy: {position_buy}, position_sell: {position_sell}')


    if not df['in_uptrend'][0]:#[last_row_index]:
        position_sell=AMOUNT*df['low'][0]
        balance = balance + (1-comission)*position_sell
        is_in_long_position = False
        print('{0} long/short_signal: {1}'.format(df['timestamp'][0],df['in_uptrend'][0]))
        print(f'position_buy: {position_buy}, position_sell: {position_sell}')

    prev_in_uptrend=df['in_uptrend'][0]


def run_bot(my_prev_index,my_index):

    global position_buy, position_sell
    global prev_in_uptrend

    try:
        df = pd.DataFrame(candles , columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        supertrend_data = supertrend(df, prev_in_uptrend, period=PERIOD)
        
        print('{0} long/short_signal: {1}'.format(df['timestamp'][my_index],df['in_uptrend'][my_index]))
        print(f'position_buy: {position_buy}, position_sell: {position_sell}')

        print()
        check_buy_sell_signals(supertrend_data,my_prev_index,my_index)
        prev_in_uptrend=df['in_uptrend'][my_index]

    except Exception as e:
        print(e)


# Функция возвращает истрию свечек
# Количество запрашиваемых свечек = limit, offset задаёт смещение 
def get_candles_list(offset,limit):
        candles_full_list = client.get_klines(symbol='DOGEBUSD', interval=Client.KLINE_INTERVAL_5MINUTE, startTime=(1632782100000-2592000000*7)+3*limit*100000*offset,limit=limit+1)
        # в каждом новом запросе дальнейшая обработка первой свечки теряется из-за того,
        # что у первой свечки нет предыдущей и программа начинается относительно второй
        # пожтому limit+1, а не limit
        
        # пишут,что генераторы работают быстрее циклов for, поэтому генератор
        return [list(map(float, candles_full_list[i][0:6])) for i in range(len(candles_full_list))]

candles=[]
offset=1 # в этой переменной хранится количество запросов к binance
limit=10 # Количество запрашиваемых свечек (Чем больше значение, тем реже будем обращаться к Binance)
candles=get_candles_list(offset,limit) # запрашиваем свечки для выполнения функции init_bot()

prev_trend=True #Установим по умолчанию True, потому что так было в функции supertrend()
init_bot()

# История свечек запрашивается частями в переменную candles: например, по limit=10 штук
# При первом запросе первая свечка обрабатывается в функции init(), остальные 9 шт - в функции run()
# В последующих запросах все свечки (10шт) обрабатываются в функции run(), поэтому вводится init_flag
init_flag=1
for i in range(10000):
    my_prev_index=0
    my_index=1
    
    if (init_flag==1):
        print()
    else:
        offset+=1
        candles=get_candles_list(offset,limit)

    # проходим по скачанному фрагменту истории, запуская функциею run_bot() нужное количество раз
    for i in range(init_flag,limit+2): 
        # в каждом новом запросе фрагмента истории обработка первой свечки теряется из-за того,
        # что у первой свечки нет предыдущей и программа начинается относительно второй
        # поэтому limit+2, а не limit+1, тем самым мы первую свечку обрабатываем последней в предыдущем фрагменте
        run_bot(my_prev_index,my_index)

        my_prev_index+=1
        my_index+=1
    
    init_flag=0

