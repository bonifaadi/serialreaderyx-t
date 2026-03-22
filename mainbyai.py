import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.ttk as ttk
import serial
import serial.tools.list_ports as seriallst
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from datetime import datetime
import ctypes
import time
import threading
from pathlib import Path

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
LOG_PATH = "log.txt"
TEMP_PATH = Path("output/")
MAX_LOG_LINES = 50
APP_ID = "pm.kompor.scndcmbstn.2"

ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


# ─────────────────────────────────────────────
# App State  (satu class, bukan global bertebaran)
# ─────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.started = False
        self.paused = False
        self.dx: list = []
        self.dys: list[list] = []
        self.pltcolor: list = []
        self.ser: serial.Serial | None = None
        self.full_path: Path | None = None
        self.tmp_name: str = ""
        self._file_lock = threading.Lock()

    def reset_data(self, n_sensors: int):
        self.dx = []
        self.dys = [[] for _ in range(n_sensors)]
        self.pltcolor = [
            [np.random.rand(), np.random.rand(), np.random.rand()]
            for _ in range(n_sensors)
        ]


state = AppState()


# ─────────────────────────────────────────────
# Tkinter root & matplotlib figure
# ─────────────────────────────────────────────
root = tk.Tk()
root.title("Serial Plotter")
root.iconbitmap(".icon.ico")
root.resizable(False, False)

fig, ax = plt.subplots()


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def log_update(label: str, perubahan: str):
    """Tulis ke widget log dan ke file log. Thread-safe via root.after."""
    sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text_log = f"{sekarang} - {label} -> {perubahan}\n"

    def _write_gui():
        loglist.config(state="normal")
        loglist.insert(tk.END, text_log)
        jumlah_baris = int(loglist.index("end-1c").split(".")[0])
        if jumlah_baris > MAX_LOG_LINES:
            loglist.delete("1.0", "2.0")
        loglist.see(tk.END)
        loglist.config(state="disabled")

    root.after(0, _write_gui)

    with open(LOG_PATH, "a") as f:
        f.write(text_log)


def tulis(teks: str, file_path: Path):
    """Tulis ke file CSV secara thread-safe."""
    with state._file_lock:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "a") as f:
            f.write(teks)


def update_plot_random():
    """Tombol 'Update Plot' — scatter acak untuk testing."""
    ax.clear()
    x = np.random.randint(0, 100, 100)
    y = np.random.randint(0, 100, 100)
    ax.scatter(x, y)
    pltcanvas.draw()


# ─────────────────────────────────────────────
# Serial
# ─────────────────────────────────────────────
def buka_serial(com: str, baud: int) -> bool:
    """Buka koneksi serial. Return True jika berhasil."""
    try:
        state.ser = serial.Serial(port=com, baudrate=baud, timeout=1)
        log_update("Serial Connection", f"Connected to {com} at {baud} baud")
        return True
    except Exception as e:
        log_update("Serial Connection Error", str(e))
        state.ser = None
        return False


def serial_thread():
    """Background thread: baca serial, parse, update plot."""
    log_update("Serial Thread", "Started")
    while True:
        if not state.started:
            time.sleep(0.1)
            continue

        if state.paused or state.ser is None:
            time.sleep(0.05)
            continue

        try:
            if state.ser.in_waiting == 0:
                time.sleep(0.01)
                continue

            raw = state.ser.readline()
            data = raw.decode("utf-8", errors="replace").rstrip()
        except serial.SerialException as e:
            log_update("Serial Read Error", str(e))
            time.sleep(0.5)
            continue

        # Log & simpan ke file (jadwalkan GUI update ke main thread)
        if state.full_path:
            root.after(0, lambda d=data: log_update("Data Received", d))
            tulis(data + "\n", state.full_path)

        # Parse CSV: format "waktu_ms,val1,val2,..."
        parsed = data.split(",")
        if not parsed[0].strip().lstrip("-").isdigit():
            continue  # Baris header / tidak valid

        try:
            state.dx.append(int(parsed[0]))
        except ValueError:
            continue

        for i, val_str in enumerate(parsed[1:], start=0):
            if i >= len(state.dys):
                state.dys.append([])
            try:
                state.dys[i].append(float(val_str))
            except ValueError:
                state.dys[i].append(0.0)

        # Update plot di main thread
        root.after(0, _redraw_plot)


def _redraw_plot():
    """Gambar ulang plot — HARUS dipanggil dari main thread."""
    ax.clear()
    n = min(int(var_dts.get()), len(state.dys))
    for i in range(n):
        # Pastikan warna tersedia (jika dys lebih panjang dari pltcolor)
        color = state.pltcolor[i] if i < len(state.pltcolor) else None
        if len(state.dx) == len(state.dys[i]):
            ax.plot(state.dx, state.dys[i], label=f"Sensor {i+1}", color=color)
    if ax.lines:
        ax.legend(loc="upper left")
    pltcanvas.draw()


