#!/usr/bin/env python3
"""
CROUS City Monitor - Ultra Simple Version
Just reads HTML and checks if city name + postal code prefix appear together
"""

import threading
import time
import requests
from bs4 import BeautifulSoup
import re
from typing import List, Optional
from datetime import datetime, timedelta
import json
import os
import sys
from pathlib import Path


class CROUSScraper:
    def __init__(self, telegram_bot_token: str, telegram_chat_id: str, target_city: str):
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.target_city = target_city.strip().lower()
        self.base_url = "https://trouverunlogement.lescrous.fr"
        self.main_search_url = "https://trouverunlogement.lescrous.fr/tools/42/search"
        
        # City postal code prefixes (just 2 digits)
        self.city_prefixes = {
            'paris': '75',
            'lyon': '69',
            'marseille': '13',
            'toulouse': '31',
            'nice': '06',
            'nantes': '44',
            'strasbourg': '67',
            'montpellier': '34',
            'bordeaux': '33',
            'lille': '59',
            'rennes': '35',
            'reims': '51',
            'grenoble': '38',
        }
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
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

    def scan_for_city_accommodations(self, max_pages: int = 5) -> Optional[List[dict]]:
        """Scan CROUS pages - ULTRA SIMPLE"""
        results = []
        
        try:
            # Get prefix for this city
            if self.target_city not in self.city_prefixes:
                print(f"⚠️ No postal prefix defined for {self.target_city}")
                return None
            
            required_prefix = self.city_prefixes[self.target_city]
            
            # Scan pages
            for page_num in range(1, max_pages + 1):
                if page_num == 1:
                    url = self.main_search_url
                else:
                    url = f"{self.main_search_url}?page={page_num}"
                
                print(f"🔍 Scanning page {page_num}: {url}")
                
                try:
                    response = self.session.get(url, timeout=15)
                    response.raise_for_status()
                    html = response.text
                    
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Be VERY specific - only look for links to actual listings
                    # This avoids nested divs that cause duplicates
                    possible_listings = soup.find_all('a', href=re.compile(r'/logement/|/residence/'))
                    
                    # If no links found, try article tags
                    if not possible_listings:
                        possible_listings = soup.find_all('article')
                    
                    # Last resort: find divs with specific classes only
                    if not possible_listings:
                        possible_listings = soup.find_all('div', class_=re.compile(r'(card|listing|residence|logement)', re.I))
                    
                    print(f"   Found {len(possible_listings)} listing elements")
                    
                    seen_links = set()  # Track which links we've already processed
                    
                    for listing in possible_listings:
                        listing_text = listing.get_text()
                        
                        # Option 1: City name + prefix somewhere in text
                        has_city = re.search(rf'\b{re.escape(self.target_city)}\b', listing_text, re.IGNORECASE)
                        has_prefix = required_prefix in listing_text
                        
                        # Option 2: 5-digit postal code starting with prefix (e.g., 38400, 75013)
                        postal_code_pattern = rf'\b{required_prefix}\d{{3}}\b'
                        has_full_postal = re.search(postal_code_pattern, listing_text)
                        
                        # Accept if EITHER condition is true
                        if (has_city and has_prefix) or has_full_postal:
                            # Extract info
                            title = "Logement trouvé"
                            link = ""
                            
                            # Try to find link
                            if listing.name == 'a':
                                # This element IS the link
                                link_elem = listing
                            else:
                                # Find link inside this element
                                link_elem = listing.find('a', href=True)
                            
                            if link_elem and link_elem.get('href'):
                                href = link_elem.get('href')
                                if href.startswith('http'):
                                    link = href
                                else:
                                    link = self.base_url + href if href.startswith('/') else self.base_url + '/' + href
                                
                                # Skip if we've already seen this link
                                if link in seen_links:
                                    continue
                                seen_links.add(link)
                            
                            # Try to find title
                            for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                                title_elem = listing.find(tag)
                                if title_elem:
                                    title = title_elem.get_text(strip=True)
                                    break
                            
                            # Get clean text
                            clean_text = ' '.join(listing_text.split())[:400]
                            
                            result = {
                                'title': title,
                                'link': link,
                                'context': clean_text,
                                'page_number': page_num
                            }
                            
                            results.append(result)
                            print(f"   ✅ MATCH FOUND: {title}")
                
                except Exception as e:
                    print(f"   ❌ Error scanning page {page_num}: {e}")
                    continue
            
            return results if results else None
        
        except Exception as e:
            print(f"❌ Scan failed: {e}")
            return None

    def format_telegram_message(self, results: List[dict]) -> str:
        """Format results into a Telegram message"""
        city_name = self.target_city.title()
        prefix = self.city_prefixes.get(self.target_city, '??')
        
        message = f"🏠 <b>CROUS Housing Alert for {city_name}!</b>\n\n"
        message += f"Found {len(results)} listing(s) with {city_name} + postal code {prefix}xxx:\n\n"
        
        for i, result in enumerate(results, 1):
            message += f"<b>{i}. {result['title']}</b>\n"
            message += f"📍 {result['context'][:200]}...\n"
            if result['link']:
                message += f"🔗 <a href='{result['link']}'>View Details</a>\n"
            message += f"📄 Page {result.get('page_number', '?')}\n\n"
        
        message += f"🕐 Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message


