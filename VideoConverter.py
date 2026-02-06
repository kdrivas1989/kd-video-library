#!/usr/bin/env python3
"""
Video Converter Desktop App
Converts MKV, AVI, MTS files to MP4 using FFmpeg
"""

import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

class VideoConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Converter")
        self.root.geometry("600x500")
        self.root.configure(bg="#1a1a2e")

        # Variables
        self.folder_path = tk.StringVar()
        self.files_to_convert = []
        self.is_converting = False

        self.setup_ui()

    def setup_ui(self):
        # Title
        title = tk.Label(
            self.root,
            text="Video Converter",
            font=("Helvetica", 24, "bold"),
            fg="#f97316",
            bg="#1a1a2e"
        )
        title.pack(pady=20)

        subtitle = tk.Label(
            self.root,
            text="Convert MKV, AVI, MTS → MP4",
            font=("Helvetica", 12),
            fg="#9ca3af",
            bg="#1a1a2e"
        )
        subtitle.pack()

        # Folder selection frame
        folder_frame = tk.Frame(self.root, bg="#1a1a2e")
        folder_frame.pack(pady=20, padx=20, fill="x")

        self.folder_entry = tk.Entry(
            folder_frame,
            textvariable=self.folder_path,
            font=("Helvetica", 11),
            bg="#374151",
            fg="#10b981",
            insertbackground="#10b981",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#4b5563",
            highlightcolor="#f97316"
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 10))

        browse_btn = tk.Button(
            folder_frame,
            text="Browse",
            command=self.browse_folder,
            font=("Helvetica", 11),
            bg="#f97316",
            fg="white",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2"
        )
        browse_btn.pack(side="right")

        # File list
        list_frame = tk.Frame(self.root, bg="#1a1a2e")
        list_frame.pack(pady=10, padx=20, fill="both", expand=True)

        list_label = tk.Label(
            list_frame,
            text="Files to convert:",
            font=("Helvetica", 11),
            fg="#9ca3af",
            bg="#1a1a2e",
            anchor="w"
        )
        list_label.pack(fill="x")

        # Listbox with scrollbar
        list_container = tk.Frame(list_frame, bg="#1a1a2e")
        list_container.pack(fill="both", expand=True, pady=5)

        scrollbar = tk.Scrollbar(list_container)
        scrollbar.pack(side="right", fill="y")

        self.file_listbox = tk.Listbox(
            list_container,
            font=("Helvetica", 10),
            bg="#374151",
            fg="#d1d5db",
            selectbackground="#f97316",
            relief="flat",
            highlightthickness=0,
            yscrollcommand=scrollbar.set
        )
        self.file_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        # Status label
        self.status_label = tk.Label(
            self.root,
            text="Select a folder to scan for videos",
            font=("Helvetica", 11),
            fg="#9ca3af",
            bg="#1a1a2e"
        )
        self.status_label.pack(pady=5)

        # Progress bar
        self.progress = ttk.Progress(self.root, length=400, mode='determinate')
        style = ttk.Style()
        style.configure("TProgressbar", background="#f97316", troughcolor="#374151")
        self.progress.pack(pady=10)

        # Convert button
        self.convert_btn = tk.Button(
            self.root,
            text="Convert All",
            command=self.start_conversion,
            font=("Helvetica", 14, "bold"),
            bg="#10b981",
            fg="white",
            relief="flat",
            padx=40,
            pady=12,
            cursor="hand2",
            state="disabled"
        )
        self.convert_btn.pack(pady=20)

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder with videos")
        if folder:
            self.folder_path.set(folder)
            self.scan_folder(folder)

    def scan_folder(self, folder):
        self.files_to_convert = []
        self.file_listbox.delete(0, tk.END)

        valid_extensions = {'.mkv', '.avi', '.mts', '.m2ts'}

        for file in os.listdir(folder):
            ext = os.path.splitext(file)[1].lower()
            if ext in valid_extensions:
                full_path = os.path.join(folder, file)
                output_path = os.path.splitext(full_path)[0] + '.mp4'

                # Check if already converted
                if os.path.exists(output_path):
                    self.file_listbox.insert(tk.END, f"✓ {file} (already converted)")
                else:
                    self.files_to_convert.append(full_path)
                    self.file_listbox.insert(tk.END, f"○ {file}")

        if self.files_to_convert:
            self.status_label.config(text=f"Found {len(self.files_to_convert)} file(s) to convert")
            self.convert_btn.config(state="normal")
        else:
            self.status_label.config(text="No files to convert (all done or none found)")
            self.convert_btn.config(state="disabled")

    def start_conversion(self):
        if self.is_converting:
            return

        self.is_converting = True
        self.convert_btn.config(state="disabled", text="Converting...")

        # Run conversion in separate thread
        thread = threading.Thread(target=self.convert_files)
        thread.daemon = True
        thread.start()

    def convert_files(self):
        total = len(self.files_to_convert)
        converted = 0
        failed = 0

        for i, file_path in enumerate(self.files_to_convert):
            filename = os.path.basename(file_path)
            output_path = os.path.splitext(file_path)[0] + '.mp4'

            self.root.after(0, lambda f=filename: self.status_label.config(
                text=f"Converting: {f}"
            ))

            try:
                # Run FFmpeg
                cmd = [
                    'ffmpeg', '-y', '-i', file_path,
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '128k',
                    '-movflags', '+faststart',
                    output_path
                ]

                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True
                )

                if process.returncode == 0:
                    converted += 1
                    self.root.after(0, lambda idx=i: self.update_listbox_item(idx, "✓"))
                else:
                    failed += 1
                    self.root.after(0, lambda idx=i: self.update_listbox_item(idx, "✗"))

            except Exception as e:
                failed += 1
                self.root.after(0, lambda idx=i: self.update_listbox_item(idx, "✗"))

            # Update progress
            progress_value = ((i + 1) / total) * 100
            self.root.after(0, lambda v=progress_value: self.progress.configure(value=v))

        # Done
        self.root.after(0, lambda: self.conversion_complete(converted, failed))

    def update_listbox_item(self, idx, symbol):
        current = self.file_listbox.get(idx)
        new_text = symbol + current[1:]
        self.file_listbox.delete(idx)
        self.file_listbox.insert(idx, new_text)

    def conversion_complete(self, converted, failed):
        self.is_converting = False
        self.convert_btn.config(state="normal", text="Convert All")
        self.status_label.config(text=f"Complete! Converted: {converted}, Failed: {failed}")
        self.progress.configure(value=100)

        messagebox.showinfo(
            "Conversion Complete",
            f"Converted: {converted} files\nFailed: {failed} files\n\nMP4 files saved in same folder."
        )

        # Rescan folder
        if self.folder_path.get():
            self.scan_folder(self.folder_path.get())


def check_ffmpeg():
    """Check if FFmpeg is installed"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True)
        return True
    except FileNotFoundError:
        return False


def main():
    if not check_ffmpeg():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "FFmpeg Not Found",
            "FFmpeg is not installed.\n\nInstall it with:\nbrew install ffmpeg"
        )
        sys.exit(1)

    root = tk.Tk()
    app = VideoConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
