"""Responsive artwork behind the project chooser; original assets stay unchanged."""
import tkinter as tk
from PIL import Image, ImageOps, ImageTk
from atmo_runtime import BG, PANEL, SURFACE, FOREST


class ProjectBackground(tk.Canvas):
    def __init__(self, parent, image_path, with_panel=True):
        super().__init__(parent, bg=BG, highlightthickness=0, bd=0)
        self._job = None
        self._photo = None
        self._size = None
        try:
            with Image.open(image_path) as image:
                self._source = image.convert('RGB')
        except (OSError, ValueError):
            self._source = None
        self._art = self.create_image(0, 0, anchor='nw')
        self.panel = tk.Frame(self, bg=PANEL, padx=28, pady=18,
                              highlightthickness=1, highlightbackground=FOREST)
        self._card = self.create_window(0, 0, window=self.panel, anchor='center') if with_panel else None
        self.bind('<Configure>', self._schedule)
        self.bind('<Destroy>', self._cleanup)

    def _schedule(self, event=None):
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(70, self._redraw)

    def _redraw(self):
        self._job = None
        width, height = max(1, self.winfo_width()), max(1, self.winfo_height())
        card_width = min(620, max(1, width - 48))
        if self._card is not None:
            self._layout_panel(width, height, card_width)
        if self._source is not None and self._size != (width, height):
            self._size = (width, height)
            fitted = ImageOps.fit(self._source, (width, height),
                                  method=Image.Resampling.LANCZOS)
            fitted = Image.blend(fitted, Image.new('RGB', fitted.size, BG), .28)
            self._photo = ImageTk.PhotoImage(fitted, master=self)
            self.itemconfigure(self._art, image=self._photo)

    def _layout_panel(self, width, height, card_width):
        self.itemconfigure(self._card, width=card_width)
        for widget in self.panel.winfo_children():
            if isinstance(widget, (tk.Label, tk.Button)):
                widget.configure(wraplength=max(1, card_width - 60))
        self.update_idletasks()
        card_height = self.panel.winfo_reqheight()
        # Keep the entire form reachable on short displays as well.
        self.configure(scrollregion=(0, 0, width, max(height, card_height + 32)))
        self.coords(self._card, width / 2, max(height / 2, card_height / 2 + 16))

    def _cleanup(self, event):
        if event.widget is self and self._job is not None:
            self.after_cancel(self._job)
            self._job = None
