"""
Módulo de Visor de Logs con estética de consola/terminal en Tkinter.
Permite visualizar la actividad del bot en tiempo real y controlar su estado desde Windows.
Referencia de diseño: docs/ARQUITECTURA.md
"""
import logging
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from typing import Callable, Optional

logger = logging.getLogger("log_viewer")


class LogViewer:
    """Ventana de consola gráfica de logs para Windows."""

    def __init__(
        self,
        root: Optional[tk.Tk] = None,
        on_turn_on: Optional[Callable[[], None]] = None,
        on_turn_off: Optional[Callable[[], None]] = None,
        is_paused: bool = True,
        log_file_path: Optional[str] = None,
    ):
        self.root = root or tk.Tk()
        self.on_turn_on = on_turn_on
        self.on_turn_off = on_turn_off
        self.is_paused = is_paused
        if log_file_path is not None:
            self.log_file_path = Path(log_file_path).resolve()
        else:
            project_root = Path(__file__).resolve().parent.parent.parent
            default_path = project_root / "logs" / "bot.log"
            self.log_file_path = default_path if default_path.exists() else project_root / "bot.log"

        self.auto_scroll = True
        self._last_file_pos = 0
        self._poll_job = None

        self._setup_window()
        self._create_widgets()
        self._load_existing_logs()
        self._start_polling()

    def _setup_window(self):
        self.root.title("Bot P2P Binance ARS — Consola de Operaciones")
        self.root.geometry("960x600")
        self.root.minsize(700, 400)
        self.root.configure(bg="#121214")

        # Interceptar el botón 'X' de la ventana para OCULTAR a la bandeja en lugar de destruir
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # Centrar la ventana en la pantalla
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = (sw - 960) // 2
            y = (sh - 600) // 2
            self.root.geometry(f"960x600+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _create_widgets(self):
        # ── Barra Superior (Header & Status) ──────────────────────────
        header = tk.Frame(self.root, bg="#18181b", height=50, padx=12, pady=8)
        header.pack(fill=tk.X, side=tk.TOP)

        title_lbl = tk.Label(
            header,
            text="🤖 BOT P2P BINANCE ARS",
            font=("Segoe UI", 11, "bold"),
            fg="#f3ba2f",
            bg="#18181b",
        )
        title_lbl.pack(side=tk.LEFT, padx=(0, 15))

        # Badge de Estado
        self.status_badge = tk.Label(
            header,
            text="🟡 STANDBY (En espera de Telegram)",
            font=("Segoe UI", 9, "bold"),
            fg="#f59e0b",
            bg="#27272a",
            padx=10,
            pady=4,
            relief=tk.FLAT,
        )
        self.status_badge.pack(side=tk.LEFT, padx=5)

        # Botón Ocultar (X visual)
        btn_hide = tk.Button(
            header,
            text="✖ Ocultar a Bandeja",
            font=("Segoe UI", 9),
            fg="#e4e4e7",
            bg="#3f3f46",
            activebackground="#52525b",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self.hide,
        )
        btn_hide.pack(side=tk.RIGHT, padx=(6, 0))

        # Botón Abrir Archivo bot.log
        btn_open_file = tk.Button(
            header,
            text="📄 Abrir bot.log",
            font=("Segoe UI", 9),
            fg="#e4e4e7",
            bg="#27272a",
            activebackground="#3f3f46",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._open_log_in_notepad,
        )
        btn_open_file.pack(side=tk.RIGHT, padx=4)

        # Botón Limpiar Pantalla
        btn_clear = tk.Button(
            header,
            text="🗑️ Limpiar",
            font=("Segoe UI", 9),
            fg="#a1a1aa",
            bg="#27272a",
            activebackground="#3f3f46",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._clear_text,
        )
        btn_clear.pack(side=tk.RIGHT, padx=4)

        # Toggle Auto-scroll
        self.btn_scroll = tk.Button(
            header,
            text="⬇️ Auto-scroll: ON",
            font=("Segoe UI", 9),
            fg="#22c55e",
            bg="#27272a",
            activebackground="#3f3f46",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._toggle_autoscroll,
        )
        self.btn_scroll.pack(side=tk.RIGHT, padx=4)

        # Botón Encender / Apagar
        self.btn_power = tk.Button(
            header,
            text="🟢 Encender Bot",
            font=("Segoe UI", 9, "bold"),
            fg="#ffffff",
            bg="#15803d",
            activebackground="#16a34a",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=3,
            cursor="hand2",
            command=self._toggle_power,
        )
        self.btn_power.pack(side=tk.RIGHT, padx=8)

        # ── Área de Texto de la Consola ───────────────────────────────
        console_frame = tk.Frame(self.root, bg="#0d0d10", padx=6, pady=6)
        console_frame.pack(fill=tk.BOTH, expand=True)

        # Barra de desplazamiento vertical
        scrollbar = tk.Scrollbar(console_frame, bg="#27272a", troughcolor="#121214")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Caja de texto estilo terminal
        mono_font = tkfont.Font(family="Consolas", size=10)
        self.text_area = tk.Text(
            console_frame,
            wrap=tk.CHAR,
            bg="#0c0c0e",
            fg="#e4e4e7",
            insertbackground="#ffffff",
            font=mono_font,
            yscrollcommand=scrollbar.set,
            relief=tk.FLAT,
            padx=10,
            pady=10,
        )
        self.text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text_area.yview)

        # Configurar etiquetas de resaltado de colores
        self.text_area.tag_config("TIMESTAMP", foreground="#71717a")
        self.text_area.tag_config("INFO", foreground="#93c5fd")
        self.text_area.tag_config("WARNING", foreground="#fde047")
        self.text_area.tag_config("ERROR", foreground="#f87171", font=("Consolas", 10, "bold"))
        self.text_area.tag_config("CRITICAL", foreground="#ef4444", background="#450a0a")
        self.text_area.tag_config("SUCCESS", foreground="#4ade80")
        self.text_area.tag_config("HIGHLIGHT", foreground="#f3ba2f")
        self.text_area.config(state=tk.DISABLED)

        # ── Barra de Estado Inferior ──────────────────────────────────
        footer = tk.Frame(self.root, bg="#18181b", height=24, padx=12, pady=4)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        self.footer_lbl = tk.Label(
            footer,
            text="💡 Consejo: Puedes cerrar esta ventana con la [X] y el bot continuará corriendo en la bandeja (^)",
            font=("Segoe UI", 8),
            fg="#a1a1aa",
            bg="#18181b",
        )
        self.footer_lbl.pack(side=tk.LEFT)

        self.update_status(self.is_paused)

    def _toggle_autoscroll(self):
        self.auto_scroll = not self.auto_scroll
        if self.auto_scroll:
            self.btn_scroll.config(text="⬇️ Auto-scroll: ON", fg="#22c55e")
            self.text_area.see(tk.END)
        else:
            self.btn_scroll.config(text="⬇️ Auto-scroll: OFF", fg="#a1a1aa")

    def _clear_text(self):
        self.text_area.config(state=tk.NORMAL)
        try:
            self.text_area.delete("1.0", tk.END)
        finally:
            self.text_area.config(state=tk.DISABLED)

    def _open_log_in_notepad(self):
        if self.log_file_path.exists() and sys.platform == "win32":
            try:
                os.startfile(str(self.log_file_path))
            except Exception as e:
                logger.error("Error abriendo bot.log: %s", e)

    def _toggle_power(self):
        if self.is_paused:
            if self.on_turn_on:
                self.on_turn_on()
        else:
            if self.on_turn_off:
                self.on_turn_off()

    def update_status(self, is_paused: bool):
        """Actualiza el indicador visual de estado en el header."""
        self.is_paused = is_paused
        if is_paused:
            self.status_badge.config(
                text="🟡 STANDBY (En espera de Telegram)",
                fg="#f59e0b",
                bg="#27272a",
            )
            self.btn_power.config(
                text="🟢 Encender Bot",
                bg="#15803d",
                activebackground="#16a34a",
            )
        else:
            self.status_badge.config(
                text="🟢 ACTIVO (Operando en Binance)",
                fg="#22c55e",
                bg="#14532d",
            )
            self.btn_power.config(
                text="🔴 Apagar Bot",
                bg="#b91c1c",
                activebackground="#dc2626",
            )

    def _insert_log_line(self, line: str, update_scroll: bool = True):
        """Inserta una línea con formateo de colores sintácticos."""
        tags = []
        if "[INFO]" in line:
            tags.append("INFO")
        elif "[WARNING]" in line:
            tags.append("WARNING")
        elif "[ERROR]" in line:
            tags.append("ERROR")
        elif "[CRITICAL]" in line:
            tags.append("CRITICAL")

        if any(w in line for w in ("✅", "🟢", "Completada", "EXITOSO")):
            tags.append("SUCCESS")
        if any(w in line for w in ("Bot P2P Binance ARS", "STANDBY", "ESPERA")):
            tags.append("HIGHLIGHT")

        was_disabled = str(self.text_area.cget("state")) == tk.DISABLED
        if was_disabled:
            self.text_area.config(state=tk.NORMAL)
        try:
            self.text_area.insert(tk.END, line, tuple(tags))

            # Limitar historial en pantalla a 10,000 líneas para mantener agilidad
            line_count = int(self.text_area.index("end-1c").split(".")[0])
            if line_count > 10000:
                self.text_area.delete("1.0", f"{line_count - 8000}.0")
        finally:
            if was_disabled:
                self.text_area.config(state=tk.DISABLED)

        if update_scroll and self.auto_scroll:
            self.text_area.see(tk.END)

    def _load_existing_logs(self):
        """Carga las últimas líneas existentes del archivo bot.log al iniciar."""
        if not self.log_file_path.exists():
            self.text_area.config(state=tk.DISABLED)
            return
        try:
            file_size = os.path.getsize(self.log_file_path)
            with open(self.log_file_path, "r", encoding="utf-8", errors="replace") as f:
                if file_size > 65536:
                    f.seek(file_size - 65536)
                    # Descartar primera línea posiblemente parcial
                    f.readline()
                lines = f.readlines()
                recent = lines[-200:] if len(lines) > 200 else lines
                self.text_area.config(state=tk.NORMAL)
                try:
                    for line in recent:
                        self._insert_log_line(line, update_scroll=False)
                finally:
                    self.text_area.config(state=tk.DISABLED)
                self._last_file_pos = file_size
                if self.auto_scroll:
                    self.text_area.see(tk.END)
        except Exception as e:
            logger.debug("Error leyendo bot.log inicial: %s", e)
            self.text_area.config(state=tk.DISABLED)

    def _start_polling(self):
        """Monitorea el archivo bot.log periódicamente para incorporar nuevas líneas."""
        if self._poll_job is not None:
            return

        def poll():
            try:
                if self.log_file_path.exists():
                    current_size = os.path.getsize(self.log_file_path)
                    if current_size < self._last_file_pos:
                        # El archivo fue rotado o truncado
                        self._last_file_pos = 0

                    if current_size > self._last_file_pos:
                        has_new = False
                        with open(self.log_file_path, "r", encoding="utf-8", errors="replace") as f:
                            f.seek(self._last_file_pos)
                            self.text_area.config(state=tk.NORMAL)
                            try:
                                for line in f:
                                    self._insert_log_line(line, update_scroll=False)
                                    has_new = True
                            finally:
                                self.text_area.config(state=tk.DISABLED)
                            self._last_file_pos = f.tell()
                        if has_new and self.auto_scroll:
                            self.text_area.see(tk.END)
            except Exception as e:
                logger.debug("Error en poll de logs: %s", e)
            finally:
                self._poll_job = self.root.after(400, poll)

        self._poll_job = self.root.after(400, poll)

    def show(self):
        """Muestra la ventana y la trae al frente."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if self._poll_job is None:
            self._start_polling()
        if self.auto_scroll:
            self.text_area.see(tk.END)

    def hide(self):
        """Oculta la ventana sin destruir el proceso."""
        if self._poll_job is not None:
            try:
                self.root.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        self.root.withdraw()
