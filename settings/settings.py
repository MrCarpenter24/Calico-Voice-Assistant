#!/usr/bin/env python3

"""
Simple setttings application for Calico.
Uses https://zippopotam.us/ to verify zip codes.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import requests
import os
import webbrowser

class SettingsEditor(tk.Tk):
    """
    A GUI application for editing a JSON configuration file.
    """
    def __init__(self):
        super().__init__()
        self.title("Calico Voice Assistant")
        self.geometry("450x425")
        self.resizable(False, False)

        # --- Define the absolute path for the config file ---
        # Get the directory where this script (settings.py) is located.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Join that directory with the config file name.
        self.config_file = os.path.join(script_dir, 'config.json')

        # --- Style Configuration ---
        BG_COLOR = "#80CF59"
        TEXT_COLOR = "white"
        BOLD_FONT = ("Helvetica", 12, "bold")
        NORMAL_FONT = ("Helvetica", 10)
        HEADER_FONT = ("Helvetica", 18, "bold")
        LINK_FONT = ("Helvetica", 10, "underline")

        # Create and configure the style
        style = ttk.Style(self)
        self.configure(background=BG_COLOR) # Set background for main window

        # Configure style for all frames and labels
        style.configure('TFrame', background=BG_COLOR)
        style.configure('TLabel', background=BG_COLOR, foreground=TEXT_COLOR, font=BOLD_FONT)

        # Configure style for the button
        style.configure('TButton', font=BOLD_FONT, foreground=TEXT_COLOR)
        style.map('TButton',
                  background=[('!active', '#6abf40'), ('active', '#58a135')], # Lighter for normal, darker for active/hover
                  foreground=[('!disabled', TEXT_COLOR)])

        # Configure Combobox style (entry part)
        style.configure('TCombobox', fieldbackground='white', background='#6abf40', font=("Helvetica", 10))
        # Note: The dropdown list style is often controlled by the OS and may not change.
            # Style for the new "About" frame
        style.configure('About.TLabelframe', background=BG_COLOR, bordercolor=TEXT_COLOR)
        style.configure('About.TLabelframe.Label', background=BG_COLOR, foreground=TEXT_COLOR, font=BOLD_FONT)
        # Style for the new hyperlink labels
        style.configure('Link.TLabel', background=BG_COLOR, foreground=TEXT_COLOR, font=LINK_FONT)

        # Create the main frame.
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Header ---
        # The header label needs direct configuration to override the default style font size.
        header_label = ttk.Label(main_frame, text="Calico Settings", font=HEADER_FONT, background=BG_COLOR, foreground=TEXT_COLOR)
        header_label.pack(pady=(0, 20))

        # --- Form Fields ---
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.X)

        # Temperature Unit
        ttk.Label(form_frame, text="Temperature Unit:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.temp_unit_var = tk.StringVar()
        temp_unit_combo = ttk.Combobox(form_frame, textvariable=self.temp_unit_var, values=["Fahrenheit", "Celsius"], state="readonly")
        temp_unit_combo.grid(row=0, column=1, sticky=tk.EW, padx=10)

        # Other Units
        ttk.Label(form_frame, text="Other Units:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.other_units_var = tk.StringVar()
        other_units_combo = ttk.Combobox(form_frame, textvariable=self.other_units_var, values=["Imperial", "Metric"], state="readonly")
        other_units_combo.grid(row=1, column=1, sticky=tk.EW, padx=10)
        
        # Zip Code
        ttk.Label(form_frame, text="Zip Code:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.zip_code_var = tk.StringVar()
        zip_code_entry = ttk.Entry(form_frame, textvariable=self.zip_code_var, validate="key",
                                   validatecommand=(self.register(self.validate_zip_length), '%P'))
        zip_code_entry.grid(row=2, column=1, sticky=tk.EW, padx=10)
        
        # Region
        ttk.Label(form_frame, text="Region:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.region_var = tk.StringVar()
        region_combo = ttk.Combobox(form_frame, textvariable=self.region_var, values=["US", "CA", "GB"], state="readonly")
        region_combo.grid(row=3, column=1, sticky=tk.EW, padx=10)

        form_frame.columnconfigure(1, weight=1)

        # --- Buttons ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        # The save button now handles validation.
        save_button = ttk.Button(button_frame, text="Save", command=self.save_settings)
        save_button.pack(fill=tk.X)

        # --- About Section ---
        about_frame = ttk.Labelframe(main_frame, text="About", padding="10", style='About.TLabelframe')
        about_frame.pack(fill=tk.X, pady=(20, 10))

        # Helper function to create a composite label with a hyperlink
        def create_composite_link(parent, static_text, link_text, url):
            # Create a frame to hold the two labels side-by-side
            line_frame = ttk.Frame(parent)
            
            # Static text part
            static_label = ttk.Label(line_frame, text=static_text, font=NORMAL_FONT)
            static_label.pack(side=tk.LEFT)

            # Clickable link part
            link_label = ttk.Label(line_frame, text=link_text, style="Link.TLabel", cursor="hand2")
            link_label.bind("<Button-1>", lambda e: webbrowser.open_new(url))
            link_label.pack(side=tk.LEFT)
            
            return line_frame
        
        # Static info labels
        ttk.Label(about_frame, text="Calico v0.4.2 pre-alpha", font=NORMAL_FONT).pack(anchor=tk.W)
        ttk.Label(about_frame, text="MIT License", font=NORMAL_FONT).pack(anchor=tk.W)
        
        # Separator for visual clarity
        ttk.Separator(about_frame, orient='horizontal').pack(fill='x', pady=5)

        # Link labels using the new composite function
        create_composite_link(about_frame, "Weather Data Provided by ", "Open-Meteo.com", "https://open-meteo.com/").pack(anchor=tk.W)
        create_composite_link(about_frame, "Zip Code Data Provided by ", "Zippopotam.us", "https://zippopotam.us/").pack(anchor=tk.W)
        create_composite_link(about_frame, "View on ", "GitHub", "https://github.com/MrCarpenter24/Calico-Voice-Assistant/tree/main").pack(anchor=tk.W)
        create_composite_link(about_frame, "Built to work with ", "Rhasspy 2.5", "https://rhasspy.readthedocs.io/en/latest/").pack(anchor=tk.W)

        # Load initial settings
        self.load_settings()

    def validate_zip_length(self, new_value):
        """Validates that the zip code entry is no more than 8 characters."""
        return len(new_value) <= 8

    def load_settings(self):
        """Loads settings from the config file if it exists."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    
                    temp_unit = data.get("temp_unit", "f")
                    self.temp_unit_var.set("Fahrenheit" if temp_unit == 'f' else "Celsius")

                    other_units = data.get("other_units", "imperial")
                    self.other_units_var.set(other_units.capitalize())

                    self.zip_code_var.set(data.get("zip_code", ""))
                    self.region_var.set(data.get("region", "us").upper())

            except (json.JSONDecodeError, IOError) as e:
                messagebox.showerror("Error", f"Could not read config file: {e}")
                self.set_default_values()
        else:
            self.set_default_values()

    def set_default_values(self):
        """Sets default values for the form fields."""
        self.temp_unit_var.set("Fahrenheit")
        self.other_units_var.set("Imperial")
        self.zip_code_var.set("")
        self.region_var.set("US")

    def save_settings(self):
        """Validates the zip code and saves the settings to the config file."""
        # Step 1: Validate the zip code first.
        if not self.validate_zip_code_api():
            return # Stop the save process if validation fails

        # Step 2: If validation passes, proceed with saving.
        temp_unit_map = {"Fahrenheit": "f", "Celsius": "c"}
        
        settings = {
            "temp_unit": temp_unit_map.get(self.temp_unit_var.get()),
            "other_units": self.other_units_var.get().lower(),
            "zip_code": self.zip_code_var.get(),
            "region": self.region_var.get().lower()
        }

        try:
            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=4)
            messagebox.showinfo("Success", "Settings saved successfully!")
        except IOError as e:
            messagebox.showerror("Error", f"Could not save settings: {e}")

    def validate_zip_code_api(self):
        """
        Verifies the zip code using the zippopotam.us API.
        Returns True if valid, False otherwise.
        """
        zip_code = self.zip_code_var.get()
        region = self.region_var.get().lower()

        if not zip_code or not region:
            messagebox.showwarning("Input Required", "Please enter a zip code and select a region.")
            return False

        api_url = f"https://api.zippopotam.us/{region}/{zip_code}"

        try:
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                return True # Zip code is valid
            elif response.status_code == 404:
                messagebox.showerror("Validation Error", "Invalid zip code for the selected region. Settings were not saved.")
                return False
            else:
                messagebox.showerror("API Error", f"Could not validate zip code (Status: {response.status_code}). Settings were not saved.")
                return False
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Connection Error", f"Could not connect to the validation service: {e}")
            return False


if __name__ == "__main__":
    app = SettingsEditor()
    app.mainloop()
