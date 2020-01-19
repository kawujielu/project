# -*- coding: utf-8 -*-

import configparser
import getopt
import gzip
import json
import logging
import os
import random
import threading
import time
import datetime
import sys
import math
import websocket
import HuobiApi
import pandas as pd
import spot_api


class order_maker:
    def __init__(self):
        # 读取配置文件
        self.config = configparser.ConfigParser()
        self.config.read("ws_huobi_config.ini", encoding='UTF-8')

        self.trade_symbol = self.config.get("user", "trade_symbol")
        self.volume_digits = int(self.config.get("user", "volume_digits"))
        self.price_digits = int(self.config.get("user", "price_digits"))

        # 策略相关的配置
        self.price_depth = float(self.config.get('strategy', 'price_depth'))
        self.price_slip_point = int(self.config.get('strategy', 'price_slip_point'))

        # 记录启动参数
        logging.info("trade_symbol:%s", self.trade_symbol)
        logging.info("volume_digits:%s", self.volume_digits)
        logging.info("price_digits:%s", self.price_digits)
        logging.info("*" * 20)
        logging.info("price_depth:%s", self.price_depth)
        logging.info("price_slip_point:%s", self.price_slip_point)

        # 初始化Websocket
        # 墙内外修改这里
        depth_address = "wss://api.huobi.pro/ws"
        # depth_address = 'wss://api.huobi.br.com/ws'
        websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(depth_address,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)
        self.ws.on_open = self.on_open

        # 初始化HitBtc接口
        self.hitbtc_service = HuobiApi.HuobiApi(self.config.get("user", "key"),
                                                self.config.get("user", "secret"),
                                                self.config.get("user", "url"))

        self.spot = spot_api.SpotAPI(self.config.get("user", "key2"), 
                                     self.config.get("user", "secret2"), 
                                     self.config.get("user", "passphrase"), True)

        self.exchange1_trade_fee = 0      # A交易所手续费
        self.exchange2_trade_fee = 0      # B交易所手续费
        self.ask_price_list = []          # 卖盘盘口信息
        self.bid_price_list = []          # 买盘盘口信息
        self.depth_data = []              # 整体盘口挂单
        self.exchange1_btc_balance = 0    # A交易所BTC余额
        self.exchange1_usdt_balance = 0   # A交易所USDT余额
        self.exchange2_btc_balance = 0    # B交易所BTC余额
        self.exchange2_usdt_balance = 0   # B交易所USDT余额
        self.ratio = 0.8                  # 挂单占资金量的比例，不能是1，万一因为手续费或滑点造成资金不足，就会报错
        self.exchange1_min_size = 0.0001  # huobi最小交易量
        self.exchange2_min_size = 0.001   # okex最小交易量
        self.ledger_id = ''               # 最新成交订单的ledger_id，为了加快查询速度，只查询此ledger_id之后的成交记录
        self.slip_ratio = 0.005           # 为了保证一定成交，下单价格的滑点百分比
        self.ask_size = 0                 # 卖盘挂单数量
        self.bid_size = 0                 # 买盘挂单数量
        
        # 用于同步本地时间和服务器时间
        self.delta_time = 0

    # 精度控制，直接抹除多余位数，非四舍五入
    def digits(self, num, digit):
        site = pow(10, digit)
        tmp = num * site
        tmp = math.floor(tmp) / site
        return tmp

    # 启动ws
    def run(self):
        # 墙内外修改这里
        # self.ws.run_forever(http_proxy_host='127.0.0.1', http_proxy_port=1080) 
        self.ws.run_forever()
    
    # 获取盘口深度
    def depth(self, depth_data):
        self.depth_data = depth_data
        self.ask_price_list = []
        self.bid_price_list = []        
        asks_list = depth_data['tick']['asks'][:20]
        for ask in asks_list:
            self.ask_price_list.append(ask[0])
        bids_list = depth_data['tick']['bids'][:20]
        for bid in bids_list:
            self.bid_price_list.append(bid[0])

    # 查询未成交订单,并撤单
    def cancel_order(self):
        print('全部撤单')
        # 获取所有未成交订单
        result = self.spot.get_orders_pending('BTC-USDT')
        for i in result[0]:
            # 撤单
            self.spot.revoke_order('BTC-USDT', order_id=i['order_id'])
    
    # 获取账户资产
    def get_account(self):
        print('获取账户')
        # A交易所
        success, result= self.hitbtc_service.get_balance()
        if success:
            for i in result['data']['list']:
                if i['currency'] == 'btc' and i['type'] == 'trade':
                    self.exchange1_btc_balance = float(i['balance'])
                if i['currency'] == 'usdt' and i['type'] == 'trade':
                    self.exchange1_usdt_balance = float(i['balance'])
        # B交易所
        result = self.spot.get_coin_account_info('btc')
        self.exchange2_btc_balance = float(result['available'])
        result = self.spot.get_coin_account_info('usdt')
        self.exchange2_usdt_balance = float(result['available'])
        print('A交易所BTC余额：', self.exchange1_btc_balance)
        print('A交易所USDT余额：', self.exchange1_usdt_balance)
        print('B交易所BTC余额：', self.exchange2_btc_balance)
        print('B交易所USDT余额：', self.exchange2_usdt_balance)
        # logging.info('A交易所BTC余额：%s' % self.exchange1_btc_balance)
        # logging.info('A交易所USDT余额：%s' % self.exchange1_usdt_balance)
        # logging.info('B交易所BTC余额：%s' % self.exchange2_btc_balance)
        # logging.info('B交易所USDT余额：%s' % self.exchange2_usdt_balance)
        
    # 获取交易所手续费
    def trade_fee(self):
        print('获取手续费')
        # A交易所手续费
        A_trade_fee = self.hitbtc_service.get_trade_fee('btcusdt')
        self.exchange1_trade_fee = float(A_trade_fee[1]['data'][0]['taker-fee'])
        # B交易所手续费
        B_trade_fee = self.spot.get_trade_fee()
        self.exchange2_trade_fee = float(B_trade_fee['maker'])
        print('A交易所手续费：', self.exchange1_trade_fee)
        print('B交易所手续费：', self.exchange2_trade_fee)
        # logging.info('A交易所手续费：%s' % self.exchange1_trade_fee)
        # logging.info('B交易所手续费：%s' % self.exchange2_trade_fee)
    
    # 计算影子盘口挂单价格
    def get_fee(self):
        print('计算影子盘口价格')
        exchange1_ask_taker_fee = self.ask_price_list[0]*self.exchange1_trade_fee                           # A交易所手续费
        exchange2_ask_maker_fee = (self.ask_price_list[0]+self.price_slip_point)*self.exchange2_trade_fee   # B交易所手续费
        ask_slip_point = self.price_slip_point + exchange1_ask_taker_fee + exchange2_ask_maker_fee          # 滑点+双边手续费
        self.new_ask_price_list = [self.digits(x + ask_slip_point, self.price_digits) for x in self.ask_price_list] # B交易所影子盘口卖盘

        exchange1_bid_taker_fee = self.bid_price_list[0]*self.exchange1_trade_fee                           # A交易所手续费
        exchange2_bid_maker_fee = (self.bid_price_list[0]-self.price_slip_point)*self.exchange2_trade_fee   # B交易所手续费
        bid_slip_point = self.price_slip_point + exchange1_bid_taker_fee + exchange2_bid_maker_fee          # 滑点+双边手续费
        self.new_bid_price_list = [self.digits(x - bid_slip_point, self.price_digits) for x in self.bid_price_list] # B交易所影子盘口买盘

    # 计算挂单数量
    def get_volume(self):
        print('计算挂单数量')
        size = min(self.exchange1_usdt_balance/self.ask_price_list[0]/self.price_depth, self.exchange2_btc_balance/self.price_depth, self.depth_data['tick']['asks'][0][1])*self.ratio  # A交易所usdt数量/卖一价格 = 可买BTC数量,B交易所BTC数量，A交易所卖一挂单量，3者最小值*交易比例
        # 若挂单数量小于交易所规定的最小成交量，则返回
        if size < self.exchange1_min_size or size < self.exchange2_min_size:
            self.ask_size = 0.001
        else:
            self.ask_size = self.digits(size, self.volume_digits)
            print('卖盘挂单数量：', self.ask_size)
        size = min(self.exchange1_btc_balance/self.price_depth, self.exchange2_usdt_balance/self.new_bid_price_list[0], self.depth_data['tick']['bids'][0][1])*self.ratio
        if size < self.exchange1_min_size or size < self.exchange2_min_size:
            self.bid_size = 0.001
        else:
            self.bid_size = self.digits(size, self.volume_digits)
            print('买盘挂单数量：', self.bid_size)
    
    # 批量挂单
    def get_orders(self):
        print('批量挂单')
        # 获取最新ledger_id
        result = self.spot.get_fills('btc-usdt')
        self.ledger_id = result[1]['before']
        print('最新成交ledger_id:', self.ledger_id)
        try:
            for ask_price in self.new_ask_price_list:
                self.spot.take_order('btc-usdt', 'sell', type='limit', price=ask_price, size=self.ask_size, order_type='1')
            for bid_price in self.new_bid_price_list:
                self.spot.take_order('btc-usdt', 'bid', type='limit', price=bid_price, size=self.bid_size, order_type='1')
        except Exception as e:
            print("下单报错：", e)
            # logging.info("下单报错：%s" % e)
    
    # 检查上一轮成交情况
    def get_check(self):
        print('检查成交情况')
        # 1、查询最新成交记录
        # 2、根据成交记录的数量和方向，在A交易所下单
        if self.ledger_id == '':    # 若第一次运行该程序，则跳过这一步
            pass
        else:
            result = self.spot.get_fills('btc-usdt')        # , before=self.ledger_id
            if result != '':
                for r in result[0]:
                    try:
                        if r['side'] == 'buy':
                            # 在A交易所卖出相同数量的BTC
                            self.hitbtc_service.sell_limit(r['size'], self.digits(self.bid_price_list[0]*(1-self.slip_ratio), self.price_digits), self.trade_symbol)
                        else:
                            # 在A交易所买入相同数量的BTC
                            self.hitbtc_service.buy_limit(r['size'], self.digits(self.ask_price_list[0]*(1+self.slip_ratio), self.price_digits), self.trade_symbol)
                    except Exception as e:
                        print("下单报错：", e)
                        # logging.info("下单报错：%s" % e)

    # 处理成交行情推送
    def deal(self, quo_data):
        # 忽略掉“过时”的数据
        if self.delta_time != 0:
            if quo_data['ts'] < time.time() * 1000 + self.delta_time:
                return
        else:
            self.delta_time = quo_data['ts'] - time.time() * 1000
            print('和火币网服务器相差：%.2f秒' % (self.delta_time / 1000))
            # logging.info('和火币网服务器相差：%.2f秒' % (self.delta_time / 1000))

        # 步骤六(考虑放到第一步更合理)：每次循环开始，检查上一轮成交情况
        self.get_check()

        # 步骤一：撤销之前的所有挂单
        self.cancel_order()

        # 步骤二：获取账户在资产、交易所手续费、最小下单数量限制
        self.get_account()
        self.trade_fee()

        # 步骤三：计算影子盘口挂单价格
        self.get_fee()
        
        # 步骤四：计算挂单数量
        self.get_volume()

        # 步骤五：在B交易所挂单
        self.get_orders()


    # huobi下单操作
    def buy(self, price, volume):
        return self.hitbtc_service.buy_limit(volume, price, self.trade_symbol)

    def sell(self, price, volume):
        return self.hitbtc_service.sell_limit(volume, price, self.trade_symbol)

    # WebSocket回调函数
    def on_message(self, message):
        msg = gzip.decompress(message).decode('utf-8')

        if msg[:7] == '{"ping"':
            # 心跳
            ts = msg[8:21]
            pong = '{"pong":' + ts + '}'
            self.ws.send(pong)
        else:
            try:
                msg_obj = json.loads(msg)
                if 'ch' in msg_obj and msg_obj['ch'].find('trade') != -1:
                    self.deal(msg_obj)
                elif 'ch' in msg_obj and msg_obj['ch'].find('depth') != -1:
                    self.depth(msg_obj)
            except Exception as ex:
                logging.error(ex)

    def on_error(self, error):
        print("Websocket连接错误，%s" % error)
        # logging.error("Websocket连接错误，%s" % error)

    def on_close(self):
        print("Websocket连接关闭，5秒后重新连接")
        # logging.error("Websocket连接关闭，5秒后重新连接")

    def on_open(self):
        print("火币行情Websocket连接成功")
        # logging.info("火币行情Websocket连接成功")
        self.subscribe_depth(self.trade_symbol)
        self.subscribe_trade(self.trade_symbol)

    # 火币订阅
    def subscribe_depth(self, symbol):
        symbol_pair = symbol.replace('_', '')
        tradeStr = '{"sub": "market.%s.depth.step0", "id": "id10"}' % symbol_pair
        self.ws.send(tradeStr)

    def subscribe_trade(self, symbol):
        symbol_pair = symbol.replace('_', '')
        tradeStr = '{"sub": "market.%s.trade.detail", "id": "id11"}' % symbol_pair
        self.ws.send(tradeStr)

# 主函数
if __name__ == "__main__":
    
    while True:
        cf = order_maker()
        cf.run()
        time.sleep(5)
