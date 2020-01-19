

选用huobi和okex2家交易所
需要在ws_huobi_config.ini配置文件中，填写2家交易所的key和secret，以及其他需要的参数
实盘运行ws_huobi.py文件，已经过实盘检验，功能完整

其余文件是huobi和okex的接口文件，不需要修改

其他说明：
okex交易所上的下单类型，我选择的是only maker，属于高级限价委托。在网页上，需要选择“高级限价委托”才能看到挂单和撤单
套利策略，需求明确，规则简单。但对代码效率要求很高，赢家通吃。

需要优化的内容：

1、logging功能编码错误，暂时未解决

2、代码整体效率需要进一步提高：挂撤单不需要每次全部撤单，只撤销一部分，加快运行速度

3、增加数据统计细节：预计盈利与开仓实际价格的差距；套利前后账户总资金变动数量

4、增加账户资金不足时，下单报错时等各种情况下，发送钉钉通知

5、增加记录累计开仓次数，累计出错次数等功能，便于及时诊断策略运行状态
