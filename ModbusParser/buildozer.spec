[app]
title = Modbus调试工具
package.name = modbusparser
package.domain = org.modbus.app
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
source.include_patterns = simhei.ttf
requirements = python3,kivy,pillow,pyserial,requests
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.ndk = 25b
android.sdk = 24
android.private_storage = True
# 中文字体配置
android.add_assets = simhei.ttf
# 应用图标（没有可删除此行）
# icon.filename = icon.png