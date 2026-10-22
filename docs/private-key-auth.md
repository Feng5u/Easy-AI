# M5 私钥认证入口与秘密边界

主机指纹经既有独立确认流程变为trusted后，认证面板可明确选择“私钥文件”，输入可选口令，再点击“选择私钥并认证”。系统文件选择器由Main打开，页面不能提交任意私钥路径、看到文件内容或本机路径；取消选取不认证、不自动重试，不扫描~/.ssh、不使用agent。当前不记住路径/口令，连接概要仍仅保存原非敏感设置。

Main只读取本次原生选中的普通非链接文件，上限64KiB，核fd身份/大小/mtime并严格UTF-8；支持OpenSSH及传统RSA/EC PEM封装，不支持PuTTY/PKCS8等其他格式。明文、加密RSA及加密OpenSSH Ed25519已做合成内存往返测试，ECDSA代码复用锁定SDK但本轮没有独立真实目标机验证。文件句柄在finally关闭，暂存Buffer填零。私钥内容仅经Main内部固定私钥HTTP路由送本机后端，不经过Renderer或远端文件上传。

密码入口保留。私钥route复用原单用身份grant、project/target/revision、已验证连接及再次host pin门、认证deadline、取消tombstone、清理等待和固定五分钟lease。实际SDK认证前及解析后重核授权，取消或超时不能发布迟到会话；环境/接续运行仅放宽认证方式枚举，仍必须匹配原project、用户、目标和指纹。SDK publickey timeout使用剩余预算，AuthHandler.private_key/password及saved_exception引用按原机制清理。

后端只在内存StringIO解析，字段是SecretStr、repr=False/exclude=True，不进入响应、工程JSON、概要、运行配置或报告。非法输入和SDK错误固定脱敏；HTTP验证异常也不回显秘密。UI密码和口令为非受控输入，开始等待前及切换方式/取消/关闭/卸载时清空；Main args/body和后端变量在finally丢弃引用。**JS/Python不可变字符串、HTTP/IPC缓冲和SDK/密码学内部内存无法承诺强制擦除**；不宣称凭据瞬间从进程内存消失。

不把64KiB当作解析成本上限：进入SDK前按OpenSSH PROTOCOL.key校验单key及容器边界，只接受none空KDF，或aes256-ctr/cbc+bcrypt、盐16–64字节、rounds 1–64；其他成本/格式拒绝，不自动降强度或重写密钥。按公钥算法只选一个RSA/ECDSA/Ed25519 decoder，避免轮流解密。这个轮数是当前应用保守支持边界，不是安全强度建议；更高成本密钥保留原文件，当前入口不支持。解析仍在工作线程，取消不会强杀正在执行的密码学函数；原running/BUSY保护保留到线程退出，不能宣称硬实时KDF取消。依据：[OpenSSH私钥格式](https://raw.githubusercontent.com/openssh/openssh-portable/master/PROTOCOL.key)。

本轮只生成测试内存合成keypairs和临时非真实key文件，禁用socket外连。没有读取、配置或上传真实用户私钥，没有创建SSH账号/授权凭据，没有连接真实服务器。native picker/桌面、安全目标机、真实私钥认证及SSH训练/重连都未验；现有Windows信任/远端存储生产gate不因此放开。M8本地便携目录仍对应先前源码7b91c46，未重打包或发布本轮私钥功能。
