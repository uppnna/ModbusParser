"""
Modbus RTU 报文解析工具 (Kivy 版)
功能：输入十六进制 Modbus RTU 报文，解析基础帧信息与报文解析数据。
支持 Bit / Int16 / UInt16 / Int32 / UInt32 / Float32 数据类型，
大端/小端模式与字交换组合（ABCD / CDAB / BADC / DCBA）。
界面已针对手机屏幕优化。
字体：SimHei (simhei.ttf)
"""
import re
import struct
from kivy.config import Config

Config.set('kivy', 'default_font', ['SimHei', 'simhei.ttf', 'simhei.ttf'])

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.metrics import dp

# ---------- Modbus 工具函数 ----------
def calc_modbus_crc(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def hex_to_bytes(hex_str: str) -> bytes:
    clean = re.sub(r"[^0-9a-fA-F]", "", hex_str)
    if len(clean) % 2 != 0:
        raise ValueError("十六进制字符总数必须为偶数")
    return bytes.fromhex(clean)

def bytes_to_hex(data: bytes) -> str:
    return " ".join(f"{x:02X}" for x in data)

def reg_convert(raw_bytes: bytes, data_type: str, byte_order: str):
    """根据数据类型和字节序，将字节转为数值"""
    buf = bytearray(raw_bytes)
    try:
        if data_type in ("Int16", "UInt16"):
            if len(buf) < 2:
                return None
            temp = buf[::-1] if byte_order == "DCBA" else buf
            fmt = ">H" if data_type == "UInt16" else ">h"
            return struct.unpack(fmt, temp[:2])[0]
        if data_type in ("Int32", "UInt32", "Float32"):
            if len(buf) < 4:
                return None
            four = buf[:4]
            if byte_order == "CDAB":
                temp = bytearray([four[2], four[3], four[0], four[1]])
            elif byte_order == "BADC":
                temp = bytearray([four[1], four[0], four[3], four[2]])
            elif byte_order == "DCBA":
                temp = four[::-1]
            else:
                temp = four
            fmt = {"UInt32": ">I", "Int32": ">i", "Float32": ">f"}[data_type]
            return round(struct.unpack(fmt, temp)[0], 4) if data_type == "Float32" else struct.unpack(fmt, temp)[0]
    except:
        return None

def get_bit_list(raw_2bytes: bytes):
    """返回16位二进制字符串列表（高位在前）"""
    if len(raw_2bytes) < 2:
        return ["-"] * 16
    val = int.from_bytes(raw_2bytes, "big")
    return [("1" if (val >> i) & 1 else "0") for i in range(15, -1, -1)]

# ---------- Modbus RTU 解析器 ----------
class ModbusAnalyser:
    FUNC_MAP = {
        0x01: "01 读线圈",
        0x02: "02 读离散输入",
        0x03: "03 读保持寄存器",
        0x04: "04 读输入寄存器",
    }
    EXC_CODE = {
        1: "非法功能",
        2: "非法地址",
        3: "非法数据",
        4: "从站故障",
        5: "确认",
        6: "从站忙",
        8: "存储器奇偶校验错误",
    }

    def parse_rtu(self, data: bytes):
        result = {
            "proto": "",
            "msg_type": "",
            "addr": "",
            "func": "",
            "data_len": "",
            "crc_check": "",
            "payload": "",
        }
        reg_list = []
        if len(data) < 4:
            result["proto"] = "报文太短"
            return result, reg_list

        slave_id = data[0]
        func_code = data[1]

        result["proto"] = "Modbus RTU"
        result["addr"] = f"{slave_id} (0x{slave_id:02X})"
        result["data_len"] = f"{len(data)} 字节"

        if func_code & 0x80:
            err_code = data[2]
            result.update(
                {
                    "msg_type": "异常响应帧",
                    "func": f"{func_code & 0x7F}(异常)",
                    "crc_check": "——",
                    "payload": self.EXC_CODE.get(err_code, f"未知异常{err_code}"),
                }
            )
            return result, reg_list

        result["func"] = self.FUNC_MAP.get(func_code, f"未知 0x{func_code:02X}")

        crc_recv = int.from_bytes(data[-2:], "little")
        crc_calc = calc_modbus_crc(data[:-2])
        result["crc_check"] = "校验通过" if crc_recv == crc_calc else "校验失败"

        body = data[2:-2]

        if func_code in (0x01, 0x02):
            if len(body) == 4:
                result["msg_type"] = "请求帧"
                result["payload"] = f"起始点位 {int.from_bytes(body[0:2], 'big')}"
            else:
                result["msg_type"] = "响应帧"
                byte_count = body[0]
                result["payload"] = f"{byte_count} 字节"
                reg_list = [body[i:i+2].hex().upper() for i in range(1, len(body), 2)]
        elif func_code in (0x03, 0x04):
            if len(body) == 4:
                result["msg_type"] = "请求帧"
                start = int.from_bytes(body[0:2], "big")
                count = int.from_bytes(body[2:4], "big")
                result["payload"] = f"起始{start}, 长度{count}"
            else:
                result["msg_type"] = "响应帧"
                byte_count = body[0]
                result["payload"] = f"{byte_count} 字节"
                reg_list = [body[i:i+2].hex().upper() for i in range(1, len(body), 2)]
        elif func_code in (0x05, 0x06):
            result["msg_type"] = "请求/应答帧"
            addr = int.from_bytes(body[0:2], "big")
            val = int.from_bytes(body[2:4], "big")
            result["payload"] = f"地址{addr}={val}"
        elif func_code in (0x0F, 0x10):
            result["msg_type"] = "请求/应答帧"
            start = int.from_bytes(body[0:2], "big")
            cnt = int.from_bytes(body[2:4], "big")
            result["payload"] = f"起始{start}, 数量{cnt}"
        else:
            result["msg_type"] = "未知帧类型"

        return result, reg_list

# ---------- 主界面 ----------
class MainWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(5), spacing=dp(4), **kwargs)
        self.analyser = ModbusAnalyser()
        self.reg_cache = []
        self.current_dtype = "Int16"
        self.word_swap = False
        self.byte_swap = False

        # 报文输入区
        self.hex_input = TextInput(
            hint_text="输入十六进制 Modbus RTU 报文",
            size_hint_y=None,
            height=dp(48),
            multiline=True,
            font_size=dp(13),
            foreground_color=(0, 0, 0, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
        )
        self.add_widget(self.hex_input)

        # 按钮行
        btn_box = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(8))
        btn_parse = Button(text="解析报文", on_press=self.parse_msg, font_size=dp(13))
        btn_parse.color = (0, 0, 0, 1)
        btn_clear = Button(text="清空报文", on_press=self.clear_all, font_size=dp(13))
        btn_clear.color = (0, 0, 0, 1)
        btn_box.add_widget(btn_parse)
        btn_box.add_widget(btn_clear)
        self.add_widget(btn_box)

        # 基础解析信息
        self.info_label = Label(
            text="解析结果将显示在这里",
            size_hint_y=None,
            height=dp(72),
            halign="left",
            valign="top",
            markup=True,
            font_size=dp(12),
            color=(0, 0, 0, 1),
        )
        self.info_label.bind(size=lambda s, w: s.setter('text_size')(s, w))
        self.add_widget(self.info_label)

        # 控制行（含标题、数据类型、端序、字交换）
        control_box = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))

        # “报文解析数据”标题（移至最左侧）
        control_box.add_widget(Label(
            text="报文解析数据",
            size_hint_x=None,
            width=dp(90),
            bold=True,
            font_size=dp(12),
            color=(0, 0, 0, 1),
            halign="left",
            valign="middle"
        ))

        # 数据类型标签与下拉
        control_box.add_widget(Label(
            text="数据类型:",
            size_hint_x=None,
            width=dp(70),
            font_size=dp(12),
            color=(0, 0, 0, 1),
            halign="right",
            valign="middle"
        ))
        self.dtype_spinner = Spinner(
            text="Int16",
            values=["Bit", "Int16", "UInt16", "Int32", "UInt32", "Float32"],
            size_hint_x=None,
            width=dp(95),
            font_size=dp(12),
        )
        self.dtype_spinner.color = (0, 0, 0, 1)
        self.dtype_spinner.bind(text=self.on_dtype_change)
        control_box.add_widget(self.dtype_spinner)

        # 大端/小端按钮
        self.btn_endian = ToggleButton(
            text="大端",
            size_hint_x=None,
            width=dp(75),
            font_size=dp(12),
            color=(0, 0, 0, 1),
            background_normal='',
            background_color=(0.8, 0.8, 0.8, 1),
            state="normal"
        )
        self.btn_endian.bind(on_press=self.toggle_endian)
        control_box.add_widget(self.btn_endian)

        # 字交换按钮
        self.btn_word_swap = ToggleButton(
            text="字交换",
            size_hint_x=None,
            width=dp(75),
            font_size=dp(12),
            color=(0, 0, 0, 1),
            background_normal='',
            background_color=(0.8, 0.8, 0.8, 1),
            state="normal"
        )
        self.btn_word_swap.bind(on_press=self.toggle_word_swap)
        control_box.add_widget(self.btn_word_swap)

        self.add_widget(control_box)

        # 解析数据表格（占满剩余空间）
        self.reg_scroll = ScrollView(size_hint=(1, 1))
        self.reg_grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(2))
        self.reg_grid.bind(minimum_height=self.reg_grid.setter("height"))
        self.reg_scroll.add_widget(self.reg_grid)
        self.add_widget(self.reg_scroll)

    def parse_msg(self, *args):
        content = self.hex_input.text.strip()
        if not content:
            self.show_popup("错误", "请输入十六进制报文")
            return
        try:
            data = hex_to_bytes(content)
        except Exception as e:
            self.show_popup("格式错误", str(e))
            self.clear_results()
            return

        res, regs = self.analyser.parse_rtu(data)
        self.reg_cache = regs
        self.update_info(res)
        self.update_reg_table()

    def update_info(self, res):
        info_text = (
            f"[b]协议：[/b] {res['proto']}\n"
            f"[b]类型：[/b] {res['msg_type']}\n"
            f"[b]从站地址：[/b] {res['addr']}\n"
            f"[b]功能码：[/b] {res['func']}\n"
            f"[b]数据长度：[/b] {res['data_len']}\n"
            f"[b]CRC校验：[/b] {res['crc_check']}\n"
            f"[b]详细内容：[/b] {res['payload']}"
        )
        self.info_label.text = info_text

    def clear_all(self, *args):
        self.hex_input.text = ""
        self.clear_results()

    def clear_results(self):
        self.info_label.text = "解析结果将显示在这里"
        self.reg_cache = []
        self.update_reg_table()

    def toggle_endian(self, instance):
        if instance.state == 'down':
            self.byte_swap = True
            self.word_swap = True
            instance.text = "小端"
        else:
            self.byte_swap = False
            self.word_swap = False
            instance.text = "大端"
        self.btn_word_swap.state = 'down' if self.word_swap else 'normal'
        self.btn_word_swap.text = "字交换:开" if self.word_swap else "字交换"
        self.update_reg_table()

    def toggle_word_swap(self, instance):
        self.word_swap = (instance.state == 'down')
        instance.text = "字交换:开" if self.word_swap else "字交换"
        self.update_reg_table()

    def on_dtype_change(self, spinner, text):
        self.current_dtype = text
        if text == "Bit":
            self.btn_endian.disabled = True
            self.btn_word_swap.disabled = True
        elif text in ("Int16", "UInt16"):
            self.btn_endian.disabled = True
            self.btn_word_swap.disabled = False
            self.byte_swap = False
        else:
            self.btn_endian.disabled = False
            self.btn_word_swap.disabled = False
        self.update_reg_table()

    def get_current_byte_order(self):
        dtype = self.current_dtype
        if dtype == "Bit":
            return None
        if dtype in ("Int16", "UInt16"):
            return "DCBA" if self.word_swap else "ABCD"
        if not self.word_swap and not self.byte_swap:
            return "ABCD"
        elif self.word_swap and not self.byte_swap:
            return "CDAB"
        elif not self.word_swap and self.byte_swap:
            return "BADC"
        else:
            return "DCBA"

    def update_reg_table(self):
        self.reg_grid.clear_widgets()
        dtype = self.current_dtype
        if not self.reg_cache:
            no_data_label = Label(
                text="暂无报文解析数据",
                size_hint_y=None,
                height=dp(30),
                font_size=dp(12),
                color=(0, 0, 0, 1),
            )
            self.reg_grid.add_widget(no_data_label)
            return

        byte_order = self.get_current_byte_order()
        if dtype == "Bit":
            col_title = "Bit数据"
        else:
            col_title = f"解析值 ({byte_order})" if byte_order else "解析值"

        # 表头
        header = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(2))
        header.add_widget(Label(text="序号", bold=True, size_hint_x=None, width=dp(45), font_size=dp(12), color=(0,0,0,1)))
        header.add_widget(Label(text="原始HEX", bold=True, size_hint_x=None, width=dp(90), font_size=dp(12), color=(0,0,0,1)))
        val_header = Label(text=col_title, bold=True, size_hint_x=1, font_size=dp(12), color=(0,0,0,1), halign="left")
        header.add_widget(val_header)
        self.reg_grid.add_widget(header)

        if dtype == "Bit":
            for idx, hex_val in enumerate(self.reg_cache):
                row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(2))
                bits = get_bit_list(bytes.fromhex(hex_val))
                grouped = ' '.join(''.join(bits[i:i+4]) for i in range(0, 16, 4))
                row.add_widget(Label(text=str(idx+1), size_hint_x=None, width=dp(45), font_size=dp(12), color=(0,0,0,1)))
                row.add_widget(Label(text=hex_val, size_hint_x=None, width=dp(90), font_size=dp(12), color=(0,0,0,1)))
                row.add_widget(Label(text=grouped, size_hint_x=1, font_size=dp(12), halign="left", color=(0,0,0,1)))
                self.reg_grid.add_widget(row)

        elif dtype in ("Int16", "UInt16"):
            for idx, hex_val in enumerate(self.reg_cache):
                raw = bytes.fromhex(hex_val)
                val = reg_convert(raw, dtype, byte_order)
                row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(2))
                row.add_widget(Label(text=str(idx+1), size_hint_x=None, width=dp(45), font_size=dp(12), color=(0,0,0,1)))
                row.add_widget(Label(text=hex_val, size_hint_x=None, width=dp(90), font_size=dp(12), color=(0,0,0,1)))
                val_text = str(val) if val is not None else "—"
                row.add_widget(Label(text=val_text, size_hint_x=1, font_size=dp(12), halign="left", color=(0,0,0,1)))
                self.reg_grid.add_widget(row)

        else:  # 32位或浮点
            idx = 1
            i = 0
            while i < len(self.reg_cache):
                if i + 1 < len(self.reg_cache):
                    hex_pair = self.reg_cache[i] + self.reg_cache[i+1]
                    raw4 = bytes.fromhex(hex_pair)
                    disp = f"{self.reg_cache[i]} {self.reg_cache[i+1]}"
                else:
                    raw4 = b""
                    disp = self.reg_cache[i]
                val = reg_convert(raw4, dtype, byte_order) if raw4 else None
                row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(2))
                row.add_widget(Label(text=str(idx), size_hint_x=None, width=dp(45), font_size=dp(12), color=(0,0,0,1)))
                row.add_widget(Label(text=disp, size_hint_x=None, width=dp(90), font_size=dp(12), color=(0,0,0,1)))
                val_text = str(val) if val is not None else "不足"
                row.add_widget(Label(text=val_text, size_hint_x=1, font_size=dp(12), halign="left", color=(0,0,0,1)))
                self.reg_grid.add_widget(row)
                idx += 1
                i += 2

    def show_popup(self, title, message):
        pop = Popup(
            title=title,
            content=Label(text=message, color=(0, 0, 0, 1), font_size=dp(14)),
            size_hint=(0.8, 0.3),
            auto_dismiss=True,
        )
        pop.open()

class ModbusParseApp(App):
    def build(self):
        Window.clearcolor = (0.95, 0.95, 0.95, 1)
        return MainWidget()

if __name__ == "__main__":
    ModbusParseApp().run()