[app]
# 应用桌面名称（手机显示名字）
title = Modbus解析工具
# 包名：仅小写英文，不能中文、空格、特殊符号
package.name = modbusparser
package.domain = org.modbusparser
# 版本号
version = 1.0
# 程序入口文件
entrypoint = main.py
# 源码目录
source.dir = .
# 允许打包的文件后缀
source.include_exts = py,png,jpg,jpeg,gif,kv,ttf
# 依赖库，默认kivy图形框架
requirements = python3,kivy
# 安卓SDK版本
android.api = 33
android.ndk = 25b
android.sdk = 24
# 关闭不必要编译项，提速
android.archs = arm64-v8a
# 权限按需开启，基础通用权限
android.permissions = INTERNET,ACCESS_NETWORK_STATE
# 关闭多余日志
log_level = info

[buildozer]
# 最大并行编译线程
max_parallel = 4
warn_on_root = 1
