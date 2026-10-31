import json
import os
import tempfile
import tkinter as tk
import webbrowser
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog
from uuid import uuid4

BG = "#f6f4ee"
GREEN = "#54816d"
INK = "#35463f"
KINDS = ["Bed", "Desk", "Wardrobe", "Bookshelf", "Storage box"]


def furniture(name, kind, x, y, items=None):
    return {
        "id": uuid4().hex, "name": name, "kind": kind,
        "x": x, "y": y, "items": items or []
    }


def sample():
    return [
        furniture("我的床", "Bed", 60, 60, [
            {"name": "备用床单", "category": "家居", "quantity": 1,
             "price": "", "purchase_date": "", "store": "",
             "url": "", "notes": "放在床下的收纳袋中"}
        ]),
        furniture("学习桌", "Desk", 450, 70, [
            {"name": "笔记本", "category": "文具", "quantity": 3,
             "price": "12.50", "purchase_date": "", "store": "",
             "url": "", "notes": ""}
        ]),
        furniture("衣柜", "Wardrobe", 60, 320),
        furniture("书架", "Bookshelf", 450, 320),
        furniture("收纳箱", "Storage box", 280, 390),
    ]


class Roomly(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Roomly · 每件物品都有自己的位置")
        self.geometry("1180x760")
        self.minsize(960, 640)
        self.configure(bg=BG)
        self.path = Path.home() / ".roomly" / "room.json"
        self.protected = False
        self.selected = None
        self.drag = None
        self.rows = {}
        self.query = tk.StringVar()
        self.status = tk.StringVar(value="欢迎回家 · 点击家具查看物品，拖动家具调整布局")
        self.room = self.load()

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Helvetica", 11), background=BG)
        style.configure("TButton", padding=7)
        style.configure("Treeview", rowheight=30)

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=20, pady=16)
        tk.Label(top, text="roomly", font=("Helvetica", 27, "bold"),
                 bg=BG, fg=GREEN).pack(side="left")
        ttk.Button(top, text="库存统计", command=self.dashboard).pack(side="right")
        entry = ttk.Entry(top, textvariable=self.query, width=24)
        entry.pack(side="right", padx=12)
        tk.Label(top, text="搜索物品", bg=BG, fg=INK).pack(side="right")
        self.query.trace_add("write", lambda *_: self.inventory())

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16)

        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="y", padx=(0, 12))
        tk.Label(left, text="我的房间", bg=BG, fg=GREEN,
                 font=("Helvetica", 14, "bold")).pack(pady=10)
        self.listbox = tk.Listbox(
            left, width=16, bg="#e9ecdf", fg=INK,
            selectbackground=GREEN, relief="flat", exportselection=False
        )
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.choose_list)
        for text, command in [
            ("添加家具", self.add_furniture),
            ("重命名", self.rename),
            ("删除家具", self.delete_furniture),
        ]:
            ttk.Button(left, text=text, command=command).pack(fill="x", pady=5)

        right = tk.Frame(body, bg=BG, width=260)
        right.pack(side="right", fill="y", padx=(12, 0))
        self.heading = tk.Label(
            right, text="物品清单", bg=BG, fg=INK,
            font=("Helvetica", 15, "bold"), wraplength=250
        )
        self.heading.pack(pady=10)
        self.tree = ttk.Treeview(
            right, columns=("qty",), show="tree headings", height=9
        )
        self.tree.heading("#0", text="物品")
        self.tree.heading("qty", text="数量")
        self.tree.column("#0", width=190)
        self.tree.column("qty", width=45, stretch=False)
        self.tree.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", self.show_item)

        self.details = tk.Label(
            right, text="选择家具查看物品", bg=BG, fg=INK,
            justify="left", anchor="nw", wraplength=245
        )
        self.details.pack(fill="both", expand=True, pady=14)
        for text, command in [
            ("添加物品", self.edit_item),
            ("编辑 / 移动物品", self.edit_selected),
            ("打开购买链接", self.open_link),
            ("删除物品", self.delete_item),
        ]:
            ttk.Button(right, text=text, command=command).pack(fill="x", pady=4)

        center = tk.Frame(body, bg=BG)
        center.pack(fill="both", expand=True)
        tk.Label(center, text="你的温馨小空间", bg=BG, fg=INK,
                 font=("Helvetica", 17, "bold")).pack(anchor="w", pady=10)
        tk.Label(center, text="点击查看 · 拖动布置", bg=BG,
                 fg=GREEN).pack(anchor="w", pady=(0, 10))
        self.canvas = tk.Canvas(center, bg="#efe6d7", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _: self.draw())
        self.canvas.bind("<Button-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.motion)
        self.canvas.bind("<ButtonRelease-1>", self.release)

        tk.Label(self, textvariable=self.status, bg=BG, fg=GREEN,
                 anchor="w", padx=20, pady=12).pack(fill="x")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()

    def load(self):
        if not self.path.exists():
            return sample()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("version") != 1 or not isinstance(data["furniture"], list):
                raise ValueError("文件格式不受支持")
            for f in data["furniture"]:
                if f["kind"] not in KINDS or not f["name"].strip():
                    raise ValueError("家具数据无效")
                if not (0 <= f["x"] <= 650 and 0 <= f["y"] <= 430):
                    raise ValueError("家具坐标无效")
                for i in f["items"]:
                    self.validate(i)
            return data["furniture"]
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
            self.protected = True
            self.after(100, lambda error=str(exc): messagebox.showerror(
                "数据文件已保护",
                f"无法读取数据：{error}\n\n原文件不会被覆盖。\n"
                f"请先备份并检查：{self.path}", parent=self
            ))
            return []

    @staticmethod
    def validate(item):
        if not item["name"].strip():
            raise ValueError("请输入物品名称")
        if type(item["quantity"]) is not int or item["quantity"] < 1:
            raise ValueError("数量必须是正整数")
        if item["price"]:
            try:
                value = Decimal(item["price"])
            except InvalidOperation:
                raise ValueError("价格必须是数字")
            if not value.is_finite() or value < 0:
                raise ValueError("价格必须是有限的非负数")
        if item["purchase_date"]:
            date.fromisoformat(item["purchase_date"])
        if item["url"] and not item["url"].startswith(("https://", "http://")):
            raise ValueError("购买链接必须以 https:// 或 http:// 开头")

    def save(self):
        temporary = None
        try:
            if self.protected:
                raise OSError("现有数据文件已保护，无法保存。请先备份并修复原文件。")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as stream:
                temporary = stream.name
                json.dump({"version": 1, "furniture": self.room},
                          stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self.status.set("已保存到本机 · ~/.roomly/room.json")
            return True
        except OSError as exc:
            self.status.set("修改尚未保存")
            messagebox.showerror("保存失败", str(exc), parent=self)
            return False
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def close(self):
        if self.save() or messagebox.askyesno(
            "尚未保存", "放弃未保存的修改并退出？", parent=self
        ):
            self.destroy()

    def refresh(self):
        self.listbox.delete(0, "end")
        for n, f in enumerate(self.room):
            self.listbox.insert("end", f["name"])
            if f is self.selected:
                self.listbox.selection_set(n)
        self.inventory()
        self.draw()

    def choose_list(self, _):
        if self.listbox.curselection():
            self.selected = self.room[self.listbox.curselection()[0]]
            self.query.set("")
            self.refresh()

    def inventory(self):
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        q = self.query.get().strip().casefold()
        self.heading.config(
            text="搜索结果" if q else self.selected["name"]
            if self.selected else "物品清单"
        )
        for f in self.room:
            for item in f["items"]:
                haystack = " ".join([
                    item["name"], item["category"], item["notes"], f["name"]
                ]).casefold()
                if (q and q in haystack) or (not q and f is self.selected):
                    key = str(len(self.rows))
                    self.rows[key] = (f, item)
                    name = item["name"] + (" · " + f["name"] if q else "")
                    self.tree.insert("", "end", iid=key, text=name,
                                     values=(item["quantity"],))
        self.details.config(
            text="选择物品查看详情。" if self.rows
            else "这里还没有物品。\n选择家具后点击“添加物品”。"
        )

    def current(self):
        keys = self.tree.selection()
        return self.rows.get(keys[0]) if keys else None

    def show_item(self, _=None):
        match = self.current()
        if not match:
            return
        f, i = match
        self.selected = f
        self.draw()
        self.details.config(text=(
            f'{i["name"]}\n\n分类：{i["category"]}\n数量：{i["quantity"]}\n'
            f'位置：{f["name"]}\n\n单价：{i["price"] or "未知"}\n'
            f'购买日期：{i["purchase_date"] or "未记录"}\n'
            f'商店：{i["store"] or "未记录"}\n\n'
            f'备注：{i["notes"] or "暂无"}'
        ))

    def draw(self):
        c = self.canvas
        c.delete("all")
        self.scale = min(max(c.winfo_width(), 1) / 820,
                         max(c.winfo_height(), 1) / 610)
        s = self.scale

        def rect(x, y, w, h, color):
            c.create_rectangle(x*s, y*s, (x+w)*s, (y+h)*s,
                               fill=color, outline="")

        for y in range(20, 610, 40):
            c.create_line(0, y*s, 820*s, y*s, fill="#e0d5c3")
        c.create_oval(220*s, 170*s, 620*s, 470*s,
                      fill="#dce5d3", outline="#ced9c4", width=4)
        rect(300, 0, 220, 18, "#a9cacb")
        for f in self.room:
            x, y = f["x"], f["y"]
            w, h = (140, 160) if f["kind"] == "Bed" else (150, 110)
            rect(x+5, y+7, w, h, "#cbbda8")
            kind = f["kind"]
            if kind == "Bed":
                rect(x, y, w, h, "#baa18a")
                rect(x+7, y+8, w-14, h-16, "#e6bcb1")
                rect(x+18, y+15, w-36, 35, "#fff7e7")
                rect(x+7, y+65, w-14, 12, "#f3d9cf")
            elif kind == "Desk":
                rect(x, y, w, h, "#cbb090")
                rect(x+40, y+15, 72, 43, "#5a7068")
                rect(x+45, y+20, 62, 32, "#bdd8cf")
                rect(x+48, y+70, 60, 16, "#f7f1e6")
            elif kind == "Wardrobe":
                rect(x, y, w, h, "#a7b79c")
                rect(x+7, y+7, 65, 96, "#cad4bd")
                rect(x+78, y+7, 65, 96, "#cad4bd")
                rect(x+60, y+45, 4, 18, "#6d8262")
                rect(x+86, y+45, 4, 18, "#6d8262")
            elif kind == "Bookshelf":
                rect(x, y, w, h, "#b1997c")
                for row in range(2):
                    rect(x+7, y+7+row*51, 136, 43, "#d9c9b0")
                    for j, color in enumerate(
                        ["#94b5a5", "#d9a392", "#adb0c7", "#ddbe83", "#a5bfaa"]
                    ):
                        rect(x+14+j*25, y+15+row*51, 18, 32, color)
            else:
                rect(x, y, w, h, "#bdb0cc")
                rect(x-3, y+5, w+6, 20, "#d8cce4")
                rect(x+50, y+48, 50, 22, "#faf2e5")
            if f is self.selected:
                c.create_rectangle(
                    (x-5)*s, (y-5)*s, (x+w+5)*s, (y+h+5)*s,
                    outline=GREEN, width=3, dash=(5, 3)
                )
            c.create_text((x+w/2)*s, (y+h+18)*s, text=f["name"],
                          fill=INK, font=("Helvetica", max(9, int(12*s))))

    def press(self, event):
        x, y = event.x/self.scale, event.y/self.scale
        for f in reversed(self.room):
            w, h = (140, 160) if f["kind"] == "Bed" else (150, 110)
            if f["x"] <= x <= f["x"]+w and f["y"] <= y <= f["y"]+h:
                self.selected = f
                self.drag = (x-f["x"], y-f["y"])
                self.query.set("")
                self.refresh()
                break

    def motion(self, event):
        if self.drag:
            self.selected["x"] = max(
                12, min(650, event.x/self.scale-self.drag[0])
            )
            self.selected["y"] = max(
                24, min(420, event.y/self.scale-self.drag[1])
            )
            self.draw()

    def release(self, _):
        if self.drag:
            self.drag = None
            self.save()

    def add_furniture(self):
        win = tk.Toplevel(self)
        win.title("添加家具")
        win.transient(self)
        win.grab_set()
        ttk.Label(win, text="家具名称").pack(padx=25, pady=10)
        name = ttk.Entry(win, width=28)
        name.pack(padx=25)
        kind = ttk.Combobox(win, values=KINDS, state="readonly")
        kind.current(0)
        kind.pack(padx=25, pady=12)

        def submit():
            if not name.get().strip():
                messagebox.showerror("提示", "请输入家具名称", parent=win)
                return
            self.selected = furniture(name.get().strip(), kind.get(), 280, 210)
            self.room.append(self.selected)
            self.save()
            self.refresh()
            win.destroy()

        ttk.Button(win, text="添加", command=submit).pack(pady=12)

    def rename(self):
        if self.selected:
            value = simpledialog.askstring(
                "重命名", "新名称：", initialvalue=self.selected["name"], parent=self
            )
            if value and value.strip():
                self.selected["name"] = value.strip()
                self.save()
                self.refresh()

    def delete_furniture(self):
        if self.selected and messagebox.askyesno(
            "确认删除", "删除这件家具及其中的全部物品？此操作不能撤销。", parent=self
        ):
            self.room.remove(self.selected)
            self.selected = None
            self.save()
            self.refresh()

    def edit_selected(self):
        match = self.current()
        if match:
            self.edit_item(*match)

    def edit_item(self, source=None, item=None):
        source = source or self.selected
        if source is None:
            messagebox.showinfo("选择位置", "请先选择一件家具。", parent=self)
            return
        win = tk.Toplevel(self)
        win.title("编辑物品" if item else "添加物品")
        win.transient(self)
        win.grab_set()
        entries = {}
        fields = [
            ("name", "物品名称 *"), ("category", "分类"),
            ("quantity", "数量 *"), ("price", "单价（可选）"),
            ("purchase_date", "日期 YYYY-MM-DD"),
            ("store", "商店"), ("url", "购买链接"), ("notes", "备注")
        ]
        for row, (key, label) in enumerate(fields):
            ttk.Label(win, text=label).grid(
                row=row, column=0, sticky="w", padx=16, pady=7
            )
            entry = ttk.Entry(win, width=36)
            entry.grid(row=row, column=1, padx=16, pady=7)
            entry.insert(0, str(item[key]) if item
                         else "1" if key == "quantity" else "")
            entries[key] = entry

        ttk.Label(win, text="存放位置").grid(row=8, column=0, padx=16)
        destination = ttk.Combobox(
            win, values=[f'{n+1}. {f["name"]}' for n, f in enumerate(self.room)],
            state="readonly", width=33
        )
        destination.current(self.room.index(source))
        destination.grid(row=8, column=1, padx=16, pady=8)

        def submit():
            try:
                values = {key: entry.get().strip()
                          for key, entry in entries.items()}
                values["quantity"] = int(values["quantity"])
                values["category"] = values["category"] or "其他"
                self.validate(values)
            except (ValueError, TypeError) as exc:
                messagebox.showerror("请检查输入", str(exc), parent=win)
                return
            if item is not None:
                source["items"].remove(item)
            target = self.room[destination.current()]
            target["items"].append(values)
            self.selected = target
            self.query.set("")
            self.save()
            self.refresh()
            win.destroy()

        ttk.Button(win, text="保存", command=submit).grid(
            row=9, column=1, sticky="e", padx=16, pady=16
        )

    def delete_item(self):
        match = self.current()
        if match and messagebox.askyesno(
            "确认删除", "删除这件物品？此操作不能撤销。", parent=self
        ):
            match[0]["items"].remove(match[1])
            self.save()
            self.inventory()

    def open_link(self):
        match = self.current()
        if match and match[1]["url"]:
            webbrowser.open(match[1]["url"])
        else:
            messagebox.showinfo("购买链接", "请先选择一个填写了购买链接的物品。", parent=self)

    def dashboard(self):
        count = unknown = 0
        total = Decimal(0)
        categories = {}
        for f in self.room:
            for item in f["items"]:
                count += item["quantity"]
                if item["price"]:
                    value = Decimal(item["price"]) * item["quantity"]
                    total += value
                    category = item["category"]
                    categories[category] = categories.get(category, Decimal(0)) + value
                else:
                    unknown += item["quantity"]
        text = (
            f"家具：{len(self.room)} 件\n物品总数量：{count}\n"
            f"已记录购买总值：{total:,.2f}\n价格未知：{unknown} 件\n\n分类价值\n"
        )
        text += "\n".join(f"{k}：{v:,.2f}" for k, v in sorted(categories.items()))
        text += "\n\n请为所有物品使用同一种货币。\n未知价格不计入已记录总值。"
        messagebox.showinfo("库存统计", text, parent=self)


if __name__ == "__main__":
    Roomly().mainloop()
