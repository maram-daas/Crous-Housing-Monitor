#!/usr/bin/env python3
"""
CROUS City Monitor - Terminal Version for macOS (CORRECTED)
Monitors CROUS housing listings for specific cities and sends Telegram notifications
Version 2.0 - Fixed false positive detection (e.g., Paris vs Paris Saclay)
"""

import threading
import time
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import logging
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
        
        # City-specific postal code patterns for better detection
        self.city_postal_codes = {
            'paris': r'75\d{3}',
            'lyon': r'69\d{3}',
            'marseille': r'13\d{3}',
            'toulouse': r'31\d{3}',
            'nice': r'06\d{3}',
            'nantes': r'44\d{3}',
            'strasbourg': r'67\d{3}',
            'montpellier': r'34\d{3}',
            'bordeaux': r'33\d{3}',
            'lille': r'59\d{3}',
            'rennes': r'35\d{3}',
            'reims': r'51\d{3}',
            'grenoble': r'38\d{3}',
        }
        
        # Patterns to exclude (false positives) - DISABLED to include Paris Saclay, Paris Sud, etc.
        self.exclusion_patterns = {
            # All exclusions removed - user wants to include everything
        }
        
        # Session for maintaining cookies and better performance
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://trouverunlogement.lescrous.fr/',
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

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        """Extract total number of pages from pagination"""
        try:
            # Look for pagination elements
            title = soup.find('title')
            if title:
                title_text = title.get_text()
                match = re.search(r'page\s+\d+\s+(?:sur|of)\s+(\d+)', title_text, re.IGNORECASE)
                if match:
                    return int(match.group(1))
            
            # Pattern 2: Look for pagination navigation
            pagination_selectors = [
                '.pagination',
                '[class*="paging"]',
                '[class*="pagination"]',
                'nav[aria-label*="pagination"]',
                '.page-numbers'
            ]
            
            for selector in pagination_selectors:
                pagination = soup.select(selector)
                if pagination:
                    page_links = pagination[0].find_all(['a', 'span', 'button'])
                    page_numbers = []
                    for link in page_links:
                        text = link.get_text(strip=True)
                        if text.isdigit():
                            page_numbers.append(int(text))
                    if page_numbers:
                        return max(page_numbers)
            
            # Pattern 3: Look in page text for "X résultats"
            text_content = soup.get_text()
            results_match = re.search(r'(\d+)\s+résultats?', text_content, re.IGNORECASE)
            if results_match:
                total_results = int(results_match.group(1))
                estimated_pages = (total_results + 19) // 20
                return min(estimated_pages, 10)
            
            # Pattern 4: Check URL parameters in links
            links = soup.find_all('a', href=True)
            max_page = 1
            for link in links:
                href = link.get('href', '')
                page_match = re.search(r'[?&]page=(\d+)', href)
                if page_match:
                    page_num = int(page_match.group(1))
                    max_page = max(max_page, page_num)
            
            if max_page > 1:
                return max_page
            
            return 1
        except Exception:
            return 1

    def remove_only_search_elements(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Remove ONLY search-related UI elements, keep everything else"""
        search_selectors_to_remove = [
            '.search-suggestions',
            '.autocomplete',
            '.search-form',
            '.search-bar',
            '.search-input',
            'input[type="search"]',
            '[class*="search-suggestion"]',
            '[class*="autocomplete"]',
            '[id*="search-suggestion"]',
            '[id*="autocomplete"]',
            'script',
            'style',
        ]
        
        for selector in search_selectors_to_remove:
            elements = soup.select(selector)
            for element in elements:
                element.decompose()
        
        return soup

    def is_false_positive(self, text: str) -> bool:
        """Check if the city mention is a false positive"""
        text_lower = text.lower()
        
        # Check exclusion patterns for this city
        if self.target_city in self.exclusion_patterns:
            for pattern in self.exclusion_patterns[self.target_city]:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return True
        
        return False

    def extract_postal_code(self, text: str) -> Optional[str]:
        """Extract postal code from text"""
        postal_match = re.search(r'\b(\d{5})\b', text)
        if postal_match:
            return postal_match.group(1)
        return None

    def is_valid_city_match(self, text: str) -> bool:
        """Validate if the city match is genuine - STRICT: must have correct postal code"""
        # Extract postal code
        postal_code = self.extract_postal_code(text)
        
        # For Paris: MUST have postal code 75xxx, reject everything else
        if self.target_city == 'paris':
            if postal_code:
                # Only accept 75xxx codes
                if postal_code.startswith('75'):
                    return True
                else:
                    # Reject if postal code is 91, 92, or anything other than 75
                    return False
            else:
                # No postal code found - reject to be safe
                return False
        
        # For other cities with postal code patterns
        if self.target_city in self.city_postal_codes and postal_code:
            pattern = self.city_postal_codes[self.target_city]
            return bool(re.match(pattern, postal_code))
        
        # For cities without specific postal codes, require city name + postal code
        city_pattern = rf'\b{re.escape(self.target_city)}\b'
        has_city = bool(re.search(city_pattern, text.lower(), re.IGNORECASE))
        return has_city and postal_code is not None

    def check_for_city_anywhere(self, soup: BeautifulSoup, url: str) -> bool:
        """Check if the target city appears anywhere in content (with validation)"""
        try:
            cleaned_soup = self.remove_only_search_elements(soup)
            all_text = cleaned_soup.get_text()
            
            # Check if city name exists
            pattern = rf'\b{re.escape(self.target_city)}\b'
            if not re.search(pattern, all_text, re.IGNORECASE):
                return False
            
            # Validate the match
            return self.is_valid_city_match(all_text)
        except Exception:
            return False

    def extract_city_context(self, soup: BeautifulSoup) -> List[dict]:
        """Extract all contexts where the target city appears (with validation)"""
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
                    
                    # Validate this is a genuine match
                    if not self.is_valid_city_match(element_text):
                        continue
                    
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
                            'page_url': soup.find('link', rel='canonical')['href'] 
                                if soup.find('link', rel='canonical') else ""
                        })
            
            unique_contexts = []
            seen = set()
            for ctx in contexts:
                key = (ctx['title'], ctx['context'][:100])
                if key not in seen:
                    seen.add(key)
                    unique_contexts.append(ctx)
            
            return unique_contexts[:5]
        
        except Exception:
            return []

    def scan_for_city_accommodations(self, max_pages: int = 5) -> Optional[List[dict]]:
        """Scan CROUS website for accommodations in target city"""
        results = []
        
        try:
            first_page_soup = self.fetch_page_content(self.main_search_url)
            if not first_page_soup:
                return None
            
            total_pages_available = self.get_total_pages(first_page_soup)
            pages_to_scan = min(max_pages, total_pages_available)
            
            if self.check_for_city_anywhere(first_page_soup, self.main_search_url):
                contexts = self.extract_city_context(first_page_soup)
                for ctx in contexts:
                    ctx['page_number'] = 1
                results.extend(contexts)
            
            for page_num in range(2, pages_to_scan + 1):
                page_url = f"{self.main_search_url}?page={page_num}"
                soup = self.fetch_page_content(page_url)
                
                if not soup:
                    continue
                
                if self.check_for_city_anywhere(soup, page_url):
                    contexts = self.extract_city_context(soup)
                    for ctx in contexts:
                        ctx['page_number'] = page_num
                    results.extend(contexts)
            
            return results if results else None
        
        except Exception:
            return None

    def format_telegram_message(self, results: List[dict]) -> str:
        """Format results into a Telegram message"""
        city_name = self.target_city.title()
        message = f"🏠 <b>CROUS Housing Alert for {city_name}!</b>\n\n"
        message += f"Found {len(results)} mention(s) of {city_name}:\n\n"
        
        for i, result in enumerate(results, 1):
            message += f"<b>{i}. {result['title']}</b>\n"
            message += f"📍 {result['context'][:200]}...\n"
            if result['link']:
                message += f"🔗 <a href='{result['link']}'>View Details</a>\n"
            message += f"📄 Page {result.get('page_number', 'Unknown')}\n\n"
        
        message += f"🕐 Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return message


class CROUSMonitorTerminal:
    def __init__(self):
        self.scraper = None
        self.monitoring = False
        self.monitor_thread = None
        self.settings_file = os.path.join(Path.home(), '.crous_monitor_settings.json')
        
        # Default settings
        self.settings = {
            'city': '',
            'telegram_token': '',
            'telegram_chat_id': '',
            'interval_minutes': 30,
            'max_pages': 5
        }
        
        self.load_settings()

    def load_settings(self):
        """Load settings from file"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
                    return True
        except Exception as e:
            self.print_error(f"Failed to load settings: {e}")
        return False

    def save_settings(self):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            self.print_error(f"Failed to save settings: {e}")
            return False

    def print_header(self):
        """Print application header"""
        print("\n" + "="*60)
        print(" "*10 + "CROUS CITY MONITOR - Terminal v3.0")
        print(" "*12 + "(Strict Postal Code Validation)")
        print("="*60 + "\n")

    def print_success(self, message):
        """Print success message"""
        print(f"✅ {message}")

    def print_error(self, message):
        """Print error message"""
        print(f"❌ {message}")

    def print_info(self, message):
        """Print info message"""
        print(f"ℹ️  {message}")

    def print_warning(self, message):
        """Print warning message"""
        print(f"⚠️  {message}")

    def print_log(self, message):
        """Print log message with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {message}")

    def configure_settings(self):
        """Interactive configuration"""
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
                self.print_warning("Invalid interval, keeping previous value")
        
        max_pages = input(f"Max pages to scan (1-50) [{self.settings['max_pages']}]: ").strip()
        if max_pages:
            try:
                pages = int(max_pages)
                if 1 <= pages <= 50:
                    self.settings['max_pages'] = pages
                else:
                    self.print_warning("Max pages must be 1-50, keeping previous value")
            except ValueError:
                self.print_warning("Invalid number, keeping previous value")
        
        if self.save_settings():
            self.print_success("Settings saved successfully!")
        else:
            self.print_error("Failed to save settings")

    def view_settings(self):
        """Display current settings"""
        print("\n⚙️  Current Settings\n" + "-"*60)
        print(f"City: {self.settings['city']}")
        print(f"Telegram Token: {self.settings['telegram_token'][:20]}..." if self.settings['telegram_token'] else "Not set")
        print(f"Telegram Chat ID: {self.settings['telegram_chat_id']}")
        print(f"Check Interval: {self.settings['interval_minutes']} minutes")
        print(f"Max Pages: {self.settings['max_pages']}")
        print()

    def validate_settings(self):
        """Check if settings are valid"""
        if not self.settings['city']:
            self.print_error("City not set!")
            return False
        if not self.settings['telegram_token']:
            self.print_error("Telegram token not set!")
            return False
        if not self.settings['telegram_chat_id']:
            self.print_error("Telegram chat ID not set!")
            return False
        return True

    def test_check(self):
        """Perform a single test check"""
        if not self.validate_settings():
            self.print_warning("Please configure settings first (option 2)")
            return
        
        self.print_info(f"Starting test check for {self.settings['city'].title()}...")
        self.print_info(f"Scanning up to {self.settings['max_pages']} pages...")
        self.print_info("🔍 STRICT mode: Only 75xxx postal codes for Paris...")
        
        try:
            scraper = CROUSScraper(
                self.settings['telegram_token'],
                self.settings['telegram_chat_id'],
                self.settings['city']
            )
            
            results = scraper.scan_for_city_accommodations(self.settings['max_pages'])
            
            if results:
                self.print_success(f"✓ {self.settings['city'].title()} found in {len(results)} VALID listing(s)!")
                message = scraper.format_telegram_message(results)
                if scraper.send_telegram_message(message):
                    self.print_success("Telegram notification sent!")
                else:
                    self.print_error("Failed to send Telegram message")
            else:
                self.print_info(f"No VALID {self.settings['city'].title()} listings found (false positives filtered out)")
        
        except Exception as e:
            self.print_error(f"Test check failed: {e}")

    def monitoring_loop(self):
        """Main monitoring loop"""
        interval_seconds = self.settings['interval_minutes'] * 60
        
        try:
            while self.monitoring:
                try:
                    next_check = datetime.now()
                    next_check = next_check.replace(second=0, microsecond=0)
                    
                    self.print_log("Starting scheduled check...")
                    
                    results = self.scraper.scan_for_city_accommodations(self.settings['max_pages'])
                    
                    if results:
                        message = self.scraper.format_telegram_message(results)
                        if self.scraper.send_telegram_message(message):
                            self.print_success(f"✓ {self.settings['city'].title()} found! Telegram notification sent.")
                        else:
                            self.print_warning(f"{self.settings['city'].title()} found but failed to send Telegram message")
                    else:
                        self.print_info(f"No valid {self.settings['city'].title()} listings (false positives filtered)")
                    
                    # Display next check time
                    next_time = datetime.now() + timedelta(minutes=self.settings['interval_minutes'])
                    self.print_info(f"Next check at: {next_time.strftime('%H:%M:%S')}")
                    
                    # Wait with periodic checks for stop signal
                    for remaining in range(int(interval_seconds), 0, -1):
                        if not self.monitoring:
                            break
                        time.sleep(1)
                
                except Exception as e:
                    self.print_error(f"Error during monitoring: {e}")
                    time.sleep(60)
        
        except KeyboardInterrupt:
            self.stop_monitoring()

    def start_monitoring(self):
        """Start the monitoring process"""
        if not self.validate_settings():
            self.print_warning("Please configure settings first (option 2)")
            return
        
        if self.monitoring:
            self.print_warning("Monitoring is already running!")
            return
        
        try:
            self.scraper = CROUSScraper(
                self.settings['telegram_token'],
                self.settings['telegram_chat_id'],
                self.settings['city']
            )
            
            self.monitoring = True
            
            startup_message = f"🤖 <b>CROUS {self.settings['city'].title()} Monitor Started!</b>\n\nMonitoring for {self.settings['city'].title()} with STRICT postal code validation.\nScanning up to {self.settings['max_pages']} pages every {self.settings['interval_minutes']} minutes.\n\n✓ Only 75xxx postal codes accepted for Paris"
            self.scraper.send_telegram_message(startup_message)
            
            self.print_success(f"Monitoring started for {self.settings['city'].title()}")
            self.print_info(f"Check interval: {self.settings['interval_minutes']} minutes")
            self.print_info(f"Max pages: {self.settings['max_pages']}")
            self.print_info("✓ STRICT postal code filter: Only 75xxx for Paris")
            self.print_info("Press Ctrl+C to stop monitoring\n")
            
            self.monitor_thread = threading.Thread(
                target=self.monitoring_loop,
                daemon=True
            )
            self.monitor_thread.start()
            
            # Keep main thread alive and handle Ctrl+C
            try:
                while self.monitoring:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop_monitoring()
        
        except Exception as e:
            self.print_error(f"Failed to start monitoring: {e}")

    def stop_monitoring(self):
        """Stop the monitoring process"""
        if not self.monitoring:
            self.print_warning("Monitoring is not running")
            return
        
        self.monitoring = False
        
        if self.scraper:
            stop_message = f"🛑 <b>CROUS {self.settings['city'].title()} Monitor Stopped</b>\n\nMonitoring has been stopped."
            self.scraper.send_telegram_message(stop_message)
        
        self.print_success("Monitoring stopped")

    def show_menu(self):
        """Display main menu"""
        print("\n📋 Main Menu\n" + "-"*60)
        print("1. Start Monitoring")
        print("2. Configure Settings")
        print("3. View Current Settings")
        print("4. Test Check (single scan)")
        print("5. Stop Monitoring")
        print("6. Exit")
        print("-"*60)

    def run(self):
        """Main application loop"""
        self.print_header()
        
        if os.path.exists(self.settings_file):
            self.print_success("Previous settings loaded")
        else:
            self.print_info("No previous settings found")
        
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
                    self.print_warning("Invalid choice. Please enter 1-6")
            
            except KeyboardInterrupt:
                print("\n")
                if self.monitoring:
                    self.stop_monitoring()
                print("\nGoodbye! 👋\n")
                sys.exit(0)
            except Exception as e:
                self.print_error(f"An error occurred: {e}")


if __name__ == "__main__":
    app = CROUSMonitorTerminal()
    app.run()
