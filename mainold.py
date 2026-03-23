import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.ttk as ttk
import serial, numpy as np
import serial.tools.list_ports as seriallst
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from datetime import datetime
import ctypes, time, threading
from pathlib import Path


global started, paused, dx, dys, pltcolor, LOG_path, TEMP_path, ser, thread, tmp_name, full_path
LOG_path = "log.txt"
TEMP_path = "output/"
tmp_name = ""
full_path = ""
started = False
paused = False
dx = []
dys = []
pltcolor = []
myappid = 'pm.kompor.scndcmbstn.2' 
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

root = tk.Tk()
root.title("Serial Plotter")
root.iconbitmap(".icon.ico")
root.resizable(False, False)
fig, ax = plt.subplots()

def update_plot():
    ax.clear()
    x = np.random.randint(0, 100, 100)
    y = np.random.randint(0, 100, 100)
    ax.scatter(x, y)
    pltcanvas.draw()

def log_update(label, perubahan, event=None, *args):
    MAX_BARIS = 50
    sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    loglist.config(state='normal')
    text_log = f"{sekarang} - {label} -> {perubahan}\n"
    loglist.insert(tk.END, text_log)

    with open(LOG_path, "a") as log_file:
        log_file.write(text_log)

    jumlah_baris = int(loglist.index('end-1c').split('.')[0])

    if jumlah_baris > MAX_BARIS:
        loglist.delete(1.0, 2.0)

    loglist.see(tk.END)
    loglist.config(state='disabled')

def rekam(COM,PORT):
    global ser, thread
    try:
        ser = serial.Serial(port=COM, baudrate=PORT, timeout=1)
        log_update("Serial Connection", f"Connected to {COM} at {PORT} baud")
        return 0
    except Exception as e:
        log_update("Serial Connection Error", str(e))
        ser = None
        return 1
def serial_thread():
    global ser, paused, started, dx, dys, pltcolor, full_path
    log_update("Serial Thread", "Started")
    while True:
        while started:
            if ser and ser.in_waiting > 0 and not paused:
                
                data = ser.readline().decode('utf-8').rstrip()
                # Gunakan root.after untuk update GUI dari thread lain (Thread-Safe)
                root.after(0, lambda d=data: (log_update("Data Received", d), tulis(d + "\n", full_path)))
                
                parsed = data.split(",")
                try:
                    int(parsed[0])
                except:
                    continue
                dx.append(int(parsed[0]))
                for i in range(1, len(parsed)):
                    if len(dys) < i:
                        dys.append([])
                    try:
                        dys[i-1].append(float(parsed[i]))
                    except:
                        dys[i-1].append(0.0)
                try:
                    ax.clear()
                    for i in range(min(int(var_dts.get()), len(dys),len(parsed)-1)):
                        ax.plot(dx, dys[i], label=f"Sensor {i+1}",color=pltcolor[i])
                      # Hapus legend lama jika ada
                    ax.legend(loc="upper left") if not ax.get_legend() else None
                    
                except Exception as e:
                    log_update("Plotting Error", str(e))
                    log_update("Plotting Error", f"dx length: {len(dx)}, dys lengths: {[len(d) for d in dys]}")
                    
                pltcanvas.draw()
        time.sleep(0.1)  # Biar CPU tidak kerja terlalu keras
    log_update("Serial Thread", "Stopped")

def tombolstart():
    global started, ser, paused, dx, dys, pltcolor, full_path
    if started == True:
        log_update("Control", "Stopped")
        started = False
        startbtn.config(text="Start", command=tombolstart)
        comlstcb.config(state='normal')
        baudcb.config(state='normal')
        pausebtn.config(state='disabled')
        spinbx.config(state='readonly')
        ser.close()
        ax.get_legend().remove() if ax.get_legend() else None
        
        if paused: tombolpause()  # Pastikan tidak dalam keadaan paused saat stop
        return
    log_update("Control", "Starting...")
    if rekam(var_comport.get(), var_baud.get()) == 1:
        log_update("Control", "Failed to start recording")
        return
    started = True
    tmp_name = f"data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    full_path = Path(f"{TEMP_path}{tmp_name}")
    tulis(f"Pengambilan data dimulai pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", full_path)
    tulis("waktu (ms), MAX31855_1, MAX31855_2, MAX6675_1, MAX6675_2, MAX6675_3\n", full_path)
    dx = []
    dys = [[] for _ in range(int(var_dts.get()))]
    pltcolor = [[np.random.rand(), np.random.rand(), np.random.rand()] for _ in range(int(var_dts.get()))]
    ax.clear()
    pausebtn.config(state='normal')
    spinbx.config(state='disabled')
    comlstcb.config(state='disabled')
    baudcb.config(state='disabled')
    log_update("Control", "Recording started")
    startbtn.config(text="Stop", command=tombolstart)

