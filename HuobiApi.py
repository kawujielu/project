# -*- coding:utf-8 -*-
# 火币交易接口

import base64
import datetime
import hashlib
import hmac
import json
import urllib
import urllib.parse
import urllib.request
import requests
import configparser

class HuobiApi:

    def __init__(self, api_key='', secret_key='',base_url = 'https://api.huobi.pro'):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.acct_id = '' # 账户ID,API操作都需要用到该ID

    def http_get_request(self, url, params, add_to_headers=None):
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
        }
        if add_to_headers:
            headers.update(add_to_headers)
        postdata = urllib.parse.urlencode(params)

        try:
            response = requests.get(url, postdata, headers=headers, timeout=5)

            if response.status_code == 200:
                return response.json()
            else:
                print("status_code wrong, detail is:%s,%s" % (response.status_code, response.text))
                return
        except BaseException as e:
            print("httpGet failed, detail is:%s,%s" % (response.text, e))
            return

    def http_post_request(self, url, params, add_to_headers=None):
        headers = {
            "Accept": "application/json",
            'Content-Type': 'application/json'
        }
        if add_to_headers:
            headers.update(add_to_headers)
        postdata = json.dumps(params)

        try:
            response = requests.post(url, postdata, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print("status_code wrong, detail is:%s,%s" % (response.status_code,response.text))
                return
        except BaseException as e:
            print("httpPost failed, detail is:%s,%s" % (response.text, e))
            return

    def api_key_get(self, params, request_path):
        method = 'GET'
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        params.update({'AccessKeyId': self.api_key,
                       'SignatureMethod': 'HmacSHA256',
                       'SignatureVersion': '2',
                       'Timestamp': timestamp})

        host_url = self.base_url
        host_name = urllib.parse.urlparse(host_url).hostname
        host_name = host_name.lower()
        params['Signature'] = self.createSign(params, method, host_name, request_path, self.secret_key)

        url = host_url + request_path
        return self.http_get_request(url, params)

    def api_key_post(self, params, request_path):
        method = 'POST'
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        params_to_sign = {'AccessKeyId': self.api_key,
                          'SignatureMethod': 'HmacSHA256',
                          'SignatureVersion': '2',
                          'Timestamp': timestamp}

        host_url = self.base_url
        host_name = urllib.parse.urlparse(host_url).hostname
        host_name = host_name.lower()
        params_to_sign['Signature'] = self.createSign(params_to_sign, method, host_name, request_path, self.secret_key)
        url = host_url + request_path + '?' + urllib.parse.urlencode(params_to_sign)
        return self.http_post_request(url, params)

    def createSign(self, pParams, method, host_url, request_path, secret_key):
        sorted_params = sorted(pParams.items(), key=lambda d: d[0], reverse=False)
        encode_params = urllib.parse.urlencode(sorted_params)
        payload = [method, host_url, request_path, encode_params]
        payload = '\n'.join(payload)
        payload = payload.encode(encoding='UTF8')
        secret_key = secret_key.encode(encoding='UTF8')

        digest = hmac.new(secret_key, payload, digestmod=hashlib.sha256).digest()
        signature = base64.b64encode(digest)
        signature = signature.decode()
        return signature

    # 获取KLine
    def get_kline(self, symbol, period, size=150):
        """
        :param symbol
        :param period: 可选值：{1min, 5min, 15min, 30min, 60min, 1day, 1mon, 1week, 1year }
        :param size: 可选值： [1,2000]
        :return:
        """
        params = {'symbol': symbol,
                  'period': period,
                  'size': size}

        url = self.base_url + '/market/history/kline'
        return self.http_get_request(url, params)

    # 获取marketdepth
    def get_depth(self, symbol, type):
        """
        :param symbol
        :param type: 可选值：{ percent10, step0, step1, step2, step3, step4, step5 }
        :return:
        """
        params = {'symbol': symbol,
                  'type': type}

        url = self.base_url + '/market/depth'
        return self.http_get_request(url, params)

    # 获取tradedetail
    def get_trade(self, symbol):
        """
        :param symbol
        :return:
        """
        params = {'symbol': symbol}

        url = self.base_url + '/market/trade'
        return self.http_get_request(url, params)

    # 获取merge ticker
    def get_ticker(self, symbol):
        """
        :param symbol:
        :return:
        """
        params = {'symbol': symbol}

        url = self.base_url + '/market/detail/merged'
        return self.http_get_request(url, params)

    # 获取 Market Detail 24小时成交量数据
    def get_detail(self, symbol):
        """
        :param symbol
        :return:
        """
        params = {'symbol': symbol}

        url = self.base_url + '/market/detail'
        return self.http_get_request(url, params)

    # 获取  支持的交易对
    def get_symbols(self, long_polling=None):
        """

        """
        params = {}
        if long_polling:
            params['long-polling'] = long_polling
        path = '/v1/common/symbols'
        return self.api_key_get(params, path)

    '''
    Trade/Account API
    '''

    def get_accounts(self):
        """
        :return:
        """
        path = "/v1/account/accounts"
        params = {}
        ret = self.api_key_get(params, path)
        try:
            if ret:
                self.acct_id = ret['data'][0]['id']
            return self.__processRet(ret)
        except Exception as ex:
            print('call get_accounts err:%s' % ex )
            return self.__processRet(ret)

    # 获取当前账户资产
    def get_balance(self, acct_id=None):
        """
        :param acct_id
        :return:
        """

        if not self.acct_id:
            success, accounts = self.get_accounts()
            if success:
                self.acct_id = accounts['data'][0]['id']

        url = "/v1/account/accounts/{0}/balance".format(self.acct_id)
        params = {"account-id": self.acct_id}
        ret = self.api_key_get(params, url)
        return self.__processRet(ret)
    
    # 查询当前未成交订单
    def get_open_orders(self, symbol, side, size):
        if not self.acct_id:
            success, accounts = self.get_accounts()
            if success:
                self.acct_id = accounts['data'][0]['id']

        url = "/v1/order/openOrders"
        params = {"account-id":self.acct_id, "symbol":symbol}
        if side:
            params['side'] = side
        if size:
            params['size'] = size
        ret = self.api_key_get(params, url)
        return self.__processRet(ret)
    
    # 查询手续费
    def get_trade_fee(self, symbol):
        url = '/v1/fee/fee-rate/get'
        params = {'symbols':symbol}
        ret = self.api_key_get(params, url)
        return self.__processRet(ret)


    # 下单
    # 创建并执行订单
    def send_order(self, amount, price, _type, symbol, source=''):
        """
        :param amount:
        :param source: 类型string，如果使用借贷资产交易，请在下单接口,请求参数source中填写'margin-api'
        :param symbol: 如ehtusdt,btcusdt
        :param _type: 类型string可选值 {buy-market：市价买, sell-market：市价卖, buy-limit：限价买, sell-limit：限价卖}
        :param price:
        :return: 下单成功后的‘data'字段是报单编号
        """
        try:
            if not self.acct_id:
                success, accounts = self.get_accounts()
                if success:
                    self.acct_id = accounts['data'][0]['id']
                else:
                    return False, accounts
        except BaseException as e:
            print('get acct_id error.%s' % e)
            self.acct_id = None
            return False, e

        params = {"account-id": self.acct_id,
                  "amount": amount,
                  "symbol": symbol,
                  "type": _type,
                  "source": source}
        if price:
            params["price"] = price

        url = '/v1/order/orders/place'
        ret = self.api_key_post(params, url)
        print('253', ret)
        print(self.__processRet(ret))
        return self.__processRet(ret)

    def buy_limit(self, amount, price, symbol, source=''):
        return self.send_order(amount, price, 'buy-limit', symbol, source)

    def sell_limit(self,amount, price, symbol, source=''):
        return self.send_order(amount, price, 'sell-limit', symbol, source)

    # 撤销订单
    def cancel_order(self, order_id):
        """

        :param order_id:
        :return:
        """
        params = {}
        url = "/v1/order/orders/{0}/submitcancel".format(order_id)
        ret = self.api_key_post(params, url)
        return self.__processRet(ret)

    # 查询某个订单状态
    def get_order(self, order_id):
        """

        :param order_id:
        :return: 返回值的state字段：submitting , submitted 已提交, partial-filled 部分成交, partial-canceled 部分成交撤销, filled 完全成交, canceled 已撤销

        """
        params = {}
        url = "/v1/order/orders/{0}".format(order_id)
        ret = self.api_key_get(params, url)
        return self.__processRet(ret)

    # 查询某个订单的成交明细
    def order_matchresults(self, order_id):
        """

        :param order_id:
        :return:
        """
        params = {}
        url = "/v1/order/orders/{0}/matchresults".format(order_id)
        ret = self.api_key_get(params, url)
        return self.__processRet(ret)

    # 查询当前委托、历史委托
    def orders_list(self, symbol, states, types=None, start_date=None, end_date=None, _from=None, direct=None, size=None):
        """

        :param symbol:
        :param states: 可选值 {pre-submitted 准备提交, submitted 已提交, partial-filled 部分成交, partial-canceled 部分成交撤销, filled 完全成交, canceled 已撤销}
        :param types: 可选值 {buy-market：市价买, sell-market：市价卖, buy-limit：限价买, sell-limit：限价卖}
        :param start_date:
        :param end_date:
        :param _from:
        :param direct: 可选值{prev 向前，next 向后}
        :param size:
        :return:
        """
        params = {'symbol': symbol,
                  'states': states}

        if types:
            params['types'] = types
        if start_date:
            params['start-date'] = start_date
        if end_date:
            params['end-date'] = end_date
        if _from:
            params['from'] = _from
        if direct:
            params['direct'] = direct
        if size:
            params['size'] = size
        url = '/v1/order/orders'
        ret = self.api_key_get(params, url)
        return self.__processRet(ret)

    # 查询当前成交、历史成交
    def orders_matchresults(self, symbol, types=None, start_date=None, end_date=None, _from=None, direct=None, size=None):
        """

        :param symbol:
        :param types: 可选值 {buy-market：市价买, sell-market：市价卖, buy-limit：限价买, sell-limit：限价卖}
        :param start_date:
        :param end_date:
        :param _from:
        :param direct: 可选值{prev 向前，next 向后}
        :param size:
        :return:
        """
        params = {'symbol': symbol}

        if types:
            params[types] = types
        if start_date:
            params['start-date'] = start_date
        if end_date:
            params['end-date'] = end_date
        if _from:
            params['from'] = _from
        if direct:
            params['direct'] = direct
        if size:
            params['size'] = size
        url = '/v1/order/matchresults'
        ret = self.api_key_get(params, url)
        return self.__processRet(ret)

    # 申请提现虚拟币
    def withdraw(self, address_id, amount, currency, fee=0, addr_tag=""):
        """

        :param address_id:
        :param amount:
        :param currency:btc, ltc, bcc, eth, etc ...(火币Pro支持的币种)
        :param fee:
        :param addr-tag:
        :return: {
                  "status": "ok",
                  "data": 700
                }
        """
        params = {'address-id': address_id,
                  'amount': amount,
                  "currency": currency,
                  "fee": fee,
                  "addr-tag": addr_tag}
        url = '/v1/dw/withdraw/api/create'

        ret = self.api_key_post(params, url)
        return self.__processRet(ret)

    # 申请取消提现虚拟币
    def cancel_withdraw(self, address_id):
        """

        :param address_id:
        :return: {
                  "status": "ok",
                  "data": 700
                }
        """
        params = {}
        url = '/v1/dw/withdraw-virtual/{0}/cancel'.format(address_id)

        ret = self.api_key_post(params, url)
        return self.__processRet(ret)

    # 处理API接口的返回值，返回的元组为True但是status不是200的话(下单、撤单、查询单子状态等)
    def __processRet(self, ret):
        if not ret:
            return False, 'ret null'
        else:  # 返回的非空对象，处理一下下单后的返回状态status不是200的情况（说明下单失败，如资金不足等）
            if isinstance(ret, dict):  # 返回True
                status = ret['status']
                if status != 'ok':
                    return False, ret
                else:
                    return True, ret
            else:
                return False, ret

if __name__ == "__main__":
    huobi = HuobiApi(
                     '',
                     ''
                     )


    success, balance = huobi.get_balance()
    if success:
        for i in balance['data']['list']:
            if i['balance'] != '0':
                print(i)
    else:
        print("查询余额失败")
    
    a,b = huobi.get_trade_fee('btcusdt')
    print(a,b)
    
    # pre-submitted 准备提交, submitted 已提交, partial-filled 部分成交, 
    # partial-canceled 部分成交撤销, filled 完全成交, canceled 已撤销
    