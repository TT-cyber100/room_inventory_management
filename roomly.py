#!/usr/bin/env python3
"""Roomly — 单文件桌面房间物品管理器。"""

import argparse
import json
import math
import os
import tempfile
import uuid
import webbrowser
import tkinter as tk

from dataclasses import dataclass, field, asdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog


BG = "#f6f4ee"
INK = "#35463f"
GREEN = "#54816d"

KINDS = ("Bed", "Desk", "Wardrobe", "Bookshelf", "Storage box")
KIND_NAMES = {
    "Bed": "床",
    "Desk": "书桌",
    "Wardrobe": "衣柜",
    "Bookshelf": "书架",
    "Storage box": "收纳箱",
}


def uid():
    return uuid.uuid4().hex


@dataclass
class Item:
    name: str
    category: str = "其他"
    quantity: int = 1
    price: str = ""
    purchase_date: str = ""
    store: str = ""
    url: str = ""
    notes: str = ""
    id: str = field(default_factory=uid)

    def __post_init__(self):
        self.name = self.name.strip()

        if not self.name:
            raise ValueError("请输入物品名称。")

        if type(self.quantity) is not int or self.quantity < 1:
            raise ValueError("数量必须是正整数。")

        if self.price:
            try:
                value = Decimal(self.price)
            except InvalidOperation as exc:
                raise ValueError("价格必须是数字。") from exc

            if not value.is_finite() or value < 0:
                raise ValueError("价格必须是有限的非负数。")

        if self.purchase_date:
            try:
                date.fromisoformat(self.purchase_date)
            except ValueError as exc:
                raise ValueError("请输入有效日期，格式为 YYYY-MM-DD。") from exc

        if self.url and not self.url.startswith(("https://", "http://")):
            raise ValueError("购买链接必须以 https:// 或 http:// 开头。")


@dataclass
class Furniture:
    name: str
    kind: str
    x: float
    y: float
    items: list[Item] = field(default_factory=list)
    id: str = field(default_factory=uid)


@dataclass
class Room:
    furniture: list[Furniture] = field(default_factory=list)
    width: int = 900
    height: int = 660


def sample_room():
    return Room([
        Furniture(
            "我的床", "Bed", 75, 70,
            [Item("备用床单", "家居", price="39.90", notes="放在床下收纳袋里。")]
        ),
        Furniture(
            "学习桌", "Desk", 550, 65,
            [
                Item("笔记本", "文具", 3, "4.50"),
                Item("耳机", "电子产品", price="79.00", store="校园商店"),
            ]
        ),
        Furniture(
            "日常衣柜", "Wardrobe", 90, 380,
            [Item("毛衣", "衣物", 2, "25.00")]
        ),
        Furniture(
            "小书架", "Bookshelf", 550, 365,
            [Item("设计书", "书籍", notes="朋友送的，价格未知。")]
        ),
        Furniture(
            "纪念品箱", "Storage box", 350, 420,
            [Item("旅行明信片", "纪念品", 12)]
        ),
    ])


class InventoryManager:
    def __init__(self, path):
        self.path = Path(path)
        self.room = Room()
        self.warning = ""
        self.read_only = False
        self.load()

    def load(self):
        if not self.path.exists():
            self.room = sample_room()
            return

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))

            if data.get("version") != 1:
                raise ValueError("不支持的数据版本。")

            furniture = []
            ids = set()

            for raw in data["room"]["furniture"]:
                raw = dict(raw)
                raw["items"] = [Item(**i) for i in raw["items"]]
                f = Furniture(**raw)

                if not f.name.strip() or f.kind not in KINDS:
                    raise ValueError("家具数据无效。")

                if not (0 <= f.x <= 720 and 0 <= f.y <= 500):
                    raise ValueError("家具坐标无效。")

                for obj in [f, *f.items]:
                    if not obj.id or obj.id in ids:
                        raise ValueError("数据标识缺失或重复。")
                    ids.add(obj.id)

                furniture.append(f)

            self.room = Room(furniture)

        except (
            OSError, ValueError, TypeError, KeyError, AttributeError
        ) as exc:
            self.warning = (
                f"无法读取：{self.path}\n\n{exc}\n\n"
                "原文件已受到保护，不会被覆盖。\n"
                "请备份并检查原文件，或使用 --data 指定一个新文件。"
            )
            self.read_only = True
            self.room = Room()

    def save(self):
        if self.read_only:
            raise OSError(
                "原数据文件已受到保护。\n"
                "请修复原文件，或使用 --data 指定新文件后重新启动。"
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"version": 1, "room": asdict(self.room)},
            indent=2,
            ensure_ascii=False,
        )

        temporary = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                delete=False,
            ) as stream:
                temporary = stream.name
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())

            os.replace(temporary, self.path)

        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def search(self, query):
        query = query.casefold().strip()
        return [
            (f, item)
            for f in self.room.furniture
            for item in f.items
            if query in " ".join(
                (item.name, item.category, item.notes, f.name)
            ).casefold()
        ]

    def summary(self):
        items = [
            item
            for f in self.room.furniture
            for item in f.items
        ]

        categories = {}

        for item in items:
            if item.price:
                value = Decimal(item.price) * item.quantity
                categories[item.category] = (
                    categories.get(item.category, Decimal(0)) + value
                )

        count = sum(item.quantity for item in items)
        value = sum(categories.values(), Decimal(0))
        unknown = sum(item.quantity for item in items if not item.price)

        return count, value, unknown, categories


