# mastering_gui.py (v4.1)
#
# This version fixes a SyntaxError caused by a missing parenthesis.
#

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
import threading
import os

try:
    from ttkthemes import ThemedTk
except ImportError:
    messagebox.showerror("Error", "The 'ttkthemes' library is not installed.\nPlease run: pip install ttkthemes")
    exit()

try:
    import audio_mastering_engine as engine
    EQ_PRESETS = engine.EQ_PRESETS
except ImportError:
    messagebox.showerror("Error", "The 'audio_mastering_engine.py' file was not found.")
    exit()

class MasteringApp(ThemedTk):
    def __init__(self):
        super().__init__(theme="equilux")

        self.SCALING_FACTOR = 2.0
        self.FONT_NORMAL = font.Font(family="Helvetica", size=int(11 * self.SCALING_FACTOR))
        self.FONT_BOLD = font.Font(family="Helvetica", size=int(11 * self.SCALING_FACTOR), weight="bold")
        
        self.title("Python Audio Mastering Tool")
        scaled_width = int(700 * self.SCALING_FACTOR)
        scaled_height = int(1000 * self.SCALING_FACTOR)
        self.geometry(f"{scaled_width}x{scaled_height}")
        self.configure(bg="#2b2b2b")

        self.style = ttk.Style(self)
        self.style.configure("TLabel", padding=6, font=self.FONT_NORMAL, background="#2b2b2b", foreground="white")
        self.style.configure("TButton", padding=8, font=self.FONT_BOLD)
        self.style.configure("TCheckbutton", padding=6, font=self.FONT_NORMAL, background="#2b2b2b", foreground="white")
        self.style.map("TCheckbutton", background=[('active', '#3c3f41')])
        self.style.configure("TFrame", background="#2b2b2b")
        self.style.configure("TLabelframe", padding=10, background="#2b2b2b", bordercolor="#555555")
        self.style.configure("TLabelframe.Label", font=self.FONT_BOLD, background="#2b2b2b", foreground="white")
        self.style.configure("Accent.TButton", background="#007acc", foreground="white")
        self.style.map("Accent.TButton", background=[('active', '#005f9e')])

        main_frame = ttk.Frame(self, padding=int(20 * self.SCALING_FACTOR))
        main_frame.pack(fill="both", expand=True)

        # --- File I/O Section ---
        file_frame = ttk.LabelFrame(main_frame, text="1. Select Files")
        file_frame.pack(fill="x", pady=(0, 15))
        self.input_file_path = tk.StringVar()
        self.output_file_path = tk.StringVar()
        ttk.Button(file_frame, text="Select Input File", command=self.select_input_file).grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        ttk.Label(file_frame, textvariable=self.input_file_path, wraplength=int(500*self.SCALING_FACTOR)).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Button(file_frame, text="Select Output File", command=self.select_output_file).grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        ttk.Label(file_frame, textvariable=self.output_file_path, wraplength=int(500*self.SCALING_FACTOR)).grid(row=1, column=1, sticky="w", padx=5)
        file_frame.columnconfigure(1, weight=1)

        # --- Presets Section ---
        preset_frame = ttk.LabelFrame(main_frame, text="2. Apply a Preset (Optional)")
        preset_frame.pack(fill="x", pady=15)
        self.preset_var = tk.StringVar()
        preset_names = ["None"] + list(EQ_PRESETS.keys())
        preset_menu = ttk.OptionMenu(preset_frame, self.preset_var, preset_names[0], *preset_names, command=self.apply_preset)
        preset_menu.pack(fill="x", expand=True, ipady=int(5*self.SCALING_FACTOR))

        # --- Manual Controls Section ---
        controls_frame = ttk.LabelFrame(main_frame, text="3. Adjust Parameters")
        controls_frame.pack(fill="x", pady=15)
        self.saturation = self.create_slider(controls_frame, "Saturation (%)", 0.0, 100.0, 0.0, 0)
        self.bass_boost = self.create_slider(controls_frame, "Bass (dB)", -6.0, 6.0, 0.0, 1)
        self.mid_cut = self.create_slider(controls_frame, "Mid Cut (dB)", 0.0, 6.0, 0.0, 2)
        self.presence_boost = self.create_slider(controls_frame, "Presence (dB)", -6.0, 6.0, 0.0, 3)
        self.treble_boost = self.create_slider(controls_frame, "Treble (dB)", -6.0, 6.0, 0.0, 4)
        self.width = self.create_slider(controls_frame, "Stereo Width", 0.0, 2.0, 1.0, 5)
        self.lufs = self.create_slider(controls_frame, "Target LUFS", -24.0, -6.0, -14.0, 6)

        # --- Multiband Compressor Section ---
        self.use_multiband = tk.BooleanVar()
        # --- THIS IS THE CORRECTED LINE ---
        ttk.Checkbutton(controls_frame, text="Use Multiband Compressor", variable=self.use_multiband, command=self.toggle_multiband_controls).grid(row=7, column=0, columnspan=3, sticky="w", pady=10)
        
        self.multiband_frame = ttk.LabelFrame(main_frame, text="4. Multiband Compressor Settings")
        
        self.low_band_threshold = self.create_slider(self.multiband_frame, "Low Thresh (dB)", -40.0, 0.0, -25.0, 0)
        self.low_band_ratio = self.create_slider(self.multiband_frame, "Low Ratio", 1.0, 12.0, 6.0, 1)
        self.mid_band_threshold = self.create_slider(self.multiband_frame, "Mid Thresh (dB)", -40.0, 0.0, -20.0, 2)
        self.mid_band_ratio = self.create_slider(self.multiband_frame, "Mid Ratio", 1.0, 12.0, 3.0, 3)
        self.high_band_threshold = self.create_slider(self.multiband_frame, "High Thresh (dB)", -40.0, 0.0, -15.0, 4)
        self.high_band_ratio = self.create_slider(self.multiband_frame, "High Ratio", 1.0, 12.0, 4.0, 5)

        # --- Process Section ---
        process_frame = ttk.Frame(main_frame)
        process_frame.pack(fill="x", pady=15)
        self.process_button = ttk.Button(process_frame, text="Start Processing", command=self.start_processing, style="Accent.TButton")
        self.process_button.pack(fill="x", expand=True, ipady=int(10*self.SCALING_FACTOR))

        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Ready.")
        status_label = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=5, background="#3c3f41", foreground="white")
        status_label.pack(side="bottom", fill="x")

    def toggle_multiband_controls(self):
        if self.use_multiband.get():
            self.multiband_frame.pack(fill="x", pady=15, before=self.process_button.master)
        else:
            self.multiband_frame.pack_forget()

    def create_slider(self, parent, label, from_, to, default, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        var = tk.DoubleVar(value=default)
        slider = ttk.Scale(parent, from_=from_, to=to, orient="horizontal", variable=var)
        slider.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        label_val = ttk.Label(parent, text=f"{default:.1f}", width=5)
        label_val.grid(row=row, column=2, sticky="w")
        slider.configure(command=lambda v, lbl=label_val: lbl.config(text=f"{float(v):.1f}"))
        parent.columnconfigure(1, weight=1)
        return var

    def select_input_file(self):
        path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.wav *.mp3 *.flac *.aiff")])
        if path:
            self.input_file_path.set(path)
            if not self.output_file_path.get():
                base, ext = os.path.splitext(path)
                self.output_file_path.set(f"{base}_mastered{ext}")

    def select_output_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV file", "*.wav"), ("MP3 file", "*.mp3")])
        if path:
            self.output_file_path.set(path)
            
    def apply_preset(self, preset_name):
        def update_labels():
             for child in self.winfo_children()[0].winfo_children()[2].winfo_children():
                if isinstance(child, ttk.Label) and child.grid_info()['column'] == 2:
                    row = child.grid_info()['row']
                    if row == 1: child.config(text=f"{self.bass_boost.get():.1f}")
                    if row == 2: child.config(text=f"{self.mid_cut.get():.1f}")
                    if row == 3: child.config(text=f"{self.presence_boost.get():.1f}")
                    if row == 4: child.config(text=f"{self.treble_boost.get():.1f}")
        if preset_name == "None":
            self.bass_boost.set(0.0); self.mid_cut.set(0.0)
            self.presence_boost.set(0.0); self.treble_boost.set(0.0)
        else:
            settings = EQ_PRESETS[preset_name]
            self.bass_boost.set(settings.get("bass_boost", 0.0))
            self.mid_cut.set(settings.get("mid_cut", 0.0))
            self.presence_boost.set(settings.get("presence_boost", 0.0))
            self.treble_boost.set(settings.get("treble_boost", 0.0))
        self.after(50, update_labels)

    def start_processing(self):
        settings = {
            "input_file": self.input_file_path.get(), "output_file": self.output_file_path.get(),
            "saturation": self.saturation.get(),
            "bass_boost": self.bass_boost.get(), "mid_cut": self.mid_cut.get(),
            "presence_boost": self.presence_boost.get(), "treble_boost": self.treble_boost.get(),
            "width": self.width.get(), "lufs": self.lufs.get(),
            "multiband": self.use_multiband.get(), "compress": False,
            "low_band_threshold": self.low_band_threshold.get(),
            "low_band_ratio": self.low_band_ratio.get(),
            "mid_band_threshold": self.mid_band_threshold.get(),
            "mid_band_ratio": self.mid_band_ratio.get(),
            "high_band_threshold": self.high_band_threshold.get(),
            "high_band_ratio": self.high_band_ratio.get(),
        }
        if not settings["input_file"] or not settings["output_file"]:
            messagebox.showerror("Error", "Please select both an input and an output file.")
            return
        self.process_button.config(state="disabled", text="Processing...")
        processing_thread = threading.Thread(target=engine.process_audio, args=(settings, self.update_status))
        processing_thread.daemon = True
        processing_thread.start()

    def update_status(self, message):
        self.status_var.set(message)
        if message == "Processing complete!":
            self.process_button.config(state="normal", text="Start Processing")
            messagebox.showinfo("Success", "Audio processing finished successfully!")
        elif "Error" in message:
             self.process_button.config(state="normal", text="Start Processing")
             messagebox.showerror("Error", message)

if __name__ == "__main__":
    app = MasteringApp()
    app.mainloop()