def tombolpause():
    global paused
    paused = not paused
    status = "paused" if paused else "resumed"
    log_update("Control", f"Recording {status}")
    pausebtn.config(text="Resume" if paused else "Pause")

def tulis(teks, file_path):
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "a") as f:
        f.write(teks)

root.protocol("WM_DELETE_WINDOW", lambda: (print("Window closed"), plt.close('all'), root.destroy(), exit()))


# widget settings

#LOG
frame_log = tk.Frame(root)
scrollbar = tk.Scrollbar(frame_log)
loglist = tk.Text(frame_log, height=10, state='disabled', yscrollcommand=scrollbar.set, wrap="word")
scrollbar.config(command=loglist.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
loglist.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

#COMS
comlstlabel = ttk.Label(root, text="COM Port:")
var_comport = tk.StringVar()
id_comport = var_comport.trace_add("write", lambda *a: log_update("COM Port", var_comport.get(), *a))
com = seriallst.comports()
comlst = [port.device for port in com]
if len(comlst)==0:comlst.insert(0, "No COM Ports Found")
comlstcb = ttk.Combobox(root, values=comlst, textvariable=var_comport)
comlstcb.current(0)
comlstrefresh = ttk.Button(root, text="Refresh", command=lambda: (comlstcb.config(values=[port.device for port in seriallst.comports()]), comlstcb.current(0), log_update("COM Port List", "Refreshed")))

#BAUD
baudlabel = ttk.Label(root, text="Baud Rate:")
var_baud = tk.StringVar()
id_baud = var_baud.trace_add("write", lambda *a: log_update("Baud Rate", var_baud.get(), *a))
baudcb = ttk.Combobox(root, values=[9600, 19200, 38400, 57600, 115200], textvariable=var_baud)
baudcb.current(0)

#SAVE PATH
def simpan():
    global full_path
    if not full_path:
        log_update("Save", "No data to save")
        return
    file_path = filedialog.asksaveasfilename(initialdir=TEMP_path, initialfile=tmp_name, defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")], title="Save Data As")
    if file_path:
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            Path(full_path).rename(file_path)
            log_update("Save", f"Data saved to {file_path}")
            full_path = Path(file_path)  # Update full_path ke lokasi baru
        except Exception as e:
            log_update("Save Error", str(e))
    else:
        log_update("Save", "Save cancelled")
savebtn = ttk.Button(root, text="save", command=simpan)

#CONTROL
ctlframe = tk.Frame(root)
startbtn = ttk.Button(ctlframe, text="Start", command=tombolstart)
startbtn.pack(side=tk.LEFT, padx=0)
pausebtn = ttk.Button(ctlframe, text="Pause", command=tombolpause, state='disabled')
pausebtn.pack(side=tk.LEFT, padx=5)
var_dts = tk.StringVar()
spinbx = ttk.Spinbox(ctlframe, from_=1, to=100, width=5, textvariable=var_dts, state='readonly')
spinbx.set(5)  # Set default value
spinbx.pack(side=tk.LEFT, padx=5)

#CANVAS
pltcanvas = FigureCanvasTkAgg(fig, master=root)
plttoolbar = NavigationToolbar2Tk(pltcanvas, root, pack_toolbar=False)
plttoolbar.update()

pltupdate = ttk.Button(root, text="Update Plot", command=update_plot)

# widget placements

comlstlabel.grid(row=0, column=0, padx=10, pady=10, sticky="w")
comlstcb.grid(row=0, column=1, padx=10, pady=10, sticky="w e")
comlstrefresh.grid(row=0, column=2, padx=10, pady=10, sticky="w")
savebtn.grid(row=0, column=3, padx=10, pady=10, sticky="w")
baudlabel.grid(row=1, column=0, padx=10, pady=10, sticky="w")
baudcb.grid(row=1, column=1, padx=10, pady=10, sticky="w e")
ctlframe.grid(row=1, column=2, columnspan=4, padx=10, pady=10, sticky="w e")
pltcanvas.get_tk_widget().grid(row=2, column=0, columnspan=6, padx=10, pady=10)
plttoolbar.grid(row=3, column=0, columnspan=6, padx=10, pady=0, sticky="w e")
pltupdate.grid(row=4, column=0, columnspan=6, padx=10, pady=10)
frame_log.grid(row=5, column=0, columnspan=6, padx=10, pady=10, sticky="w e")



#thread
thread = threading.Thread(target=serial_thread, daemon=True)
thread.start()
root.mainloop()
#akhir