# ─────────────────────────────────────────────
# Control callbacks
# ─────────────────────────────────────────────
def tombolstart():
    if state.started:
        # ── STOP ──
        state.started = False
        if state.paused:
            tombolpause()  # Reset pause state
        if state.ser and state.ser.is_open:
            state.ser.close()
        #ax.clear()
        pltcanvas.draw()
        log_update("Control", "Stopped")

        startbtn.config(text="Start")
        comlstcb.config(state="normal")
        baudcb.config(state="normal")
        pausebtn.config(state="disabled")
        spinbx.config(state="readonly")
        return

    # ── START ──
    log_update("Control", "Starting...")
    baud = int(var_baud.get())
    if not buka_serial(var_comport.get(), baud):
        log_update("Control", "Failed to start recording")
        return

    state.started = True
    state.tmp_name = f"data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    state.full_path = TEMP_PATH / state.tmp_name

    n_sensors = int(var_dts.get())
    state.reset_data(n_sensors)

    tulis(
        f"Pengambilan data dimulai pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        state.full_path,
    )
    tulis("waktu (ms), MAX31855_1, MAX31855_2, MAX6675_1, MAX6675_2, MAX6675_3\n", state.full_path)

    ax.clear()
    pltcanvas.draw()
    log_update("Control", "Recording started")

    startbtn.config(text="Stop")
    pausebtn.config(state="normal")
    spinbx.config(state="disabled")
    comlstcb.config(state="disabled")
    baudcb.config(state="disabled")


def tombolpause():
    state.paused = not state.paused
    status = "paused" if state.paused else "resumed"
    log_update("Control", f"Recording {status}")
    pausebtn.config(text="Resume" if state.paused else "Pause")


def simpan():
    if not state.full_path or not state.full_path.exists():
        log_update("Save", "No data file to save")
        return

    file_path = filedialog.asksaveasfilename(
        initialdir=str(TEMP_PATH),
        initialfile=state.tmp_name,
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        title="Save Data As",
    )
    if not file_path:
        log_update("Save", "Save cancelled")
        return

    try:
        dest = Path(file_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        state.full_path.rename(dest)
        state.full_path = dest
        log_update("Save", f"Data saved to {file_path}")
    except Exception as e:
        log_update("Save Error", str(e))


def refresh_comports():
    ports = [p.device for p in seriallst.comports()]
    if not ports:
        ports = ["No COM Ports Found"]
    comlstcb.config(values=ports)
    comlstcb.current(0)
    log_update("COM Port List", "Refreshed")


def on_close():
    plt.close("all")
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)


# ─────────────────────────────────────────────
# Widget definitions
# ─────────────────────────────────────────────

# LOG
frame_log = tk.Frame(root)
scrollbar = tk.Scrollbar(frame_log)
loglist = tk.Text(
    frame_log, height=10, state="disabled",
    yscrollcommand=scrollbar.set, wrap="word"
)
scrollbar.config(command=loglist.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
loglist.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# COM PORT
comlstlabel = ttk.Label(root, text="COM Port:")
var_comport = tk.StringVar()
var_comport.trace_add("write", lambda *_: log_update("COM Port", var_comport.get()))
com_ports = [p.device for p in seriallst.comports()] or ["No COM Ports Found"]
comlstcb = ttk.Combobox(root, values=com_ports, textvariable=var_comport)
comlstcb.current(0)
comlstrefresh = ttk.Button(root, text="Refresh", command=refresh_comports)

# BAUD RATE
baudlabel = ttk.Label(root, text="Baud Rate:")
var_baud = tk.StringVar()
var_baud.trace_add("write", lambda *_: log_update("Baud Rate", var_baud.get()))
baudcb = ttk.Combobox(root, values=[9600, 19200, 38400, 57600, 115200], textvariable=var_baud)
baudcb.current(0)

# SAVE
savebtn = ttk.Button(root, text="Save", command=simpan)

# CONTROL FRAME
ctlframe = tk.Frame(root)
startbtn = ttk.Button(ctlframe, text="Start", command=tombolstart)
startbtn.pack(side=tk.LEFT, padx=0)
pausebtn = ttk.Button(ctlframe, text="Pause", command=tombolpause, state="disabled")
pausebtn.pack(side=tk.LEFT, padx=5)
var_dts = tk.StringVar()
spinbx = ttk.Spinbox(ctlframe, from_=1, to=100, width=5, textvariable=var_dts, state="readonly")
spinbx.set(5)
spinbx.pack(side=tk.LEFT, padx=5)

# PLOT CANVAS
pltcanvas = FigureCanvasTkAgg(fig, master=root)
plttoolbar = NavigationToolbar2Tk(pltcanvas, root, pack_toolbar=False)
plttoolbar.update()
pltupdate = ttk.Button(root, text="Update Plot", command=update_plot_random)

# ─────────────────────────────────────────────
# Grid layout
# ─────────────────────────────────────────────
comlstlabel.grid(row=0, column=0, padx=10, pady=10, sticky="w")
comlstcb.grid(row=0, column=1, padx=10, pady=10, sticky="we")
comlstrefresh.grid(row=0, column=2, padx=10, pady=10, sticky="w")
savebtn.grid(row=0, column=3, padx=10, pady=10, sticky="w")
baudlabel.grid(row=1, column=0, padx=10, pady=10, sticky="w")
baudcb.grid(row=1, column=1, padx=10, pady=10, sticky="we")
ctlframe.grid(row=1, column=2, columnspan=4, padx=10, pady=10, sticky="we")
pltcanvas.get_tk_widget().grid(row=2, column=0, columnspan=6, padx=10, pady=10)
plttoolbar.grid(row=3, column=0, columnspan=6, padx=10, pady=0, sticky="we")
pltupdate.grid(row=4, column=0, columnspan=6, padx=10, pady=10)
frame_log.grid(row=5, column=0, columnspan=6, padx=10, pady=10, sticky="we")

# ─────────────────────────────────────────────
# Start background thread & main loop
# ─────────────────────────────────────────────
thread = threading.Thread(target=serial_thread, daemon=True)
thread.start()

root.mainloop()
#Akhir