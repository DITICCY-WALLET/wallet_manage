# APIS

[toc]

## 列表

| 版本 | API | URL | 方法 | 说明 |
| :---: | :---: | :---: | :---: |
| v1 | getBlockHeight | /api/v1/getBlockHeight | POST | 获取节点最新情况 |
| v1 | newAddress | /api/v1/newAddress | POST | 生成新地址, 生成地址比较消耗性能, v2将升级为异步 |
| v1 | getBalance | /api/v1/getBalance | POST | 获取某地址余额 |
| v1 | getTotalBalance | /api/v1/getTotalBalance | POST | 查询所有地址余额, 地址可能会过多造成系统阻塞, v2将升级成为异步 |
| v1 | sendTransaction | /api/v1/sendTransaction | POST | 发送交易 |
| v1 | getTransaction | /api/v1/getTransaction | POST | 获取交易信息, 成功, 失败, 具体详细情况 |
| v1 | checkAddress | /api/v1/checkAddress | POST | 查询该地址是否为钱包地址 |
| v1 | setWalletPassphrase | /api/v1/setWalletPassphrase | POST | 设置钱包密码 | 


## 接口报文
访问 /docs/api/ 查看