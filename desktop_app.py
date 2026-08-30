#!/usr/bin/env python3

import os
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from core.chat_engine import ChatEngine


class DesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI Security Workspace")
        self.geometry("980x700")
        self.minsize(760, 520)

        self.engine = ChatEngine(provider="openai")
        self._build_ui()
        self._append("assistant", "Ready. Talk to me in plain language. Choose ChatGPT or Ollama above.")

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(5, weight=1)

        ttk.Label(top, text="Provider").grid(row=0, column=0, padx=(0, 6))
        self.provider_var = tk.StringVar(value="openai")
        self.provider_box = ttk.Combobox(
            top,
            textvariable=self.provider_var,
            values=["openai", "ollama"],
            state="readonly",
            width=10,
        )
        self.provider_box.grid(row=0, column=1, padx=(0, 12))
        self.provider_box.bind("<<ComboboxSelected>>", self._provider_changed)

        ttk.Label(top, text="Model").grid(row=0, column=2, padx=(0, 6))
        self.model_var = tk.StringVar(value="gpt-5.6-sol")
        self.model_entry = ttk.Entry(top, textvariable=self.model_var, width=24)
        self.model_entry.grid(row=0, column=3, padx=(0, 12))

        self.settings_btn = ttk.Button(top, text="Settings", command=self._toggle_settings)
        self.settings_btn.grid(row=0, column=4, padx=(0, 8))

        self.clear_btn = ttk.Button(top, text="Clear Chat", command=self._clear_chat)
        self.clear_btn.grid(row=0, column=6)

        self.settings = ttk.Frame(self, padding=(10, 0, 10, 10))
        self.settings.columnconfigure(1, weight=1)
        ttk.Label(self.settings, text="OpenAI API key").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.api_key_var = tk.StringVar(value=os.getenv("OPENAI_API_KEY", ""))
        self.api_key_entry = ttk.Entry(self.settings, textvariable=self.api_key_var, show="*" )
        self.api_key_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(self.settings, text="Apply", command=self._apply_settings).grid(row=0, column=2)
        self.settings_visible = False

        self.chat = ScrolledText(self, wrap=tk.WORD, state="disabled", font=("Segoe UI", 11))
        self.chat.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.chat.tag_configure("user", font=("Segoe UI", 11, "bold"))
        self.chat.tag_configure("assistant", font=("Segoe UI", 11))
        self.chat.tag_configure("error", font=("Segoe UI", 11, "italic"))

        bottom = ttk.Frame(self, padding=(10, 0, 10, 10))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        self.input_box = tk.Text(bottom, height=4, wrap=tk.WORD, font=("Segoe UI", 11))
        self.input_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.input_box.bind("<Control-Return>", self._send_shortcut)

        self.send_btn = ttk.Button(bottom, text="Send", command=self._send)
        self.send_btn.grid(row=0, column=1, sticky="ns")

        hint = ttk.Label(bottom, text="Ctrl+Enter to send")
        hint.grid(row=1, column=0, sticky="w", pady=(4, 0))

    def _toggle_settings(self):
        if self.settings_visible:
            self.settings.grid_forget()
        else:
            self.settings.grid(row=3, column=0, sticky="ew")
        self.settings_visible = not self.settings_visible

    def _provider_changed(self, _event=None):
        provider = self.provider_var.get()
        if provider == "openai" and self.model_var.get().startswith("dolphin"):
            self.model_var.set("gpt-5.6-sol")
        elif provider == "ollama" and self.model_var.get().startswith("gpt-"):
            self.model_var.set("dolphin-llama3")
        self._apply_settings(show_message=False)

    def _apply_settings(self, show_message=True):
        self.engine.configure(
            provider=self.provider_var.get(),
            model=self.model_var.get(),
            api_key=self.api_key_var.get().strip() or None,
        )
        if show_message:
            self._append("assistant", f"Using {self.engine.provider} / {self.engine.model}.")

    def _clear_chat(self):
        self.engine.clear()
        self.chat.configure(state="normal")
        self.chat.delete("1.0", tk.END)
        self.chat.configure(state="disabled")
        self._append("assistant", "Conversation cleared.")

    def _send_shortcut(self, _event=None):
        self._send()
        return "break"

    def _send(self):
        text = self.input_box.get("1.0", tk.END).strip()
        if not text:
            return

        self._apply_settings(show_message=False)
        self.input_box.delete("1.0", tk.END)
        self._append("user", text)
        self.send_btn.configure(state="disabled")
        self.provider_box.configure(state="disabled")
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()

    def _worker(self, text):
        try:
            answer = self.engine.ask(text)
            self.after(0, lambda: self._append("assistant", answer))
        except Exception as exc:
            self.after(0, lambda: self._append("error", f"Error: {exc}"))
        finally:
            self.after(0, self._unlock)

    def _unlock(self):
        self.send_btn.configure(state="normal")
        self.provider_box.configure(state="readonly")
        self.input_box.focus_set()

    def _append(self, role, text):
        label = "You" if role == "user" else "AI"
        self.chat.configure(state="normal")
        self.chat.insert(tk.END, f"{label}: ", role)
        self.chat.insert(tk.END, f"{text}\n\n", role)
        self.chat.configure(state="disabled")
        self.chat.see(tk.END)


if __name__ == "__main__":
    app = DesktopApp()
    app.mainloop()
