import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import easyocr
import segno
from PIL import Image, ImageTk
import cv2
from tkinter import filedialog
import pyttsx3  # Import pyttsx3 for text-to-speech

class ParkingSystem:
    amount_per_hour = 10  # Set amount charged per hour

    def __init__(self, root):
        self.root = root
        self.conn = sqlite3.connect("parking.db")
        self.create_table()

        self.engine = pyttsx3.init()  # Initialize TTS engine

        self.root.title("Parking System")
        self.vehicles = []

        self.style = ttk.Style()
        self.style.configure('TButton', font=('Helvetica', 12))
        self.style.configure('TLabel', font=('Helvetica', 12))
        self.style.configure('TEntry', font=('Helvetica', 12))

        self.label = ttk.Label(root, text="Parking System")
        self.label.grid(row=0, column=0, columnspan=3, pady=10)

        self.entry_button = ttk.Button(root, text="Vehicle Entry", command=self.vehicle_entry)
        self.entry_button.grid(row=1, column=0, padx=5, pady=5)

        self.exit_button = ttk.Button(root, text="Vehicle Exit", command=self.vehicle_exit)
        self.exit_button.grid(row=1, column=1, padx=5, pady=5)

        self.payment_button = ttk.Button(root, text="Make Payment", command=self.make_payment)
        self.payment_button.grid(row=1, column=2, padx=5, pady=5)

        self.exit_program_button = ttk.Button(root, text="Exit Program", command=self.exit_program)
        self.exit_program_button.grid(row=2, column=0, columnspan=3, padx=5, pady=5)

        self.duration_var = tk.StringVar()
        self.duration_label = ttk.Label(root, textvariable=self.duration_var)
        self.duration_label.grid(row=3, column=0, columnspan=3, pady=5)

        self.update_duration_label()

    def create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate TEXT,
            entry_time TEXT,
            exit_time TEXT,
            amount_due INTEGER
        )
        """
        self.conn.execute(query)

    def update_duration_label(self):
        if self.vehicles:
            current_time = datetime.now()
            total_duration = sum((current_time - vehicle["entry_time"]).total_seconds() for vehicle in self.vehicles)

            hours = total_duration / 3600
            self.duration_var.set(f"Duration: {int(hours)} hours")
        else:
            self.duration_var.set("Duration: 0 hours")

        self.root.after(60000, self.update_duration_label)

    def vehicle_entry(self):
        self.speak("Welcome! Please wait while we scan your license plate.")
        license_plate = self.recognize_license_plate()
        if not license_plate:
            self.display_message("License plate not recognized. Please try again.")
            return

        entry_time = datetime.now()
        entry_date = entry_time.strftime("%Y-%m-%d %H:%M:%S")

        # Calculate the duration
        duration = 0
        if self.vehicles:
            current_time = datetime.now()
            total_duration = sum((current_time - vehicle["entry_time"]).total_seconds() for vehicle in self.vehicles)
            duration = total_duration / 3600

        # Calculate the amount per hour based on duration
        amount_per_hour_int = 40 if duration <= 3 else 40 + (int(duration) - 3) * 10

        message = f"Vehicle entered. License Plate: {license_plate}\n" \
                  f"Entry Date: {entry_date}\n" \
                  f"Amount Charged per Hour: ₹{amount_per_hour_int}"
        self.display_message(message)
        self.store_entry_in_db(license_plate, entry_time)
        
        self.ask_slip_preference("Entry", license_plate, entry_date)

    def recognize_license_plate(self):
        # Use a file dialog to select the license plate image
        image_path = filedialog.askopenfilename(title="Select License Plate Image", filetypes=[("Image files", "*.jpg;*.jpeg;*.png")])

        if image_path:
            # Preprocess the image
            image = cv2.imread(image_path)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

            # Use EasyOCR to read the text with detailed output
            reader = easyocr.Reader(['en'])
            result = reader.readtext(thresh, detail=1)

            # Combine text from all detected regions
            license_plate = ' '.join([text for _, text, _ in result])
            return license_plate
        else:
            print("No file selected.")
            return ""

    def store_entry_in_db(self, license_plate, entry_time):
        entry_time_str = entry_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        query = "INSERT INTO vehicles (license_plate, entry_time) VALUES (?, ?)"
        self.conn.execute(query, (license_plate, entry_time_str))
        self.conn.commit()

    def vehicle_exit(self):
        self.speak("Please wait while we scan your license plate.")
        license_plate = self.recognize_license_plate()
        if not license_plate:
            self.display_message("License plate not recognized. Please try again.")
            return

        exit_time = datetime.now()
        exit_date = exit_time.strftime("%Y-%m-%d %H:%M:%S")

        entry_time, amount_due = self.calculate_amount_due(license_plate, exit_time)

        if entry_time:
            duration = (exit_time - entry_time).total_seconds() / 3600
            message = f"Vehicle exited. License Plate: {license_plate}\n" \
                      f"Entry Date: {entry_time.strftime('%Y-%m-%d %H:%M:%S')}\n" \
                      f"Exit Date: {exit_date}\n" \
                      f"Duration: {int(duration)} hours\n" \
                      f"Amount Due: ₹{amount_due}"
            self.display_message(message)
            self.update_exit_in_db(license_plate, exit_time, amount_due)
            self.ask_slip_preference("Exit", license_plate, entry_time.strftime('%Y-%m-%d %H:%M:%S'), exit_date, amount_due)
        else:
            self.display_message(f"No entry found for license plate: {license_plate}")

    def calculate_amount_due(self, license_plate, exit_time):
        query = "SELECT entry_time FROM vehicles WHERE license_plate = ? AND exit_time IS NULL"
        cursor = self.conn.execute(query, (license_plate,))
        result = cursor.fetchone()

        if result:
            entry_time = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S.%f")
            duration = (exit_time - entry_time).total_seconds() / 3600
            amount_due = 40 if duration <= 3 else 40 + (int(duration) - 3) * 10
            return entry_time, amount_due
        else:
            return None, 0

    def update_exit_in_db(self, license_plate, exit_time, amount_due):
        exit_time_str = exit_time.strftime("%Y-%m-%d %H:%M:%S.%f")
        query = "UPDATE vehicles SET exit_time = ?, amount_due = ? WHERE license_plate = ?"
        self.conn.execute(query, (exit_time_str, amount_due, license_plate))
        self.conn.commit()

    def ask_slip_preference(self, action, license_plate, entry_date, exit_date=None, amount_due=None):
        self.speak("Would you like a digital or manual slip?")
        
        popup = tk.Toplevel(self.root)
        popup.title("Slip Preference")

        label = ttk.Label(popup, text="Choose slip preference:")
        label.grid(row=0, column=0, columnspan=2, padx=10, pady=10)

        digital_button = ttk.Button(popup, text="Digital", command=lambda: self.generate_entry_exit_qr_code(action, license_plate, entry_date, exit_date, amount_due, popup))
        digital_button.grid(row=1, column=0, padx=10, pady=10)

        manual_button = ttk.Button(popup, text="Manual", command=lambda: self.provide_manual_slip(action, license_plate, entry_date, exit_date, amount_due, popup))
        manual_button.grid(row=1, column=1, padx=10, pady=10)

    def generate_entry_exit_qr_code(self, action, license_plate, entry_date, exit_date=None, amount_due=None, popup=None):
        qr_data = f"Action: {action}\nLicense Plate: {license_plate}\nEntry Date: {entry_date}"
        if exit_date:
            qr_data += f"\nExit Date: {exit_date}\nAmount Due: ₹{amount_due}"

        qr = segno.make_qr(qr_data)
        qr_image_path = "entry_exit_qr_code.png"
        qr.save(qr_image_path)
        
        self.display_qr_code(qr_image_path)
        if popup:
            popup.destroy()

    def provide_manual_slip(self, action, license_plate, entry_date, exit_date=None, amount_due=None, popup=None):
        manual_slip = f"Action: {action}\nLicense Plate: {license_plate}\nEntry Date: {entry_date}"
        if exit_date:
            manual_slip += f"\nExit Date: {exit_date}\nAmount Due: ₹{amount_due}"

        self.display_message(manual_slip)
        if popup:
            popup.destroy()

    def display_qr_code(self, qr_image_path):
        qr_image = Image.open(qr_image_path)
        qr_image = qr_image.resize((200, 200), Image.LANCZOS)
        qr_photo = ImageTk.PhotoImage(qr_image)
        
        popup = tk.Toplevel(self.root)
        popup.title("QR Code")

        label = ttk.Label(popup, text="Scan this QR code:")
        label.grid(row=0, column=0, padx=10, pady=10)

        qr_label = ttk.Label(popup, image=qr_photo)
        qr_label.image = qr_photo  # Keep a reference to avoid garbage collection
        qr_label.grid(row=1, column=0, padx=10, pady=10)

    def speak(self, text):
        self.engine.say(text)
        self.engine.runAndWait()

    def display_message(self, message):
        popup = tk.Toplevel(self.root)
        popup.title("Message")

        label = ttk.Label(popup, text=message)
        label.grid(row=0, column=0, padx=10, pady=10)

        button = ttk.Button(popup, text="OK", command=popup.destroy)
        button.grid(row=1, column=0, padx=10, pady=10)

    def exit_program(self):
        self.conn.close()
        self.root.quit()

    def make_payment(self):
        self.speak("Please wait while we process your payment.")
        self.display_message("Payment processing is not implemented yet.")

def main():
    root = tk.Tk()
    parking_system = ParkingSystem(root)
    window_width = 400
    window_height = 400
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x_position = (screen_width - window_width) // 2
    y_position = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
    root.mainloop()

if __name__ == "__main__":
    main()
