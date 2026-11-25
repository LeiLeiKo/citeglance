"""Paper Watch desktop client for Windows and Python installations with Tk."""

from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
from queue import Empty, Queue
import sqlite3
from threading import Thread
import time
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from urllib.parse import quote, urlsplit
import webbrowser

import bot
from desktop_store import (
    DATA_DIRECTORY, INTERVAL_SECONDS, Library, Secrets, clean_terms, read_json, saved_settings,
    translation_key, validate_channels, write_json,
)
from i18n import INTERFACE_LANGUAGES, PRESET_CHANNELS, translate, translate_error
from providers import (
    CUSTOM_SEARCH, LANGUAGES, SEARCH_PROVIDERS, TRANSLATION_ENDPOINTS, TRANSLATORS,
    endpoint_url, make_search, translate_abstract, validate_custom,
)


BG = "#edf2f5"
WHITE = "#ffffff"
INK = "#192a38"
SUBTLE = "#4f6574"
BLUE = "#146766"
TITLE_FONT = ("Microsoft YaHei UI", 22, "bold")
FONT = ("Microsoft YaHei UI", 10)
ALL = "全部频道"


class PaperWatch(tk.Tk):
    def __init__(self, directory=DATA_DIRECTORY, channels_path=bot.ROOT / "channels.json"):
        super().__init__()
        self.withdraw()
        self.geometry("1180x810")
        self.minsize(920, 630)
        self.configure(background=BG)
        self.directory = Path(directory)
        self.channels_path = Path(channels_path)
        self.config_data = validate_channels(read_json(self.channels_path, {"channels": [], "exclude": []}))
        self.settings = saved_settings(self.directory)
        self.ui_language = self.settings["ui_language"]
        if not isinstance(self.ui_language, str) or self.ui_language not in INTERFACE_LANGUAGES:
            self.ui_language = "zh"
        self.title(self.t("论文追踪"))
        self.static_labels = []
        self.tab_labels = []
        self.table_labels = []
        self.choice_updates = []
        self.secrets = Secrets(self.directory)
        self.library = Library(self.directory / "papers.sqlite3")
        self.last_round = self.library.last_search_started()
        self.schedule_timer = None
        self.schedule_issue = None
        self.auto_running = False
        self.events = Queue()
        self.busy = False
        self.visible = {}
        self.current_ids = None
        self.current_favorites = False
        self.edit_id = None
        self.lookup = []
        self.status = tk.StringVar()
        self.set_status("已载入本机论文库")
        self.picked_channel = tk.StringVar(value=self.settings["channel"])

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=FONT, foreground=INK, background=BG)
        style.configure("Tile.TFrame", background=WHITE)
        style.configure("Tile.TLabel", background=WHITE)
        style.configure("Hint.TLabel", foreground=SUBTLE)
        style.configure("Heading.TLabel", font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("TButton", padding=(12, 7), bordercolor="#b5c6cd", lightcolor=BG, darkcolor=BG)
        style.configure("Compact.TButton", width=0, padding=(8, 6))
        style.configure("Primary.TButton", background=BLUE, foreground=WHITE)
        style.map("Primary.TButton", background=[("disabled", "#829a99"), ("active", "#0b5455")])
        style.configure("TNotebook", bordercolor="#b5c6cd")
        style.configure("TNotebook.Tab", padding=(19, 8), background="#dce7ec", bordercolor="#b5c6cd")
        style.map("TNotebook.Tab", background=[("selected", BG), ("active", "#e5eef1")])
        style.configure("Treeview", rowheight=34, fieldbackground=WHITE, background=WHITE)
        style.configure("Treeview.Heading", padding=(7, 8))

        header = ttk.Frame(self, padding=(24, 15, 24, 10))
        header.pack(fill="x")
        self.label(header, "论文追踪", font=TITLE_FONT).pack(side="left")
        self.locale_picker = ttk.Combobox(header, values=tuple(INTERFACE_LANGUAGES.values()),
                                         state="readonly", width=13)
        self.locale_picker.current(tuple(INTERFACE_LANGUAGES).index(self.ui_language))
        self.locale_picker.bind("<<ComboboxSelected>>", self.change_language)
        self.locale_picker.pack(side="right", pady=8)
        self.label(header, "界面语言", style="Hint.TLabel").pack(side="right", padx=(14, 6))
        self.source_label = ttk.Label(header, style="Hint.TLabel", text=self.t(self.settings["provider"]))
        self.source_label.pack(side="right", pady=8)
        self.tabs = ttk.Notebook(self)
        self.build_library()
        self.build_channels()
        self.build_settings()
        self.build_schedule()
        footer = ttk.Frame(self, padding=(22, 1, 22, 12))
        footer.pack(side="bottom", fill="x")
        self.progress_bar = ttk.Progressbar(footer, mode="indeterminate", length=100)
        self.progress_bar.pack(side="right")
        self.status_label = ttk.Label(footer, textvariable=self.status, style="Hint.TLabel")
        self.status_label.pack(side="left", fill="x", expand=True)
        self.status_label.bind("<Configure>", lambda event: self.status_label.configure(wraplength=event.width))
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        self.refresh_channels()
        self.render_library()
        self.poll_timer = self.after(100, self.process_events)
        self.deiconify()
        self.wake_schedule()

    def t(self, key, **values):
        return translate(self.ui_language, key, **values)

    def error(self, error):
        if isinstance(error, json.JSONDecodeError):
            return self.t("JSON 格式错误（第 {line} 行，第 {column} 列）",
                          line=error.lineno, column=error.colno)
        return translate_error(self.ui_language, error)

    def show_error(self, caption, error):
        self.dialog(caption, self.error(error))

    def dialog(self, caption, message, *, confirm=None):
        popup = tk.Toplevel(self)
        popup.withdraw()
        popup.title(self.t(caption))
        popup.transient(self)
        popup.resizable(False, False)
        panel = ttk.Frame(popup, padding=18)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text=message, wraplength=430, justify="left").pack(fill="x")
        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=(14, 0))
        accepted = False

        def close(result=False):
            nonlocal accepted
            accepted = result
            popup.destroy()

        action = ttk.Button(buttons, text=self.t(confirm or "确定"), command=lambda: close(True))
        action.pack(side="right")
        focus = action
        if confirm:
            focus = ttk.Button(buttons, text=self.t("取消"), command=close)
            focus.pack(side="right", padx=(0, 8))
        popup.protocol("WM_DELETE_WINDOW", close)
        popup.bind("<Escape>", lambda _: close())
        popup.bind("<Return>", lambda _: focus.invoke())
        popup.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - popup.winfo_reqwidth()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - popup.winfo_reqheight()) // 2
        popup.geometry(f"+{max(0, x)}+{max(0, y)}")
        popup.deiconify()
        popup.wait_visibility()
        popup.grab_set()
        focus.focus_set()
        popup.wait_window()
        return accepted

    def local_widget(self, widget_type, parent, caption, **options):
        widget = widget_type(parent, text=self.t(caption), **options)
        self.static_labels.append((widget, caption))
        return widget

    def label(self, parent, caption, **options):
        return self.local_widget(ttk.Label, parent, caption, **options)

    def button(self, parent, caption, **options):
        return self.local_widget(ttk.Button, parent, caption, **options)

    def checkbutton(self, parent, caption, **options):
        return self.local_widget(ttk.Checkbutton, parent, caption, **options)

    def set_status(self, caption, **fields):
        self.status_message = caption, fields
        self.refresh_status()

    def refresh_status(self):
        caption, stored = self.status_message
        fields = dict(stored)
        failures = fields.pop("failures", ())
        for field in ("provider", "language"):
            if field in fields:
                fields[field] = self.t(fields[field])
        if "reason" in fields:
            fields["reason"] = self.error(fields["reason"])
        value = self.t(caption, **fields) if fields else self.error(caption)
        suffix = [
            self.t("频道 {number}未完成（{reason}）", number=number, reason=self.error(reason))
            for number, reason in failures
        ]
        self.status.set(" · ".join([value, *suffix]))

    def change_language(self, _):
        index = self.locale_picker.current()
        if index < 0:
            return
        language = tuple(INTERFACE_LANGUAGES)[index]
        if language == self.ui_language:
            return
        fresh = {**self.settings, "ui_language": language}
        try:
            write_json(self.directory / "settings.json", fresh)
        except OSError as error:
            self.locale_picker.current(tuple(INTERFACE_LANGUAGES).index(self.ui_language))
            self.show_error("无法保存界面语言", error)
            return
        self.settings = fresh
        self.ui_language = language
        self.title(self.t("论文追踪"))
        for widget, caption in self.static_labels:
            widget.configure(text=self.t(caption))
        for tab, caption in self.tab_labels:
            self.tabs.tab(tab, text=self.t(caption))
        for key, caption in self.table_labels:
            self.tree.heading(key, text=self.t(caption))
        for update in self.choice_updates:
            update()
        self.source_label.configure(text=self.t(self.settings["provider"]))
        self.refresh_channel_labels(self.edit_id)
        self.refresh_editor_label()
        self.refresh_result_label()
        position = self.detail.yview()[0]
        self.render_detail()
        self.detail.yview_moveto(position)
        self.refresh_status()
        self.refresh_schedule_status()

    def add_tab(self, title):
        tab = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(tab, text=self.t(title))
        self.tab_labels.append((tab, title))
        return tab

    def build_library(self):
        tab = self.add_tab("论文库")
        tools = ttk.Frame(tab)
        tools.pack(fill="x", pady=(0, 12))
        self.label(tools, "检索频道").pack(side="left", padx=(0, 7))
        self.channel_combo = ttk.Combobox(tools, state="readonly", width=33)
        self.channel_combo.bind("<<ComboboxSelected>>", self.pick_channel)
        self.channel_combo.pack(side="left", padx=(0, 10))
        self.search_button = self.button(tools, "检索新论文", style="Primary.TButton", command=self.start_search)
        self.search_button.pack(side="left", padx=(0, 8))
        self.button(tools, "检索历史", command=lambda: self.render_library()).pack(side="left", padx=(0, 8))
        self.button(tools, "收藏", command=lambda: self.render_library(favorites=True)).pack(side="left")

        body = ttk.Panedwindow(tab, orient="horizontal")
        body.pack(fill="both", expand=True)
        listing = ttk.Frame(body, padding=(0, 0, 8, 0))
        body.add(listing, weight=5)
        self.result_label = ttk.Label(listing, style="Heading.TLabel", text=self.t("论文"))
        self.result_label.pack(anchor="w", pady=(0, 7))
        table_box = ttk.Frame(listing)
        table_box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table_box, columns=("title", "date", "channel"), show="headings", selectmode="browse")
        for key, text, width, stretch in (
            ("title", "标题", 260, True), ("date", "发表日期", 104, False), ("channel", "频道", 91, False)
        ):
            self.tree.heading(key, text=self.t(text), anchor="w")
            self.table_labels.append((key, text))
            self.tree.column(key, width=width, minwidth=54, stretch=stretch, anchor="w")
        scroll = ttk.Scrollbar(table_box, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _: self.render_detail())
        self.tree.bind("<Double-1>", lambda _: self.open_paper())

        detail = ttk.Frame(body, padding=(12, 0, 0, 0))
        body.add(detail, weight=6)
        actions = ttk.Frame(detail)
        actions.pack(fill="x", pady=(0, 8))
        self.detail_actions = actions
        self.actions_wrapped = None
        self.favorite_button = ttk.Button(actions, text=self.t("收藏论文"), style="Compact.TButton",
                                          command=self.toggle_favorite)
        self.favorite_button.grid(row=0, column=0, sticky="w", padx=(0, 7))
        self.link_button = self.button(actions, "打开来源", style="Compact.TButton", command=self.open_paper)
        self.link_button.grid(row=0, column=1, sticky="w", padx=(0, 7))
        self.translate_button = self.button(actions, "翻译摘要", style="Compact.TButton", command=self.start_translation)
        self.translate_button.grid(row=0, column=2, sticky="w")
        actions.bind("<Configure>", lambda _: self.arrange_detail_actions())
        self.detail = ScrolledText(detail, wrap="word", font=FONT, background=WHITE,
                                   foreground=INK, relief="flat", padx=15, pady=13, width=39)
        self.detail.pack(fill="both", expand=True)
        self.detail.tag_configure("title", font=("Microsoft YaHei UI", 16, "bold"), spacing3=12)
        self.detail.tag_configure("heading", font=("Microsoft YaHei UI", 11, "bold"), spacing1=11, spacing3=4)
        self.detail.tag_configure("muted", foreground=SUBTLE, spacing3=4)

    def new_text(self, parent, *, height=4, width=28):
        return ScrolledText(parent, height=height, width=width, wrap="word", font=FONT,
                            background=WHITE, foreground=INK, relief="flat", padx=8, pady=6,
                            undo=True, maxundo=20)

    def build_channels(self):
        tab = self.add_tab("频道与屏蔽词")
        tab.columnconfigure(1, weight=2)
        tab.columnconfigure(2, weight=1)
        tab.rowconfigure(0, weight=1)
        side = ttk.Frame(tab, padding=(0, 0, 14, 0))
        side.grid(row=0, column=0, sticky="nsew")
        self.label(side, "频道", style="Heading.TLabel").pack(anchor="w", pady=(0, 8))
        self.channel_list = tk.Listbox(side, width=27, height=12, exportselection=False, font=FONT,
                                       activestyle="none", bg=WHITE, fg=INK, relief="flat",
                                       highlightthickness=0, selectbackground=BLUE)
        self.channel_list.pack(fill="both", expand=True)
        side_scroll = ttk.Scrollbar(side, orient="horizontal", command=self.channel_list.xview)
        self.channel_list.configure(xscrollcommand=side_scroll.set)
        side_scroll.pack(fill="x")
        self.channel_list.bind("<<ListboxSelect>>", self.select_channel)
        self.button(side, "新增频道", command=lambda: self.fill_channel(None)).pack(fill="x", pady=(8, 4))
        self.button(side, "删除所选频道", command=self.delete_channel).pack(fill="x")

        editor = ttk.Frame(tab, padding=(0, 0, 14, 0))
        editor.grid(row=0, column=1, sticky="nsew")
        editor.columnconfigure(0, weight=1)
        self.editor_label = ttk.Label(editor, text=self.t("新增频道"), style="Heading.TLabel")
        self.editor_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.channel_name = tk.StringVar()
        self.label(editor, "频道名称").grid(row=1, column=0, sticky="w", pady=(0, 2))
        ttk.Entry(editor, textvariable=self.channel_name).grid(row=2, column=0, sticky="ew", pady=(0, 3))
        self.label(editor, "每行一个词组。A、B 两组都需至少命中一项。",
                   style="Hint.TLabel", wraplength=310).grid(row=3, column=0, sticky="w", pady=(0, 2))
        self.term_fields = {}
        groups = (("a", "A 组 · 对象或场景"), ("b", "B 组 · 现象、方法或技术"),
                  ("focus", "领域限定 · 可选，任一项命中"), ("exclude", "仅此频道的屏蔽词"))
        for index, (key, title) in enumerate(groups):
            row = 4 + index * 2
            self.label(editor, title).grid(row=row, column=0, sticky="w", pady=(4, 2))
            entry = self.new_text(editor, height=2)
            entry.grid(row=row + 1, column=0, sticky="nsew")
            editor.rowconfigure(row + 1, weight=1)
            self.term_fields[key] = entry
        self.save_channel_button = self.button(editor, "保存频道", style="Primary.TButton", command=self.save_channel)
        self.save_channel_button.grid(row=12, column=0, sticky="e", pady=(6, 0))

        exclusions = ttk.Frame(tab)
        exclusions.grid(row=0, column=2, sticky="nsew")
        self.label(exclusions, "全局屏蔽词", style="Heading.TLabel").pack(anchor="w", pady=(0, 7))
        self.label(exclusions, "标题或摘要命中时，从所有频道排除。每行一个词组。",
                   style="Hint.TLabel", wraplength=225).pack(anchor="w", pady=(0, 7))
        self.excluded = self.new_text(exclusions, height=15, width=22)
        self.excluded.insert("1.0", "\n".join(self.config_data.get("exclude", [])))
        self.excluded.pack(fill="both", expand=True)
        self.button(exclusions, "保存全局屏蔽词", command=self.save_exclusions).pack(anchor="e", pady=(7, 0))

    def build_settings(self):
        tab = self.add_tab("API 与设置")
        tab.columnconfigure(0, weight=1, uniform="settings")
        tab.columnconfigure(1, weight=1, uniform="settings")
        tab.rowconfigure(0, weight=1)
        left = ttk.Frame(tab, padding=(4, 5, 16, 4))
        right = ttk.Frame(tab, padding=(16, 5, 4, 4))
        left.grid(row=0, column=0, sticky="nsew")
        right.grid(row=0, column=1, sticky="nsew")
        self.values = {key: tk.StringVar(value=self.settings[key]) for key in (
            "provider", "lookback", "budget", "translator", "language", "translation_endpoint", "translation_model",
        )}
        self.api_key = tk.StringVar()
        self.translation_secret = tk.StringVar()
        self.remember = tk.BooleanVar(value=os.name == "nt")
        self.clear_search = tk.BooleanVar()
        self.clear_translation = tk.BooleanVar()
        self.label(left, "论文检索", style="Heading.TLabel").pack(anchor="w", pady=(0, 9))
        source_type = self.setting_row(left, "检索来源", self.values["provider"], choices=SEARCH_PROVIDERS)
        source_type.bind("<<ComboboxSelected>>", self.select_provider, add="+")
        self.setting_row(left, "检索 API Key", self.api_key, secret=True)
        self.checkbutton(left, "清除当前检索来源保存的密钥", variable=self.clear_search).pack(anchor="w", pady=3)
        self.setting_row(left, "检索最近几天", self.values["lookback"])
        self.setting_row(left, "每轮请求上限", self.values["budget"])
        self.custom_panel = ttk.Frame(left)
        self.label(self.custom_panel, "自定义 JSON 接口", style="Heading.TLabel").pack(anchor="w", pady=(10, 4))
        self.label(self.custom_panel, "按接口文档填写请求和返回字段映射。",
                   style="Hint.TLabel", wraplength=350).pack(anchor="w")
        self.custom = self.new_text(self.custom_panel, height=10)
        self.custom.insert("1.0", json.dumps(self.settings.get("custom") or CUSTOM_SEARCH, ensure_ascii=False, indent=2))
        self.custom.pack(fill="both", expand=True, pady=(5, 0))
        if self.values["provider"].get() == "自定义 JSON":
            self.custom_panel.pack(fill="both", expand=True)

        self.label(right, "摘要翻译", style="Heading.TLabel").pack(anchor="w", pady=(0, 9))
        kind = self.setting_row(right, "翻译服务", self.values["translator"], choices=TRANSLATORS)
        self.previous_translator = self.settings["translator"]
        self.translation_profiles = deepcopy(self.settings.get("translation_profiles", {}))
        kind.bind("<<ComboboxSelected>>", self.select_translator, add="+")
        self.setting_row(right, "目标语言", self.values["language"], choices=tuple(LANGUAGES))
        self.translation_address_entry = self.setting_row(right, "完整接口地址", self.values["translation_endpoint"])
        self.translation_model_entry = self.setting_row(right, "模型（OpenAI 兼容）", self.values["translation_model"])
        self.translation_key_entry = self.setting_row(right, "翻译 API Key", self.translation_secret, secret=True)
        self.checkbutton(right, "清除当前翻译服务保存的密钥", variable=self.clear_translation).pack(anchor="w", pady=3)
        self.checkbutton(right, "记住本次输入的密钥（Windows 加密）", variable=self.remember).pack(anchor="w", pady=(12, 3))
        self.label(right, "密钥框留空时沿用当前服务的已有密钥。翻译在点击「翻译摘要」后请求。",
                   style="Hint.TLabel", wraplength=390).pack(anchor="w", pady=(4, 10))
        self.button(right, "保存设置", style="Primary.TButton", command=self.save_preferences).pack(anchor="e", pady=(6, 0))
        self.configure_translation_entries()

    def build_schedule(self):
        tab = self.add_tab("定时检索")
        tab.columnconfigure(0, weight=1, uniform="schedule")
        tab.columnconfigure(1, weight=1, uniform="schedule")
        options = ttk.Frame(tab, padding=(4, 5, 16, 4))
        options.grid(row=0, column=0, sticky="new")
        details = ttk.Frame(tab, padding=(16, 5, 4, 4))
        details.grid(row=0, column=1, sticky="new")
        self.auto_enabled = tk.BooleanVar(value=self.settings["auto_enabled"])
        self.auto_interval = tk.StringVar(value=self.settings["auto_interval"])
        self.auto_unit = tk.StringVar(value=self.settings["auto_unit"])
        self.checkbutton(options, "启用定时检索", variable=self.auto_enabled).pack(anchor="w", pady=(0, 10))
        self.setting_row(options, "检索间隔", self.auto_interval)
        self.setting_row(options, "间隔单位", self.auto_unit, choices=tuple(INTERVAL_SECONDS))
        self.button(options, "保存定时设置", style="Primary.TButton", command=self.save_schedule).pack(
            anchor="e", pady=(10, 0)
        )
        self.label(details, "客户端打开时，会按设定频率检索全部频道，结果存入检索历史。",
                   style="Hint.TLabel", wraplength=350, justify="left").pack(anchor="w", pady=(0, 14))
        self.schedule_status = tk.StringVar()
        self.schedule_last = tk.StringVar()
        ttk.Label(details, textvariable=self.schedule_status, style="Heading.TLabel", wraplength=350,
                  justify="left").pack(anchor="w", pady=(0, 8))
        ttk.Label(details, textvariable=self.schedule_last, style="Hint.TLabel", wraplength=350).pack(anchor="w")

    def interval_seconds(self):
        return self.settings["auto_interval"] * INTERVAL_SECONDS[self.settings["auto_unit"]]

    def save_schedule(self):
        try:
            interval = int(self.auto_interval.get())
        except ValueError:
            interval = 0
        unit = self.auto_unit.get()
        if not 1 <= interval <= 365 or unit not in INTERVAL_SECONDS:
            self.show_error("无法保存定时设置", "检索间隔需为 1–365 的整数。")
            return
        fresh = {
            **self.settings, "auto_enabled": self.auto_enabled.get(),
            "auto_interval": interval, "auto_unit": unit,
        }
        try:
            write_json(self.directory / "settings.json", fresh)
        except OSError as error:
            self.show_error("无法保存定时设置", error)
            return
        self.settings = fresh
        self.set_status("已保存定时检索设置")
        self.wake_schedule()

    def wake_schedule(self):
        if self.schedule_timer is not None:
            self.after_cancel(self.schedule_timer)
            self.schedule_timer = None
        self.schedule_issue = None
        self.refresh_schedule_status()
        if self.settings["auto_enabled"]:
            self.schedule_timer = self.after(1500, self.check_schedule)

    def check_schedule(self):
        self.schedule_timer = None
        if not self.settings["auto_enabled"]:
            return
        delay = 15000
        try:
            self.last_round = self.library.last_search_started()
            remaining = self.schedule_remaining()
            if remaining <= 0:
                if not self.busy:
                    self.start_search(automatic=True)
            else:
                self.schedule_issue = None
                delay = max(250, min(30000, int(remaining * 1000)))
        except sqlite3.Error as error:
            self.schedule_issue = error
        self.refresh_schedule_status()
        self.schedule_timer = self.after(delay, self.check_schedule)

    def schedule_remaining(self):
        return self.last_round + self.interval_seconds() - time.time() if self.last_round is not None else 0

    def schedule_time(self, timestamp):
        return datetime.fromtimestamp(timestamp, bot.JAPAN_TIME).strftime("%Y-%m-%d %H:%M:%S JST")

    def refresh_schedule_status(self):
        if not self.settings["auto_enabled"]:
            status = self.t("定时检索已暂停。")
        elif self.auto_running:
            status = self.t("正在自动检索全部频道。")
        elif self.schedule_issue:
            status = self.t("定时检索等待设置：{reason}", reason=self.error(self.schedule_issue))
        elif self.schedule_remaining() > 0:
            status = self.t("下一次检索 · {when}", when=self.schedule_time(self.last_round + self.interval_seconds()))
        elif self.busy:
            status = self.t("等待当前操作结束后自动检索。")
        else:
            status = self.t("已到检索时间，正在等待启动。")
        self.schedule_status.set(status)
        self.schedule_last.set("" if self.last_round is None else
                               self.t("上次检索启动 · {when}", when=self.schedule_time(self.last_round)))

    def setting_row(self, parent, text, variable, *, choices=None, secret=False):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        self.label(row, text, width=25).pack(side="left")
        if choices:
            widget = ttk.Combobox(row, state="readonly")

            def update(*_):
                widget.configure(values=[self.t(option) for option in choices])
                value = variable.get()
                if value in choices:
                    widget.current(choices.index(value))

            def choose(_):
                index = widget.current()
                if index >= 0:
                    variable.set(choices[index])

            variable.trace_add("write", update)
            widget.bind("<<ComboboxSelected>>", choose)
            self.choice_updates.append(update)
            update()
        else:
            widget = ttk.Entry(row, textvariable=variable, show="*" if secret else "")
        widget.pack(side="left", fill="x", expand=True)
        return widget

    def refresh_channels(self, selected=None):
        self.lookup = self.config_data["channels"]
        self.refresh_channel_labels(selected)
        active = next((row for row in self.lookup if row["id"] == selected), None)
        self.fill_channel(active)

    def refresh_channel_labels(self, selected=None):
        self.channel_values = [ALL, *(self.channel_key(row) for row in self.lookup)]
        labels = [self.channel_label(row) for row in self.lookup]
        self.channel_combo.configure(values=[self.t(ALL), *labels])
        current = self.picked_channel.get()
        if current not in self.channel_values:
            current = ALL
            self.picked_channel.set(current)
        self.channel_combo.current(self.channel_values.index(current))
        self.channel_list.delete(0, "end")
        for index, label in enumerate(labels):
            self.channel_list.insert("end", label)
            if self.lookup[index]["id"] == selected:
                self.channel_list.selection_set(index)
                self.channel_list.see(index)

    @staticmethod
    def channel_key(row):
        return f'{row["id"]} · {row["name"]}'

    def channel_label(self, row):
        index = row["id"] - 1
        name = row["name"]
        if 0 <= index < len(PRESET_CHANNELS) and name == PRESET_CHANNELS[index]:
            name = self.t(name)
        return f'{row["id"]} · {name}'

    def pick_channel(self, _):
        index = self.channel_combo.current()
        if index >= 0:
            self.picked_channel.set(self.channel_values[index])

    def refresh_editor_label(self):
        title = self.t("编辑频道 {number}", number=self.edit_id) if self.edit_id else self.t("新增频道")
        self.editor_label.configure(text=title)

    def fill_channel(self, channel):
        self.edit_id = channel["id"] if channel else None
        self.refresh_editor_label()
        self.channel_name.set(channel["name"] if channel else "")
        for key, field in self.term_fields.items():
            field.delete("1.0", "end")
            if channel:
                field.insert("1.0", "\n".join(channel.get(key, [])))
        if not channel:
            self.channel_list.selection_clear(0, "end")

    def select_channel(self, _):
        pick = self.channel_list.curselection()
        if pick:
            self.fill_channel(self.lookup[pick[0]])

    def write_channels(self, replacement, message, selected=None, *, refresh=True, **fields):
        try:
            validate_channels(replacement)
            previous = read_json(self.channels_path, {"channels": [], "exclude": []})
            if previous != self.config_data:
                raise ValueError("频道文件已在其他窗口修改。请重新打开客户端后再编辑。")
            write_json(self.channels_path, replacement)
        except (ValueError, OSError) as error:
            self.show_error("无法保存频道", error)
            return
        self.config_data = replacement
        if refresh:
            self.refresh_channels(selected)
        self.set_status(message, **fields)
        self.wake_schedule()

    def save_channel(self):
        replacement = deepcopy(self.config_data)
        minimum = max((row["id"] for row in self.lookup), default=0) + 1
        channel_id = self.edit_id or max(minimum, replacement.get("next_channel_id", minimum))
        row = {"id": channel_id, "name": self.channel_name.get().strip()}
        row.update({key: clean_terms(field.get("1.0", "end-1c")) for key, field in self.term_fields.items()})
        if self.edit_id:
            for index, old in enumerate(replacement["channels"]):
                if old["id"] == self.edit_id:
                    replacement["channels"][index] = {**old, **row}
                    break
        else:
            replacement["channels"].append(row)
            replacement["next_channel_id"] = channel_id + 1
        self.write_channels(replacement, "已保存频道 {number}", channel_id, number=channel_id)

    def delete_channel(self):
        if self.edit_id is None:
            return
        if self.dialog("删除频道", self.t("删除所选频道？"), confirm="删除频道"):
            minimum = max((row["id"] for row in self.lookup), default=0) + 1
            replacement = {**self.config_data, "channels": [row for row in self.lookup if row["id"] != self.edit_id],
                           "next_channel_id": max(minimum, self.config_data.get("next_channel_id", minimum))}
            self.write_channels(replacement, "已删除频道")

    def save_exclusions(self):
        replacement = {**self.config_data, "exclude": clean_terms(self.excluded.get("1.0", "end-1c"))}
        self.write_channels(replacement, "已保存全局屏蔽词", refresh=False)

    def select_translator(self, _):
        current = self.values["translator"].get()
        self.translation_profiles[self.previous_translator] = {
            "endpoint": self.values["translation_endpoint"].get(),
            "model": self.values["translation_model"].get(),
        }
        profile = self.translation_profiles.get(current, {})
        self.values["translation_endpoint"].set(profile.get("endpoint") or TRANSLATION_ENDPOINTS[current])
        self.values["translation_model"].set(profile.get("model", ""))
        self.translation_secret.set("")
        self.clear_translation.set(False)
        self.previous_translator = current
        self.configure_translation_entries()

    def configure_translation_entries(self):
        translator = self.values["translator"].get()
        state = "disabled" if translator == "关闭" else "normal"
        self.translation_address_entry.configure(state=state)
        self.translation_key_entry.configure(state=state)
        self.translation_model_entry.configure(state="normal" if translator == "OpenAI 兼容" else "disabled")

    def select_provider(self, _):
        self.api_key.set("")
        self.clear_search.set(False)
        if self.values["provider"].get() == "自定义 JSON":
            self.custom_panel.pack(fill="both", expand=True)
        else:
            self.custom_panel.pack_forget()

    @staticmethod
    def key_slot(category, service, endpoint=""):
        return "|".join((category, service, endpoint))

    def save_preferences(self):
        try:
            fresh = {**self.settings, **{key: value.get().strip() for key, value in self.values.items()}}
            try:
                fresh["lookback"] = int(fresh["lookback"])
                fresh["budget"] = int(fresh["budget"])
            except ValueError:
                raise ValueError("请输入整数。") from None
            if not 1 <= fresh["lookback"] <= 365 or not 1 <= fresh["budget"] <= 200:
                raise ValueError("检索天数请输入 1–365，每轮请求上限请输入 1–200。")
            custom_raw = self.custom.get("1.0", "end-1c").strip()
            if fresh["provider"] == "自定义 JSON":
                fresh["custom"] = json.loads(custom_raw)
                validate_custom(fresh["custom"])
                fresh["custom"]["endpoint"] = endpoint_url(fresh["custom"]["endpoint"])
            endpoint = fresh["translation_endpoint"]
            if fresh["translator"] != "关闭":
                endpoint = endpoint_url(endpoint or TRANSLATION_ENDPOINTS[fresh["translator"]])
            fresh["translation_endpoint"] = endpoint
            fresh["channel"] = self.picked_channel.get()
            fresh["translation_profiles"] = deepcopy(self.translation_profiles)
            fresh["translation_profiles"][fresh["translator"]] = {
                "endpoint": endpoint, "model": fresh["translation_model"],
            }
            search_key = self.api_key.get().strip()
            translation_secret = self.translation_secret.get().strip()
            if any(char.isspace() for key in (search_key, translation_secret) for char in key):
                raise ValueError("API Key 应是单行且不含空格。")
            search_endpoint = fresh["custom"]["endpoint"] if fresh["provider"] == "自定义 JSON" else ""
            self.secrets.update(self.key_slot("search", fresh["provider"], search_endpoint),
                                search_key, remember=self.remember.get(), clear=self.clear_search.get())
            if fresh["translator"] != "关闭":
                self.secrets.update(self.key_slot("translation", fresh["translator"], endpoint),
                                    translation_secret, remember=self.remember.get(), clear=self.clear_translation.get())
            write_json(self.directory / "settings.json", fresh)
        except (ValueError, OSError) as error:
            self.show_error("无法保存设置", error)
            return
        self.settings = fresh
        self.source_label.configure(text=self.t(fresh["provider"]))
        self.values["translation_endpoint"].set(endpoint)
        self.api_key.set("")
        self.translation_secret.set("")
        self.clear_search.set(False)
        self.clear_translation.set(False)
        self.set_status("已保存设置")
        self.wake_schedule()
        self.render_detail()

    def render_library(self, ids=None, favorites=False, select=None):
        self.current_ids, self.current_favorites = ids, favorites
        rows = self.library.list(ids, favorites)
        self.visible = {str(paper["record_id"]): paper for paper in rows}
        self.tree.delete(*self.tree.get_children())
        for key, paper in self.visible.items():
            channels = ", ".join(str(row[0]) for row in paper["matches"])
            title = ("★ " if paper["favorite"] else "") + paper["title"]
            self.tree.insert("", "end", iid=key,
                             values=(title, paper.get("publicationDate") or paper.get("year") or "", channels))
        self.refresh_result_label()
        first = str(select) if str(select) in self.visible else next(iter(self.visible), None)
        if first:
            self.tree.selection_set(first)
            self.tree.see(first)
        self.render_detail()

    def refresh_result_label(self):
        current = "收藏" if self.current_favorites else ("本次检索" if self.current_ids is not None else "检索历史")
        self.result_label.configure(text=self.t("{view} · {count} 篇", view=self.t(current), count=len(self.visible)))

    def selected_paper(self):
        selection = self.tree.selection()
        return self.visible.get(selection[0]) if selection else None

    def record_link(self, paper):
        doi = (paper.get("externalIds") or {}).get("DOI")
        link = f"https://doi.org/{quote(doi, safe='/')}" if doi else paper.get("url") or ""
        try:
            parts = urlsplit(link)
            return link if parts.scheme in ("http", "https") and parts.hostname and not parts.username else ""
        except ValueError:
            return ""

    def render_detail(self):
        paper = self.selected_paper()
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        if not paper:
            self.detail.insert("end", self.t("选择频道并检索，或从历史中打开一篇论文。"), "muted")
        else:
            self.detail.insert("end", paper["title"] + "\n", "title")
            authors = [author.get("name") for author in paper.get("authors") or [] if author.get("name")]
            published = str(paper.get("publicationDate") or paper.get("year") or self.t("日期未知"))
            meta = [published, paper.get("venue") or "", " / ".join(self.t(source) for source in paper["sources"])]
            self.detail.insert("end", " · ".join(filter(None, meta)) + "\n", "muted")
            if authors:
                self.detail.insert("end", ", ".join(authors) + "\n", "muted")
            if paper.get("keywords"):
                keyword_heading = "OpenAlex 索引关键词" if paper.get("keyword_source") == "OpenAlex" else "来源提供的关键词"
                self.detail_heading(keyword_heading)
                self.detail.insert("end", " · ".join(paper["keywords"]) + "\n")
            else:
                self.detail_heading("来源关键词")
                self.detail.insert("end", self.t("该来源未随这条记录提供关键词。") + "\n", "muted")
            subjects = list(dict.fromkeys(
                list(paper.get("fieldsOfStudy") or []) + [
                    item["category"] for item in paper.get("s2FieldsOfStudy") or [] if item.get("category")
                ]
            ))
            if subjects:
                self.detail_heading("学科分类")
                self.detail.insert("end", " · ".join(subjects) + "\n")
            self.detail_heading("命中的检索词")
            for number, term_a, term_b in paper["matches"]:
                self.detail.insert("end", self.t("频道 {number} · {term_a} × {term_b}",
                                                 number=number, term_a=term_a, term_b=term_b) + "\n")
            self.detail_heading("原文摘要")
            self.detail.insert("end", (paper.get("abstract") or self.t("该来源未提供摘要。")) + "\n")
            key = translation_key(paper, self.settings["language"])
            translated = paper["translations"].get(key)
            if translated:
                self.detail_heading("摘要译文 · {language}", language=self.t(self.settings["language"]))
                self.detail.insert("end", translated + "\n")
        self.detail.configure(state="disabled")
        self.favorite_button.configure(state="normal" if paper else "disabled",
                                       text=self.t("取消收藏" if paper and paper["favorite"] else "收藏论文"))
        self.link_button.configure(state="normal" if paper and self.record_link(paper) else "disabled")
        self.translate_button.configure(state="normal" if paper and paper.get("abstract") and not self.busy else "disabled")
        self.arrange_detail_actions()

    def arrange_detail_actions(self):
        width = self.detail_actions.winfo_width()
        if width <= 1:
            return
        needed = sum(button.winfo_reqwidth() for button in
                     (self.favorite_button, self.link_button, self.translate_button)) + 14
        wrapped = needed > width
        if wrapped == self.actions_wrapped:
            return
        self.actions_wrapped = wrapped
        if wrapped:
            self.translate_button.grid_configure(row=1, column=0, columnspan=2, pady=(4, 0))
        else:
            self.translate_button.grid_configure(row=0, column=2, columnspan=1, pady=0)

    def detail_heading(self, caption, **fields):
        self.detail.insert("end", f"\n{self.t(caption, **fields)}\n", "heading")

    def toggle_favorite(self):
        paper = self.selected_paper()
        if paper:
            self.library.set_favorite(paper["record_id"], not paper["favorite"])
            self.render_library(self.current_ids, self.current_favorites, paper["record_id"])

    def open_paper(self):
        paper = self.selected_paper()
        link = self.record_link(paper) if paper else ""
        if link:
            webbrowser.open(link)

    def start_search(self, *, automatic=False):
        if self.busy:
            return
        settings = deepcopy(self.settings)
        provider = settings["provider"]
        key_endpoint = settings["custom"].get("endpoint", "") if provider == "自定义 JSON" else ""
        fallback = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "") if provider == "Semantic Scholar" else ""
        try:
            key = self.secrets.get(self.key_slot("search", provider, key_endpoint), fallback)
            search, query_for = make_search(provider, key, settings["budget"], settings["custom"])
            channels, exclude = bot.load_channels(self.config_data)
            selected = ALL if automatic else self.picked_channel.get()
            active = channels if selected == ALL else [
                row for row in channels if self.channel_key(row) == selected
            ]
            if not active:
                raise ValueError("请先在「频道与屏蔽词」添加一个频道。")
            if not automatic:
                self.settings["channel"] = selected
                write_json(self.directory / "settings.json", self.settings)
            if selected == ALL:
                started = time.time()
                interval = self.interval_seconds() if automatic else 0
                if not self.library.start_search_round(started, interval):
                    self.last_round = self.library.last_search_started()
                    self.schedule_issue = None
                    self.refresh_schedule_status()
                    if automatic:
                        return
                else:
                    self.last_round = started
                    self.schedule_issue = None
        except (ValueError, OSError, sqlite3.Error) as error:
            if automatic:
                self.schedule_issue = error
                self.refresh_schedule_status()
            else:
                self.show_error("无法开始检索", error)
            return

        def fetch():
            today = datetime.now(bot.JAPAN_TIME).date()
            papers, failures, _ = bot.scan(active, {"last_complete": {}}, today, search,
                                           lookback=settings["lookback"], query_for=query_for)
            ranked = bot.ranked_papers(papers, active, exclude, set())
            return self.library.ingest(ranked, provider), failures, search.used

        def show(result):
            ids, failures, count = result
            if not automatic:
                self.render_library(ids)
            elif self.current_ids is None:
                current = self.selected_paper()
                position = self.detail.yview()[0]
                self.render_library(favorites=self.current_favorites, select=current["record_id"] if current else None)
                self.detail.yview_moveto(position)
            else:
                self.render_detail()
            caption = ("自动检索 · {provider} · {count} 篇符合条件 · {requests} 次请求" if automatic
                       else "{provider} 返回 {count} 篇符合条件的论文 · {requests} 次请求")
            self.set_status(caption,
                            provider=provider, count=len(ids), requests=count, failures=failures)

        caption = "正在通过 {provider} 自动检索……" if automatic else "正在通过 {provider} 检索……"
        self.run_task(caption, fetch, show, automatic=automatic, provider=provider)

    def start_translation(self):
        paper = self.selected_paper()
        if self.busy or not paper or not paper.get("abstract"):
            return
        settings = self.settings
        provider, endpoint = settings["translator"], settings["translation_endpoint"]
        language = settings["language"]
        if provider == "关闭":
            self.set_status("请先在「API 与设置」选择翻译服务。")
            return
        cache_key = translation_key(paper, language)
        if cache_key in paper["translations"]:
            self.set_status("已显示保存的译文。")
            self.detail.see("end")
            return
        try:
            key = self.secrets.get(self.key_slot("translation", provider, endpoint))
        except (ValueError, OSError) as error:
            self.show_error("无法读取翻译密钥", error)
            return

        def fetch():
            translated = translate_abstract(provider, endpoint, settings["translation_model"], key, language, paper["abstract"])
            self.library.set_translation(paper["record_id"], cache_key, translated)

        def show(_):
            current = self.selected_paper()
            self.render_library(self.current_ids, self.current_favorites, current["record_id"] if current else None)
            if current and current["record_id"] == paper["record_id"]:
                self.detail.see("end")
            self.set_status("已保存{language}译文。", language=language)

        self.run_task("正在使用 {provider} 翻译摘要……", fetch, show, provider=provider)

    def run_task(self, caption, operation, callback, *, automatic=False, **fields):
        self.busy = True
        self.auto_running = automatic
        self.search_button.configure(state="disabled")
        self.progress_bar.start(15)
        self.set_status(caption, **fields)
        self.refresh_schedule_status()
        self.render_detail()

        def worker():
            try:
                self.events.put((callback, operation(), None, automatic))
            except (OSError, ValueError, bot.ServiceError) as error:
                self.events.put((callback, None, error, automatic))
            except Exception as error:
                self.events.put((callback, None, f"操作中断（{type(error).__name__}）", automatic))

        Thread(target=worker, daemon=True).start()

    def process_events(self):
        self.poll_timer = None
        try:
            callback, result, error, automatic = self.events.get_nowait()
        except Empty:
            pass
        else:
            self.busy = False
            self.auto_running = False
            self.progress_bar.stop()
            self.search_button.configure(state="normal")
            if error:
                if automatic:
                    self.set_status("自动检索未完成（{reason}）", reason=error)
                else:
                    self.set_status(error)
                self.render_detail()
                if not automatic:
                    self.show_error("操作未完成", error)
            else:
                callback(result)
            self.refresh_schedule_status()
        self.poll_timer = self.after(100, self.process_events)

    def destroy(self):
        for name in ("poll_timer", "schedule_timer"):
            timer = getattr(self, name, None)
            if timer is not None:
                self.after_cancel(timer)
                setattr(self, name, None)
        super().destroy()


if __name__ == "__main__":
    try:
        PaperWatch().mainloop()
    except (OSError, ValueError, tk.TclError) as error:
        try:
            language = saved_settings(DATA_DIRECTORY)["ui_language"]
        except (OSError, ValueError):
            language = "zh"
        messagebox.showerror(translate(language, "无法启动论文追踪"), translate_error(language, error))