class CROUSMonitorTerminal:
    def __init__(self):
        self.scraper = None
        self.monitoring = False
        self.monitor_thread = None
        self.settings_file = os.path.join(Path.home(), '.crous_monitor_settings.json')
        
        self.settings = {
            'city': '',
            'telegram_token': '',
            'telegram_chat_id': '',
            'interval_minutes': 30,
            'max_pages': 5
        }
        
        self.load_settings()

    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
                    return True
        except Exception as e:
            print(f"❌ Failed to load settings: {e}")
        return False

    def save_settings(self):
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            print(f"❌ Failed to save settings: {e}")
            return False

    def print_header(self):
        print("\n" + "="*60)
        print(" "*15 + "CROUS CITY MONITOR v4.0")
        print(" "*18 + "(Ultra Simple)")
        print("="*60 + "\n")

    def configure_settings(self):
        print("\n📝 Configuration\n" + "-"*60)
        
        city = input(f"City to monitor [{self.settings['city']}]: ").strip()
        if city:
            self.settings['city'] = city
        
        token = input(f"Telegram Bot Token [{self.settings['telegram_token'][:20] if self.settings['telegram_token'] else ''}...]: ").strip()
        if token:
            self.settings['telegram_token'] = token
        
        chat_id = input(f"Telegram Chat ID [{self.settings['telegram_chat_id']}]: ").strip()
        if chat_id:
            self.settings['telegram_chat_id'] = chat_id
        
        interval = input(f"Check interval (minutes) [{self.settings['interval_minutes']}]: ").strip()
        if interval:
            try:
                self.settings['interval_minutes'] = float(interval)
            except ValueError:
                print("⚠️ Invalid interval")
        
        max_pages = input(f"Max pages to scan (1-50) [{self.settings['max_pages']}]: ").strip()
        if max_pages:
            try:
                pages = int(max_pages)
                if 1 <= pages <= 50:
                    self.settings['max_pages'] = pages
            except ValueError:
                print("⚠️ Invalid number")
        
        if self.save_settings():
            print("✅ Settings saved!")
        else:
            print("❌ Failed to save settings")

    def view_settings(self):
        print("\n⚙️  Current Settings\n" + "-"*60)
        print(f"City: {self.settings['city']}")
        print(f"Telegram Token: {self.settings['telegram_token'][:20]}..." if self.settings['telegram_token'] else "Not set")
        print(f"Telegram Chat ID: {self.settings['telegram_chat_id']}")
        print(f"Check Interval: {self.settings['interval_minutes']} minutes")
        print(f"Max Pages: {self.settings['max_pages']}")
        print()

    def validate_settings(self):
        if not self.settings['city']:
            print("❌ City not set!")
            return False
        if not self.settings['telegram_token']:
            print("❌ Telegram token not set!")
            return False
        if not self.settings['telegram_chat_id']:
            print("❌ Telegram chat ID not set!")
            return False
        return True

    def test_check(self):
        if not self.validate_settings():
            print("⚠️ Please configure settings first (option 2)")
            return
        
        print(f"\nℹ️ Starting test check for {self.settings['city'].title()}...")
        print(f"ℹ️ Scanning up to {self.settings['max_pages']} pages...\n")
        
        try:
            scraper = CROUSScraper(
                self.settings['telegram_token'],
                self.settings['telegram_chat_id'],
                self.settings['city']
            )
            
            results = scraper.scan_for_city_accommodations(self.settings['max_pages'])
            
            if results:
                print(f"\n✅ {len(results)} listing(s) found!")
                message = scraper.format_telegram_message(results)
                if scraper.send_telegram_message(message):
                    print("✅ Telegram notification sent!")
                else:
                    print("❌ Failed to send Telegram message")
            else:
                print(f"\nℹ️ No listings found for {self.settings['city'].title()}")
        
        except Exception as e:
            print(f"❌ Test check failed: {e}")

    def monitoring_loop(self):
        interval_seconds = self.settings['interval_minutes'] * 60
        
        try:
            while self.monitoring:
                try:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting scheduled check...")
                    
                    results = self.scraper.scan_for_city_accommodations(self.settings['max_pages'])
                    
                    if results:
                        message = self.scraper.format_telegram_message(results)
                        if self.scraper.send_telegram_message(message):
                            print(f"✅ {len(results)} listing(s) found! Notification sent.")
                        else:
                            print(f"⚠️ Found listings but failed to send notification")
                    else:
                        print(f"ℹ️ No listings found")
                    
                    next_time = datetime.now() + timedelta(minutes=self.settings['interval_minutes'])
                    print(f"ℹ️ Next check at: {next_time.strftime('%H:%M:%S')}")
                    
                    for remaining in range(int(interval_seconds), 0, -1):
                        if not self.monitoring:
                            break
                        time.sleep(1)
                
                except Exception as e:
                    print(f"❌ Error during monitoring: {e}")
                    time.sleep(60)
        
        except KeyboardInterrupt:
            self.stop_monitoring()

    def start_monitoring(self):
        if not self.validate_settings():
            print("⚠️ Please configure settings first (option 2)")
            return
        
        if self.monitoring:
            print("⚠️ Monitoring is already running!")
            return
        
        try:
            self.scraper = CROUSScraper(
                self.settings['telegram_token'],
                self.settings['telegram_chat_id'],
                self.settings['city']
            )
            
            self.monitoring = True
            
            startup_message = f"🤖 <b>CROUS {self.settings['city'].title()} Monitor Started!</b>\n\nMonitoring every {self.settings['interval_minutes']} minutes."
            self.scraper.send_telegram_message(startup_message)
            
            print(f"✅ Monitoring started for {self.settings['city'].title()}")
            print(f"ℹ️ Check interval: {self.settings['interval_minutes']} minutes")
            print(f"ℹ️ Press Ctrl+C to stop\n")
            
            self.monitor_thread = threading.Thread(
                target=self.monitoring_loop,
                daemon=True
            )
            self.monitor_thread.start()
            
            try:
                while self.monitoring:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop_monitoring()
        
        except Exception as e:
            print(f"❌ Failed to start monitoring: {e}")

    def stop_monitoring(self):
        if not self.monitoring:
            print("⚠️ Monitoring is not running")
            return
        
        self.monitoring = False
        
        if self.scraper:
            stop_message = f"🛑 <b>CROUS {self.settings['city'].title()} Monitor Stopped</b>"
            self.scraper.send_telegram_message(stop_message)
        
        print("✅ Monitoring stopped")

    def show_menu(self):
        print("\n📋 Main Menu\n" + "-"*60)
        print("1. Start Monitoring")
        print("2. Configure Settings")
        print("3. View Current Settings")
        print("4. Test Check (single scan)")
        print("5. Stop Monitoring")
        print("6. Exit")
        print("-"*60)

    def run(self):
        self.print_header()
        
        if os.path.exists(self.settings_file):
            print("✅ Previous settings loaded")
        else:
            print("ℹ️ No previous settings found")
        
        while True:
            self.show_menu()
            
            try:
                choice = input("\nEnter your choice (1-6): ").strip()
                
                if choice == '1':
                    self.start_monitoring()
                elif choice == '2':
                    self.configure_settings()
                elif choice == '3':
                    self.view_settings()
                elif choice == '4':
                    self.test_check()
                elif choice == '5':
                    self.stop_monitoring()
                elif choice == '6':
                    if self.monitoring:
                        self.stop_monitoring()
                    print("\nGoodbye! 👋\n")
                    sys.exit(0)
                else:
                    print("⚠️ Invalid choice. Please enter 1-6")
            
            except KeyboardInterrupt:
                print("\n")
                if self.monitoring:
                    self.stop_monitoring()
                print("\nGoodbye! 👋\n")
                sys.exit(0)
            except Exception as e:
                print(f"❌ An error occurred: {e}")


if __name__ == "__main__":
    app = CROUSMonitorTerminal()
    app.run()