class Scene3D:
    """等距投影房间，以及房间内的物品浮层。"""

    def project(self, x, y, z=0):
        return (
            370 + (x - y) * 0.55,
            155 + (x + y) * 0.30 - z * 0.72,
        )

    def unproject(self, px, py):
        a = (px - 370) / 0.55
        b = (py - 155) / 0.30
        return (a + b) / 2, (b - a) / 2

    def draw(self):
        c = self.canvas
        c.delete("all")
        c.configure(bg="#eee5db")

        self.scale = min(
            max(1, c.winfo_width()) / 900,
            max(1, c.winfo_height()) / 660,
        )
        s = self.scale

        def polygon(points, fill, tag="room", outline="#82715e"):
            coordinates = [
                value * s
                for point in points
                for value in self.project(*point)
            ]
            c.create_polygon(
                coordinates,
                fill=fill,
                outline=outline,
                width=max(1, 2 * s),
                joinstyle="miter",
                tags=tag,
            )

        def plane(x, y, w, d, z, fill, tag="room"):
            polygon(
                [
                    (x, y, z),
                    (x + w, y, z),
                    (x + w, y + d, z),
                    (x, y + d, z),
                ],
                fill,
                tag,
            )

        def box(x, y, w, d, h, colors, tag="room", base=0):
            polygon(
                [
                    (x, y + d, base),
                    (x + w, y + d, base),
                    (x + w, y + d, base + h),
                    (x, y + d, base + h),
                ],
                colors[1],
                tag,
            )
            polygon(
                [
                    (x + w, y, base),
                    (x + w, y + d, base),
                    (x + w, y + d, base + h),
                    (x + w, y, base + h),
                ],
                colors[2],
                tag,
            )
            plane(x, y, w, d, base + h, colors[0], tag)

        # 两面墙。
        polygon(
            [(0, 0, 0), (900, 0, 0), (900, 0, 180), (0, 0, 180)],
            "#c8d3b9",
        )
        polygon(
            [(0, 0, 0), (0, 660, 0), (0, 660, 180), (0, 0, 180)],
            "#e0d3c2",
        )

        # 木地板。
        plane(0, 0, 900, 660, 0, "#dec19b")

        for y in range(0, 660, 55):
            for x in range(0, 900, 150):
                color = (
                    "#e2c7a4"
                    if (x // 150 + y // 55) % 2
                    else "#d9ba94"
                )
                plane(x, y, min(150, 900 - x), 55, 0, color)

        # 踢脚线。
        polygon(
            [(0, 0, 0), (900, 0, 0), (900, 0, 10), (0, 0, 10)],
            "#f7ead5",
        )
        polygon(
            [(0, 0, 0), (0, 660, 0), (0, 660, 10), (0, 0, 10)],
            "#f7ead5",
        )

        # 窗户。
        for a, b in [(340, 90), (455, 90), (340, 133), (455, 133)]:
            polygon(
                [
                    (a, 0, b),
                    (a + 100, 0, b),
                    (a + 100, 0, b + 35),
                    (a, 0, b + 35),
                ],
                "#b4d9da",
                outline="#fff1d9",
            )

        # 地毯。
        plane(270, 185, 350, 290, 1, "#b5c8a4")
        plane(280, 195, 330, 270, 2, "#cbd8b8")

        self.scene_objects = {}

        objects = sorted(
            enumerate(self.manager.room.furniture),
            key=lambda pair: pair[1].x + pair[1].y,
        )

        for index, f in objects:
            tag = f"furniture_{index}"
            self.scene_objects[tag] = f

            x, y = f.x, f.y
            w, d = (150, 190) if f.kind == "Bed" else (170, 100)

            # 地面阴影。
            plane(x + 12, y + 12, w, d, 1, "#c6ad90", tag)

            if f.kind == "Bed":
                box(
                    x, y, w, d, 28,
                    ("#d8af87", "#b68b64", "#99704e"), tag,
                )
                box(
                    x, y, w, 14, 75,
                    ("#c9a17c", "#b68b64", "#99704e"), tag,
                )
                box(
                    x + 7, y + 12, w - 14, d - 20, 20,
                    ("#f4dfcb", "#dfb7a7", "#caa18d"), tag, 28,
                )
                box(
                    x + 16, y + 25, w - 32, 38, 8,
                    ("#fff2db", "#e3ccb4", "#cfb496"), tag, 48,
                )
                plane(x + 7, y + 80, w - 14, 12, 49, "#f8d9cc", tag)

            elif f.kind == "Desk":
                for xx, yy in [
                    (x + 8, y + 8),
                    (x + w - 20, y + 8),
                    (x + 8, y + d - 20),
                    (x + w - 20, y + d - 20),
                ]:
                    box(
                        xx, yy, 12, 12, 65,
                        ("#c1a078", "#b0926e", "#907551"), tag,
                    )

                box(
                    x, y, w, d, 12,
                    ("#e4c49a", "#c5a073", "#ab8359"), tag, 65,
                )
                box(
                    x + 55, y + 15, 65, 12, 48,
                    ("#81968c", "#536d64", "#41564f"), tag, 77,
                )
                plane(x + 58, y + 40, 62, 28, 78, "#ebe7d5", tag)
                box(
                    x + 13, y + 15, 24, 22, 24,
                    ("#d9ab8d", "#bf8f75", "#a6785f"), tag, 77,
                )
                box(
                    x + 12, y + 15, 27, 25, 4,
                    ("#88a67e", "#74966c", "#59764f"), tag, 101,
                )

            elif f.kind == "Wardrobe":
                box(
                    x, y, w, d, 170,
                    ("#cad2b6", "#b6c2a2", "#94a385"), tag,
                )

                for xx in [x + 7, x + 89]:
                    polygon(
                        [
                            (xx, y + d + 1, 10),
                            (xx + 74, y + d + 1, 10),
                            (xx + 74, y + d + 1, 158),
                            (xx, y + d + 1, 158),
                        ],
                        "#c7cfb3", tag,
                    )

                for xx in [x + 72, x + 94]:
                    polygon(
                        [
                            (xx, y + d + 2, 75),
                            (xx + 4, y + d + 2, 75),
                            (xx + 4, y + d + 2, 93),
                            (xx, y + d + 2, 93),
                        ],
                        "#7d8769", tag,
                    )

            elif f.kind == "Bookshelf":
                box(
                    x, y, w, d, 132,
                    ("#cfb18b", "#b4936e", "#96734f"), tag,
                )

                colors = (
                    "#abc1a0", "#d8a190", "#b3a8c4",
                    "#e1c68f", "#94b7b6", "#dfb397",
                )

                for z in [12, 53, 94]:
                    polygon(
                        [
                            (x + 8, y + d + 1, z),
                            (x + w - 8, y + d + 1, z),
                            (x + w - 8, y + d + 1, z + 30),
                            (x + 8, y + d + 1, z + 30),
                        ],
                        "#79664f", tag,
                    )

                    for j, color in enumerate(colors):
                        xx = x + 14 + j * 24
                        polygon(
                            [
                                (xx, y + d + 2, z + 2),
                                (xx + 16, y + d + 2, z + 2),
                                (xx + 16, y + d + 2, z + 25),
                                (xx, y + d + 2, z + 25),
                            ],
                            color, tag,
                        )

            else:
                box(
                    x, y, w, d, 50,
                    ("#cfbfdc", "#b2a1c2", "#9583a8"), tag,
                )
                box(
                    x - 3, y - 3, w + 6, d + 6, 8,
                    ("#e0d2e7", "#c8b7d4", "#aa96b8"), tag, 50,
                )
                polygon(
                    [
                        (x + 65, y + d + 1, 16),
                        (x + 105, y + d + 1, 16),
                        (x + 105, y + d + 1, 33),
                        (x + 65, y + d + 1, 33),
                    ],
                    "#fff0d8", tag,
                )

            if f is self.selected:
                points = [
                    self.project(x - 5, y - 5, 2),
                    self.project(x + w + 5, y - 5, 2),
                    self.project(x + w + 5, y + d + 5, 2),
                    self.project(x - 5, y + d + 5, 2),
                    self.project(x - 5, y - 5, 2),
                ]
                c.create_line(
                    [v * s for point in points for v in point],
                    fill="#4a7c63", width=3, tags=tag,
                )

            tx, ty = self.project(x + w / 2, y + d + 24)
            c.create_text(
                tx * s, ty * s,
                text=f.name,
                fill="#3d503c",
                font=("Helvetica", max(9, int(11 * s))),
                tags=tag,
            )

        if self.overlay_open:
            if any(f is self.selected for f in self.manager.room.furniture):
                self.draw_overlay()
            else:
                self.overlay_open = False

    def draw_overlay(self):
        c = self.canvas
        width, height = c.winfo_width(), c.winfo_height()

        # Canvas 用点阵模拟透明，不会创建新的系统窗口。
        c.create_rectangle(
            0, 0, width, height,
            fill="#253c32", stipple="gray50", outline="",
            tags="overlay",
        )

        x = 24
        h = min(430, height - 44)
        y = max(22, (height - h) / 2)
        w = max(150, width - 48)

        self.overlay_bounds = (x, y, x + w, y + h)

        c.create_rectangle(
            x + 6, y + 8, x + w + 6, y + h + 8,
            fill="#35463f", stipple="gray50", outline="",
        )
        c.create_rectangle(
            x, y, x + w, y + h,
            fill="#fffaf0", stipple="gray75",
            outline="#f8f3e6", width=2,
        )
        c.create_text(
            x + 22, y + 28,
            text=self.selected.name,
            anchor="w", fill="#263e32",
            font=("Helvetica", 17, "bold"),
            width=max(80, w - 95),
        )
        c.create_text(
            x + w - 25, y + 25,
            text="×", fill=INK,
            font=("Helvetica", 24),
            tags="close_overlay",
        )

        items = self.selected.items

        c.create_text(
            x + 22, y + 62,
            text=f"共 {len(items)} 种物品 · 滚动查看 · 点击物品编辑",
            anchor="w", fill=GREEN,
            font=("Helvetica", 10),
        )

        visible = max(1, int((h - 133) // 52))
        self.overlay_offset = max(
            0,
            min(self.overlay_offset, max(0, len(items) - visible)),
        )
        self.overlay_rows = {}

        visible_items = items[
            self.overlay_offset:self.overlay_offset + visible
        ]

        for row, item in enumerate(visible_items):
            yy = y + 90 + row * 52
            tag = f"overlay_item_{row}"
            self.overlay_rows[tag] = item

            c.create_rectangle(
                x + 16, yy - 8, x + w - 16, yy + 37,
                fill="#faf6ea", outline="#e0e5d6", tags=tag,
            )
            c.create_text(
                x + 28, yy + 3,
                text=item.name, anchor="w",
                font=("Helvetica", 12, "bold"),
                fill=INK, width=max(80, w - 110), tags=tag,
            )
            c.create_text(
                x + 28, yy + 23,
                text=f"{item.category} · 单价：{item.price or '未知'}",
                anchor="w", fill="#657b69",
                font=("Helvetica", 10),
                width=max(80, w - 110), tags=tag,
            )
            c.create_text(
                x + w - 32, yy + 10,
                text=f"×{item.quantity}",
                anchor="e", fill=GREEN, tags=tag,
            )

        if not items:
            c.create_text(
                x + w / 2, y + h / 2,
                text="这里还没有物品。\n点击下方按钮，添加第一件物品。",
                justify="center", fill="#657b69",
                font=("Helvetica", 12),
            )

        c.create_rectangle(
            x + 18, y + h - 43, x + w - 18, y + h - 12,
            fill=GREEN, outline="", tags="overlay_add",
        )
        c.create_text(
            x + w / 2, y + h - 27,
            text="+ 添加物品", fill="white",
            font=("Helvetica", 11, "bold"), tags="overlay_add",
        )

    def close_overlay(self, event=None):
        self.overlay_open = False
        self.draw()

    def scene_scroll(self, event):
        if self.overlay_open:
            upward = (
                getattr(event, "num", None) == 4
                or getattr(event, "delta", 0) > 0
            )
            self.overlay_offset += -1 if upward else 1
            self.draw()
            return "break"

    def scene_tags(self, event):
        objects = self.canvas.find_overlapping(
            event.x, event.y, event.x, event.y
        )
        return [
            tag
            for obj in reversed(objects)
            for tag in self.canvas.gettags(obj)
        ]

    def press(self, event):
        tags = self.scene_tags(event)

        if self.overlay_open:
            if "close_overlay" in tags:
                self.close_overlay()

            elif "overlay_add" in tags:
                self.close_overlay()
                self.edit_item()

            else:
                for tag in tags:
                    if tag in self.overlay_rows:
                        item = self.overlay_rows[tag]
                        source = self.selected
                        self.close_overlay()
                        self.edit_item(source, item)
                        return

                x, y, right, bottom = self.overlay_bounds

                if not (
                    x <= event.x <= right
                    and y <= event.y <= bottom
                ):
                    self.close_overlay()

            return

        for tag in tags:
            if tag in self.scene_objects:
                self.selected = self.scene_objects[tag]

                px, py = self.unproject(
                    event.x / self.scale,
                    event.y / self.scale,
                )

                self.drag = (
                    px - self.selected.x,
                    py - self.selected.y,
                )
                self.press_point = (event.x, event.y)
                self.scene_moved = False
                self.query.set("")
                self.refresh()
                return

    def motion(self, event):
        if self.drag and self.selected:
            distance = math.hypot(
                event.x - self.press_point[0],
                event.y - self.press_point[1],
            )

            if distance < 5 and not self.scene_moved:
                return

            self.scene_moved = True

            px, py = self.unproject(
                event.x / self.scale,
                event.y / self.scale,
            )

            self.selected.x = max(24, min(680, px - self.drag[0]))
            self.selected.y = max(38, min(450, py - self.drag[1]))
            self.draw()

    def release(self, event):
        if self.drag:
            self.drag = None

            if self.scene_moved:
                self.persist()
            else:
                self.overlay_open = True
                self.overlay_offset = 0
                self.draw()

    def bind_scene(self):
        self.bind("<Escape>", self.close_overlay)
        self.canvas.bind("<MouseWheel>", self.scene_scroll)
        self.canvas.bind("<Button-4>", self.scene_scroll)
        self.canvas.bind("<Button-5>", self.scene_scroll)


class App(Scene3D, tk.Tk):
    def __init__(self, path):
        super().__init__()

        self.title("Roomly · 每件物品都有自己的位置")
        self.geometry("1280x800")
        self.minsize(1000, 680)
        self.configure(bg=BG)

        self.manager = InventoryManager(path)
        self.selected = None
        self.drag = None
        self.overlay_open = False
        self.overlay_offset = 0
        self.overlay_rows = {}
        self.scene_objects = {}
        self.matches = {}

        self.query = tk.StringVar()
        self.status = tk.StringVar(
            value="欢迎回家 · 点击家具查看物品，拖动家具调整布局"
        )

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            ".", font=("Helvetica", 11),
            background=BG, foreground=INK,
        )
        style.configure("TButton", padding=7)
        style.configure(
            "Treeview", rowheight=30,
            background="#fffefa", fieldbackground="#fffefa",
        )

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.show_start_screen()

    def show_start_screen(self):
        self.start_screen = tk.Frame(self, bg=BG)
        self.start_screen.pack(fill="both", expand=True)

        content = tk.Frame(self.start_screen, bg=BG)
        content.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(
            content, text="roomly", font=("Helvetica", 24, "bold"),
            bg=BG, fg=GREEN,
        ).pack(pady=(0, 24))
        tk.Label(
            content, text="your room your space",
            font=("Helvetica", 38, "bold"), bg=BG, fg=INK,
        ).pack()
        tk.Label(
            content, text="每件物品都有自己的位置",
            font=("Helvetica", 14), bg=BG, fg="#859189",
        ).pack(pady=(18, 36))
        self.start_button = ttk.Button(
            content, text="进入我的房间", command=self.enter_room,
        )
        self.start_button.pack(ipadx=24, ipady=6)
        self.start_button.focus_set()
        self.start_button.bind("<Return>", lambda event: self.enter_room())

    def enter_room(self):
        if not self.start_screen.winfo_exists():
            return
        self.start_screen.destroy()
        self.build_interface()
        self.refresh()

        if self.manager.warning:
            self.after(
                100,
                lambda: messagebox.showwarning(
                    "数据文件已保护",
                    self.manager.warning,
                    parent=self,
                ),
            )

    def build_interface(self):
        top = tk.Frame(self, bg=BG, padx=24, pady=18)
        top.pack(fill="x")

        tk.Label(
            top, text="roomly",
            font=("Helvetica", 26, "bold"),
            fg=GREEN, bg=BG,
        ).pack(side="left")

        tk.Label(
            top, text="每件物品都有自己的位置",
            bg=BG, fg="#859189",
        ).pack(side="left", padx=12)

        ttk.Button(
            top, text="库存统计",
            command=self.dashboard,
        ).pack(side="right")

        ttk.Entry(
            top, textvariable=self.query, width=24,
        ).pack(side="right", padx=12)

        tk.Label(
            top, text="搜索", bg=BG, fg=GREEN,
        ).pack(side="right")

        self.query.trace_add(
            "write", lambda *_: self.refresh_inventory()
        )

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=20)

        left = tk.Frame(body, bg=BG, width=160)
        left.pack(side="left", fill="y", padx=(0, 12))

        tk.Label(
            left, text="我的房间", bg=BG, fg=GREEN,
            font=("Helvetica", 12, "bold"),
        ).pack(anchor="w", pady=12)

        self.flist = tk.Listbox(
            left, width=16,
            bg="#ebece3", fg=INK,
            relief="flat", highlightthickness=0,
            selectbackground=GREEN,
            activestyle="none", exportselection=False,
            font=("Helvetica", 12),
        )
        self.flist.pack(fill="both", expand=True)
        self.flist.bind("<<ListboxSelect>>", self.list_select)

        for text, command in [
            ("+ 添加家具", self.add_furniture),
            ("重命名家具", self.rename),
            ("删除家具", self.delete_furniture),
        ]:
            ttk.Button(
                left, text=text, command=command,
            ).pack(fill="x", pady=5)

        right = tk.Frame(body, bg=BG, width=260)
        right.pack(side="right", fill="y", padx=(12, 0))

        self.panel_title = tk.Label(
            right, text="物品清单",
            bg=BG, fg=INK,
            font=("Helvetica", 15, "bold"),
            wraplength=250,
        )
        self.panel_title.pack(anchor="w", pady=12)

        self.tree = ttk.Treeview(
            right, columns=("quantity",),
            show="tree headings", height=9,
        )
        self.tree.heading("#0", text="物品 / 位置")
        self.tree.heading("quantity", text="数量")
        self.tree.column("#0", width=195)
        self.tree.column("quantity", width=45, stretch=False)
        self.tree.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", self.item_select)

        self.details = tk.Label(
            right,
            text="点击家具查看存放的物品。",
            justify="left", anchor="nw",
            wraplength=250, bg=BG, fg=INK,
        )
        self.details.pack(fill="both", expand=True, pady=18)

        self.link = ttk.Button(
            right, text="打开购买链接",
            command=self.open_link,
        )
        self.link.pack(fill="x", pady=4)

        for text, command in [
            ("+ 添加物品", self.edit_item),
            ("编辑 / 移动物品", self.edit_selected),
            ("删除物品", self.delete_item),
        ]:
            ttk.Button(
                right, text=text, command=command,
            ).pack(fill="x", pady=4)

        center = tk.Frame(body, bg=BG)
        center.pack(fill="both", expand=True)

        tk.Label(
            center, text="你的温馨小空间",
            bg=BG, fg=INK,
            font=("Helvetica", 17, "bold"),
        ).pack(anchor="w", pady=10)

        tk.Label(
            center,
            text="点击家具查看物品 · 拖动家具布置房间 · Esc 关闭浮层",
            bg=BG, fg="#859189",
        ).pack(anchor="w", pady=(0, 12))

        self.canvas = tk.Canvas(
            center, bg="#eee5db", highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _: self.draw())
        self.canvas.bind("<Button-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.motion)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.bind_scene()

        tk.Label(
            self, textvariable=self.status,
            anchor="w", bg=BG, fg=GREEN,
            padx=24, pady=12,
        ).pack(fill="x")

    def persist(self):
        try:
            self.manager.save()
            self.status.set("已保存到本机 · 房间数据已更新")
            return True
        except OSError as exc:
            self.status.set("修改尚未保存")
            messagebox.showerror("保存失败", str(exc), parent=self)
            return False

    def close(self):
        if self.persist() or messagebox.askyesno(
            "修改尚未保存",
            "放弃未保存的修改并退出？",
            parent=self,
        ):
            self.destroy()

    def refresh(self):
        self.flist.delete(0, "end")

        for f in self.manager.room.furniture:
            self.flist.insert("end", f.name)
            if f is self.selected:
                self.flist.selection_set(self.flist.size() - 1)

        self.refresh_inventory()
        self.draw()

    def list_select(self, event):
        if self.flist.curselection():
            index = self.flist.curselection()[0]
            self.selected = self.manager.room.furniture[index]
            self.overlay_open = False
            self.query.set("")
            self.refresh()

    def refresh_inventory(self):
        self.tree.delete(*self.tree.get_children())
        self.matches = {}

        searching = bool(self.query.get().strip())

        if searching:
            matches = self.manager.search(self.query.get())
        elif self.selected:
            matches = [
                (self.selected, item)
                for item in self.selected.items
            ]
        else:
            matches = []

        title = (
            "搜索结果" if searching
            else self.selected.name if self.selected
            else "物品清单"
        )
        self.panel_title.config(text=title)

        for f, item in matches:
            self.matches[item.id] = (f, item)
            text = (
                f"{item.name} · {f.name}"
                if searching else item.name
            )
            self.tree.insert(
                "", "end",
                iid=item.id,
                text=text,
                values=(item.quantity,),
            )

        if matches:
            text = "选择物品查看购买信息。"
        elif searching:
            text = "没有找到匹配的物品。"
        elif self.selected:
            text = "这里还没有物品。\n点击“添加物品”开始整理。"
        else:
            text = "选择家具，或搜索整个房间。"

        self.details.config(text=text)
        self.link.state(["disabled"])

    def current_item(self):
        selected = self.tree.selection()
        return self.matches.get(selected[0]) if selected else None

    def item_select(self, event=None):
        match = self.current_item()

        if not match:
            return

        f, item = match
        self.selected = f
        self.overlay_open = False
        self.draw()

        self.details.config(text=(
            f"{item.name}\n\n"
            f"分类：{item.category}\n"
            f"数量：{item.quantity}\n"
            f"位置：{f.name}\n\n"
            f"单价：{item.price or '未知'}\n"
            f"购买日期：{item.purchase_date or '未记录'}\n"
            f"商店：{item.store or '未记录'}\n\n"
            f"备注：{item.notes or '暂无'}"
        ))

        self.link.state(
            ["!disabled"] if item.url else ["disabled"]
        )

    def open_link(self):
        match = self.current_item()
        if match and match[1].url:
            webbrowser.open(match[1].url)

    def add_furniture(self):
        win = tk.Toplevel(self)
        win.title("添加家具")
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="家具名称").pack(padx=25, pady=8)

        name = ttk.Entry(win, width=28)
        name.pack(padx=25)
        name.focus_set()

        kind = ttk.Combobox(
            win,
            values=[KIND_NAMES[k] for k in KINDS],
            state="readonly",
        )
        kind.current(4)
        kind.pack(padx=25, pady=12)

        def submit():
            if not name.get().strip():
                messagebox.showerror(
                    "需要名称", "请输入家具名称。", parent=win
                )
                return

            self.overlay_open = False
            self.selected = Furniture(
                name.get().strip(),
                KINDS[kind.current()],
                350, 230,
            )
            self.manager.room.furniture.append(self.selected)
            self.persist()
            self.refresh()
            win.destroy()

        ttk.Button(
            win, text="添加家具", command=submit,
        ).pack(pady=12)

    def rename(self):
        if not self.selected:
            return

        name = simpledialog.askstring(
            "重命名家具", "新名称：",
            initialvalue=self.selected.name,
            parent=self,
        )

        if name and name.strip():
            self.selected.name = name.strip()
            self.persist()
            self.refresh()

    def delete_furniture(self):
        if not self.selected:
            return

        confirmed = messagebox.askyesno(
            "删除家具",
            f"删除“{self.selected.name}”及其中的 "
            f"{len(self.selected.items)} 条物品记录？\n此操作不能撤销。",
            parent=self,
        )

        if confirmed:
            self.manager.room.furniture.remove(self.selected)
            self.selected = None
            self.overlay_open = False
            self.persist()
            self.refresh()

    def edit_selected(self):
        match = self.current_item()
        if match:
            self.edit_item(*match)
        else:
            messagebox.showinfo(
                "选择物品", "请先在物品清单中选择一件物品。", parent=self
            )

    def edit_item(self, source=None, item=None):
        source = source or self.selected

        if source is None:
            messagebox.showinfo(
                "选择位置", "请先选择或添加一件家具。", parent=self
            )
            return

        self.overlay_open = False
        self.draw()

        win = tk.Toplevel(self)
        win.title("编辑物品" if item else "添加物品")
        win.transient(self)
        win.grab_set()

        fields = [
            ("name", "物品名称 *"),
            ("category", "分类"),
            ("quantity", "数量 *"),
            ("price", "单价（可选）"),
            ("purchase_date", "日期 YYYY-MM-DD"),
            ("store", "商店"),
            ("url", "购买链接"),
            ("notes", "备注"),
        ]
        entries = {}

        for row, (key, label) in enumerate(fields):
            ttk.Label(win, text=label).grid(
                row=row, column=0,
                sticky="w", padx=18, pady=7,
            )

            entry = ttk.Entry(win, width=38)
            entry.grid(
                row=row, column=1, padx=18, pady=7,
            )

            if item:
                value = str(getattr(item, key))
            else:
                value = "1" if key == "quantity" else ""

            entry.insert(0, value)
            entries[key] = entry

        entries["name"].focus_set()

        ttk.Label(win, text="存放位置").grid(
            row=8, column=0, padx=18,
        )

        locations = self.manager.room.furniture
        destination = ttk.Combobox(
            win,
            values=[
                f"{n + 1}. {f.name}"
                for n, f in enumerate(locations)
            ],
            state="readonly",
            width=35,
        )
        destination.current(locations.index(source))
        destination.grid(
            row=8, column=1, padx=18, pady=8,
        )

        def submit():
            try:
                values = {
                    key: entry.get().strip()
                    for key, entry in entries.items()
                }
                values["quantity"] = int(values["quantity"])
                values["category"] = values["category"] or "其他"

                if item:
                    values["id"] = item.id

                replacement = Item(**values)

            except (ValueError, TypeError) as exc:
                messagebox.showerror(
                    "请检查物品信息", str(exc), parent=win
                )
                return

            if item:
                source.items.remove(item)

            target = locations[destination.current()]
            target.items.append(replacement)
            self.selected = target

            self.query.set("")
            self.persist()
            self.refresh()
            win.destroy()

        ttk.Button(
            win, text="保存物品", command=submit,
        ).grid(
            row=9, column=1, sticky="e",
            padx=18, pady=18,
        )

    def delete_item(self):
        match = self.current_item()

        if not match:
            messagebox.showinfo(
                "选择物品", "请先选择要删除的物品。", parent=self
            )
            return

        f, item = match

        if messagebox.askyesno(
            "删除物品",
            f"删除“{item.name}”？此操作不能撤销。",
            parent=self,
        ):
            f.items.remove(item)
            self.persist()
            self.refresh_inventory()
            self.draw()

    def dashboard(self):
        count, value, unknown, categories = self.manager.summary()

        win = tk.Toplevel(self)
        win.title("库存统计")
        win.configure(bg=BG)
        win.geometry("460x500")

        text = (
            "你的房间，一目了然\n\n"
            f"物品总数量：{count}\n"
            f"家具数量：{len(self.manager.room.furniture)}\n\n"
            f"已记录购买总值：{value:,.2f}\n"
            f"价格未知的物品：{unknown} 件\n\n"
            "分类价值\n"
        )
        text += "\n".join(
            f"{category}：{amount:,.2f}"
            for category, amount in sorted(categories.items())
        )
        text += (
            "\n\n总值按单价 × 数量计算。\n"
            "未知价格不会被当成零元。\n"
            "请为所有物品使用同一种货币。"
        )

        tk.Label(
            win, text=text,
            justify="left", anchor="nw",
            bg=BG, fg=INK,
            font=("Helvetica", 12),
            padx=28, pady=25,
            wraplength=390,
        ).pack(fill="both", expand=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Roomly · 立体房间物品管理"
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=Path.home() / ".roomly" / "room-3d.json",
        help="JSON 数据文件路径",
    )
    args = parser.parse_args()
    App(args.data).mainloop()
