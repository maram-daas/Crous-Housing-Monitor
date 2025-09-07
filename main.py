import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import logging
from typing import List, Optional
from datetime import datetime
import json
import os


class CROUSScraper:
    def __init__(self, telegram_bot_token: str, telegram_chat_id: str, target_city: str):
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.target_city = target_city.strip().lower()
        self.base_url = "https://trouverunlogement.lescrous.fr"
        self.main_search_url = "https://trouverunlogement.lescrous.fr/tools/41/search"

        # Session for maintaining cookies and better performance
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def send_telegram_message(self, message: str) -> bool:
        """Send a message to Telegram bot"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def fetch_page_content(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a webpage"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup
        except Exception:
            return None

    def remove_only_search_elements(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Remove ONLY search-related UI elements, keep everything else"""
        search_selectors_to_remove = [
            '.search-suggestions', '.autocomplete', '.search-form', '.search-bar',
            '.search-input', 'input[type="search"]', '[class*="search-suggestion"]',
            '[class*="autocomplete"]', '[id*="search-suggestion"]', '[id*="autocomplete"]',
            'script', 'style',
        ]

        for selector in search_selectors_to_remove:
            elements = soup.select(selector)
            for element in elements:
                element.decompose()

        return soup

    def check_for_city_anywhere(self, soup: BeautifulSoup, url: str) -> bool:
        """Check if the target city appears anywhere in content, excluding only search elements"""
        try:
            cleaned_soup = self.remove_only_search_elements(soup)
            all_text = cleaned_soup.get_text()
            pattern = rf'\b{re.escape(self.target_city)}\b'
            return bool(re.search(pattern, all_text, re.IGNORECASE))
        except Exception:
            return False

    def extract_city_context(self, soup: BeautifulSoup) -> List[dict]:
        """Extract all contexts where the target city appears (except search elements)"""
        contexts = []
        try:
            cleaned_soup = self.remove_only_search_elements(soup)
            pattern = rf'\b{re.escape(self.target_city)}\b'
            all_elements = cleaned_soup.find_all(
                text=re.compile(pattern, re.IGNORECASE))

            for text in all_elements:
                parent = text.parent
                if parent:
                    element_text = parent.get_text(strip=True)
                    title = "Unknown"
                    link = ""

                    for title_tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        title_elem = parent.find(title_tag) or parent.find_previous(
                            title_tag) or parent.find_next(title_tag)
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            break

                    link_elem = parent.find('a') or parent.find_parent('a')
                    if link_elem and link_elem.get('href'):
                        link = urljoin(self.base_url, link_elem.get('href'))

                    context = element_text[:400].strip()
                    context = ' '.join(context.split())

                    if context and len(context) > 10:
                        contexts.append({
                            'title': title,
                            'link': link,
                            'context': context,
                            'element_type': parent.name or 'text'
                        })

            unique_contexts = []
            seen_contexts = set()
            for ctx in contexts:
                context_key = ctx['context'][:100]
                if context_key not in seen_contexts:
                    seen_contexts.add(context_key)
                    unique_contexts.append(ctx)

            return unique_contexts
        except Exception:
            return []

    def scan_single_url(self, url: str) -> dict:
        """Scan a single URL for city mentions anywhere in content"""
        soup = self.fetch_page_content(url)
        if not soup:
            return {'found_city': False, 'contexts': [], 'url': url}

        found_city = self.check_for_city_anywhere(soup, url)
        contexts = []
        if found_city:
            contexts = self.extract_city_context(soup)

        return {
            'found_city': found_city,
            'contexts': contexts,
            'url': url
        }

    def scan_for_city_accommodations(self) -> List[dict]:
        """Main method to scan for city mentions anywhere in content"""
        all_city_results = []
        urls_to_check = [
            self.main_search_url,
            f"{self.main_search_url}?page=2"
        ]

        for url in urls_to_check:
            result = self.scan_single_url(url)
            if result['found_city']:
                all_city_results.append(result)

        return all_city_results

    def format_telegram_message(self, results: List[dict]) -> str:
        """Format city findings into a Telegram message"""
        if not results:
            return f"No {self.target_city.title()} mentions found on the CROUS housing website."

        city_name = self.target_city.title()
        message = f"🏠 <b>{city_name.upper()} FOUND!</b>\n\n"
        total_contexts = sum(len(result['contexts']) for result in results)
        message += f"Found {city_name} mentioned {total_contexts} time(s) on {len(results)} page(s):\n\n"

        for i, result in enumerate(results, 1):
            message += f"<b>📍 Page {i}:</b>\n"
            message += f"🔗 <a href='{result['url']}'>View Page</a>\n\n"

            contexts = result.get('contexts', [])
            if contexts:
                message += f"<b>🔍 Found {len(contexts)} mention(s):</b>\n"
                for j, context in enumerate(contexts[:3], 1):
                    message += f"\n<b>{j}. {context.get('title', 'Unknown')}</b>\n"
                    if context.get('link'):
                        message += f"🔗 <a href='{context['link']}'>View Details</a>\n"
                    ctx_text = context.get('context', '')[:250]
                    message += f"📝 {ctx_text}...\n"

                if len(contexts) > 3:
                    message += f"\n... and {len(contexts) - 3} more mentions\n"

            message += "\n➖➖➖➖➖➖➖➖➖➖\n\n"

        return message


class CROUSMonitorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("CROUS City Monitor")
        self.root.geometry("600x700")
        self.root.resizable(True, True)

        # Settings file path
        self.settings_file = "crous_monitor_settings.json"

        # Pastel pink color scheme
        self.colors = {
            'bg': '#FFE1E6',           # Light pastel pink background
            'secondary_bg': '#F8BBD9',  # Slightly darker pink
            'accent': '#E91E63',       # Bright pink accent
            'button_bg': '#F48FB1',    # Medium pink for buttons
            'button_active': '#EC407A',  # Darker pink for active state
            'text': '#4A0E0E',         # Dark brown-red for text
            'success': '#C8E6C9',      # Light green for success
            'error': '#FFCDD2'         # Light red for errors
        }

        self.root.configure(bg=self.colors['bg'])

        # Variables
        self.monitoring = False
        self.monitor_thread = None
        self.scraper = None

        self.setup_ui()
        self.setup_logging()
        self.load_settings()

        # Save settings when window is closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_settings(self):
        """Load settings from JSON file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)

                # Load settings into fields
                self.city_entry.delete(0, tk.END)
                self.city_entry.insert(0, settings.get('target_city', ''))

                self.token_entry.delete(0, tk.END)
                self.token_entry.insert(0, settings.get('telegram_token', ''))

                self.chat_id_entry.delete(0, tk.END)
                self.chat_id_entry.insert(
                    0, settings.get('telegram_chat_id', ''))

                self.interval_var.set(settings.get('check_interval', ''))

                self.log_message("Settings loaded successfully")
            else:
                self.log_message(
                    "No previous settings found - starting with empty fields")
        except Exception as e:
            self.log_message(f"Failed to load settings: {str(e)}", "WARNING")

    def save_settings(self):
        """Save current settings to JSON file"""
        try:
            settings = {
                'target_city': self.city_entry.get().strip(),
                'telegram_token': self.token_entry.get().strip(),
                'telegram_chat_id': self.chat_id_entry.get().strip(),
                'check_interval': self.interval_var.get().strip(),
                'saved_at': datetime.now().isoformat()
            }

            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)

            self.log_message("Settings saved successfully")
        except Exception as e:
            self.log_message(f"Failed to save settings: {str(e)}", "ERROR")

    def on_closing(self):
        """Handle window close event"""
        # Save settings if any fields have content
        if any([self.city_entry.get().strip(),
                self.token_entry.get().strip(),
                self.chat_id_entry.get().strip()]):
            self.save_settings()

        # Stop monitoring if running
        if self.monitoring:
            self.monitoring = False

        self.root.destroy()

    def setup_ui(self):
        # Main frame
        main_frame = tk.Frame(
            self.root, bg=self.colors['bg'], padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(
            main_frame,
            text="🏠 CROUS City Monitor",
            font=('Arial', 18, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['text']
        )
        title_label.pack(pady=(0, 20))

        # Configuration Frame
        config_frame = tk.LabelFrame(
            main_frame,
            text="Configuration",
            font=('Arial', 12, 'bold'),
            bg=self.colors['secondary_bg'],
            fg=self.colors['text'],
            padx=15,
            pady=15
        )
        config_frame.pack(fill=tk.X, pady=(0, 15))

        # Target City
        tk.Label(
            config_frame,
            text="Target City:",
            bg=self.colors['secondary_bg'],
            fg=self.colors['text'],
            font=('Arial', 10)
        ).grid(row=0, column=0, sticky=tk.W, pady=5)

        self.city_entry = tk.Entry(
            config_frame,
            width=50,
            font=('Arial', 9)
        )
        self.city_entry.grid(row=0, column=1, padx=(
            10, 0), pady=5, sticky=tk.EW)

        # Telegram Bot Token
        tk.Label(
            config_frame,
            text="Telegram Bot Token:",
            bg=self.colors['secondary_bg'],
            fg=self.colors['text'],
            font=('Arial', 10)
        ).grid(row=1, column=0, sticky=tk.W, pady=5)

        self.token_entry = tk.Entry(
            config_frame,
            width=50,
            font=('Arial', 9)
        )
        self.token_entry.grid(row=1, column=1, padx=(
            10, 0), pady=5, sticky=tk.EW)

        # Telegram Chat ID
        tk.Label(
            config_frame,
            text="Telegram Chat ID:",
            bg=self.colors['secondary_bg'],
            fg=self.colors['text'],
            font=('Arial', 10)
        ).grid(row=2, column=0, sticky=tk.W, pady=5)

        self.chat_id_entry = tk.Entry(
            config_frame,
            width=50,
            font=('Arial', 9)
        )
        self.chat_id_entry.grid(
            row=2, column=1, padx=(10, 0), pady=5, sticky=tk.EW)

        # Time interval
        tk.Label(
            config_frame,
            text="Check Interval (minutes):",
            bg=self.colors['secondary_bg'],
            fg=self.colors['text'],
            font=('Arial', 10)
        ).grid(row=3, column=0, sticky=tk.W, pady=5)

        self.interval_var = tk.StringVar(value="")  # Start empty
        interval_frame = tk.Frame(config_frame, bg=self.colors['secondary_bg'])
        interval_frame.grid(row=3, column=1, padx=(10, 0), pady=5, sticky=tk.W)

        self.interval_entry = tk.Entry(
            interval_frame,
            textvariable=self.interval_var,
            width=10,
            font=('Arial', 9)
        )
        self.interval_entry.pack(side=tk.LEFT)

        tk.Label(
            interval_frame,
            text="minutes",
            bg=self.colors['secondary_bg'],
            fg=self.colors['text'],
            font=('Arial', 10)
        ).pack(side=tk.LEFT, padx=(5, 0))

        config_frame.columnconfigure(1, weight=1)

        # Control buttons frame
        control_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        control_frame.pack(fill=tk.X, pady=(0, 15))

        # Start button
        self.start_button = tk.Button(
            control_frame,
            text="▶ Start Monitoring",
            command=self.start_monitoring,
            bg=self.colors['button_bg'],
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20,
            pady=10,
            relief=tk.RAISED,
            borderwidth=2
        )
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))

        # Stop button
        self.stop_button = tk.Button(
            control_frame,
            text="⏹ Stop Monitoring",
            command=self.stop_monitoring,
            bg=self.colors['button_bg'],
            fg='white',
            font=('Arial', 12, 'bold'),
            padx=20,
            pady=10,
            relief=tk.RAISED,
            borderwidth=2,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))

        # Test button
        self.test_button = tk.Button(
            control_frame,
            text="🧪 Test Check",
            command=self.test_check,
            bg=self.colors['secondary_bg'],
            fg=self.colors['text'],
            font=('Arial', 10),
            padx=15,
            pady=8,
            relief=tk.RAISED,
            borderwidth=1
        )
        self.test_button.pack(side=tk.LEFT)

        # Status frame
        status_frame = tk.LabelFrame(
            main_frame,
            text="Status",
            font=('Arial', 12, 'bold'),
            bg=self.colors['secondary_bg'],
            fg=self.colors['text'],
            padx=15,
            pady=10
        )
        status_frame.pack(fill=tk.X, pady=(0, 15))

        self.status_label = tk.Label(
            status_frame,
            text="Status: Ready to start",
            bg=self.colors['secondary_bg'],
            fg=self.colors['text'],
            font=('Arial', 11)
        )
        self.status_label.pack(anchor=tk.W)

        self.next_check_label = tk.Label(
            status_frame,
            text="Next check: Not scheduled",
            bg=self.colors['secondary_bg'],
            fg=self.colors['text'],
            font=('Arial', 10)
        )
        self.next_check_label.pack(anchor=tk.W)

        # Log frame
        log_frame = tk.LabelFrame(
            main_frame,
            text="Activity Log",
            font=('Arial', 12, 'bold'),
            bg=self.colors['secondary_bg'],
            fg=self.colors['text'],
            padx=15,
            pady=10
        )
        log_frame.pack(fill=tk.BOTH, expand=True)

        # Log text area
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=15,
            bg='white',
            fg=self.colors['text'],
            font=('Consolas', 9),
            wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Clear log button
        clear_button = tk.Button(
            log_frame,
            text="Clear Log",
            command=self.clear_log,
            bg=self.colors['button_bg'],
            fg='white',
            font=('Arial', 9),
            padx=10,
            pady=5
        )
        clear_button.pack(anchor=tk.E, pady=(5, 0))

    def setup_logging(self):
        """Setup custom logging to display in GUI"""
        class GUILogHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget

            def emit(self, record):
                msg = self.format(record)
                timestamp = datetime.now().strftime("%H:%M:%S")
                self.text_widget.insert(tk.END, f"[{timestamp}] {msg}\n")
                self.text_widget.see(tk.END)

        # Setup logger
        self.logger = logging.getLogger("CROUSMonitor")
        self.logger.setLevel(logging.INFO)

        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Add GUI handler
        gui_handler = GUILogHandler(self.log_text)
        gui_handler.setFormatter(
            logging.Formatter('%(levelname)s - %(message)s'))
        self.logger.addHandler(gui_handler)

    def log_message(self, message, level="INFO"):
        """Log a message to the GUI"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {level} - {message}\n")
        self.log_text.see(tk.END)

    def clear_log(self):
        """Clear the log text area"""
        self.log_text.delete(1.0, tk.END)

    def start_monitoring(self):
        """Start the monitoring process"""
        try:
            # Validate inputs
            city_name = self.city_entry.get().strip()
            token = self.token_entry.get().strip()
            chat_id = self.chat_id_entry.get().strip()
            interval_str = self.interval_var.get().strip()

            if not city_name or not token or not chat_id or not interval_str:
                messagebox.showerror(
                    "Error", "Please fill in all configuration fields!")
                return

            try:
                interval_minutes = float(interval_str)
                if interval_minutes <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror(
                    "Error", "Please enter a valid positive number for the interval!")
                return

            # Create scraper instance
            self.scraper = CROUSScraper(token, chat_id, city_name)

            # Update UI
            self.monitoring = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.test_button.config(state=tk.DISABLED)

            # Update status
            self.status_label.config(text="Status: Monitoring active")

            # Send startup message
            startup_message = f"🤖 <b>CROUS {city_name.title()} Monitor Started!</b>\n\nMonitoring for {city_name.title()} mentions every {interval_minutes} minutes..."
            self.scraper.send_telegram_message(startup_message)

            # Start monitoring thread
            self.monitor_thread = threading.Thread(
                target=self.monitoring_loop,
                args=(interval_minutes,),
                daemon=True
            )
            self.monitor_thread.start()

            self.log_message(
                f"Monitoring started for {city_name.title()} with {interval_minutes} minute interval")

        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to start monitoring: {str(e)}")
            self.log_message(f"Failed to start monitoring: {str(e)}", "ERROR")

    def stop_monitoring(self):
        """Stop the monitoring process"""
        self.monitoring = False

        # Send stop message to Telegram
        if self.scraper:
            city_name = self.scraper.target_city.title()
            stop_message = f"🛑 <b>CROUS {city_name} Monitor Stopped</b>\n\nMonitoring has been stopped by user."
            self.scraper.send_telegram_message(stop_message)

        # Update UI
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.test_button.config(state=tk.NORMAL)

        # Update status
        self.status_label.config(text="Status: Monitoring stopped")
        self.next_check_label.config(text="Next check: Not scheduled")

        self.log_message("Monitoring stopped by user")

    def test_check(self):
        """Perform a single test check"""
        try:
            # Validate inputs
            city_name = self.city_entry.get().strip()
            token = self.token_entry.get().strip()
            chat_id = self.chat_id_entry.get().strip()

            if not city_name or not token or not chat_id:
                messagebox.showerror(
                    "Error", "Please fill in all configuration fields!")
                return

            self.test_button.config(state=tk.DISABLED)
            self.log_message(f"Starting test check for {city_name.title()}...")

            # Create scraper and run test
            scraper = CROUSScraper(token, chat_id, city_name)

            def run_test():
                try:
                    results = scraper.scan_for_city_accommodations()
                    if results:
                        message = scraper.format_telegram_message(results)
                        success = scraper.send_telegram_message(message)
                        if success:
                            self.log_message(
                                f"Test check completed - {city_name.title()} found and message sent!")
                        else:
                            self.log_message(
                                f"Test check completed - {city_name.title()} found but failed to send message", "WARNING")
                    else:
                        self.log_message(
                            f"Test check completed - No {city_name.title()} mentions found")

                except Exception as e:
                    self.log_message(f"Test check failed: {str(e)}", "ERROR")
                finally:
                    self.test_button.config(state=tk.NORMAL)

            threading.Thread(target=run_test, daemon=True).start()

        except Exception as e:
            self.test_button.config(state=tk.NORMAL)
            messagebox.showerror("Error", f"Test check failed: {str(e)}")
            self.log_message(f"Test check failed: {str(e)}", "ERROR")

    def monitoring_loop(self, interval_minutes):
        """Main monitoring loop running in separate thread"""
        interval_seconds = interval_minutes * 60

        try:
            while self.monitoring:
                try:
                    # Calculate next check time
                    next_check = datetime.now().replace(second=0, microsecond=0)
                    next_check = next_check.replace(
                        minute=next_check.minute + int(interval_minutes))
                    self.next_check_label.config(
                        text=f"Next check: {next_check.strftime('%H:%M')}")

                    self.log_message("Starting scheduled check...")

                    # Perform check
                    results = self.scraper.scan_for_city_accommodations()

                    if results:
                        message = self.scraper.format_telegram_message(results)
                        success = self.scraper.send_telegram_message(message)
                        city_name = self.scraper.target_city.title()
                        if success:
                            self.log_message(
                                f"✅ {city_name} found! Telegram notification sent.")
                        else:
                            self.log_message(
                                f"⚠️ {city_name} found but failed to send Telegram message", "WARNING")
                    else:
                        city_name = self.scraper.target_city.title()
                        self.log_message(f"No {city_name} mentions found")

                    # Wait for next check
                    for remaining in range(int(interval_seconds), 0, -1):
                        if not self.monitoring:
                            break
                        time.sleep(1)

                except Exception as e:
                    self.log_message(
                        f"Error during monitoring: {str(e)}", "ERROR")
                    time.sleep(60)

        except Exception:
            pass
        finally:
            # Send notification if monitoring stopped unexpectedly (not by user)
            if self.monitoring:
                city_name = self.scraper.target_city.title()
                error_message = f"❌ <b>CROUS {city_name} Monitor Stopped</b>\n\nMonitoring has stopped unexpectedly."
                self.scraper.send_telegram_message(error_message)
                self.monitoring = False

    def run(self):
        """Start the GUI application"""
        self.log_message("CROUS City Monitor GUI started")
        if os.path.exists(self.settings_file):
            self.log_message("Previous settings loaded")
        else:
            self.log_message(
                "Please configure your settings and click 'Start Monitoring' to begin")
        self.root.mainloop()


if __name__ == "__main__":
    app = CROUSMonitorGUI()
    app.run()
