# 🏠 CROUS City Monitor

A lightweight desktop Python application that monitors CROUS housing listings across France and sends instant Telegram notifications when new accommodations become available.

**Official CROUS website:** https://trouverunlogement.lescrous.fr/

---

## ✨ Features

- 🔍 **City-based monitoring** – Track listings for specific cities
- 📄 **Pagination support** – Scan multiple pages for comprehensive coverage
- 📱 **Telegram notifications** – Get instant alerts when monitoring starts, stops, or finds results
- 💾 **Auto-saved settings** – Your configuration persists between sessions
- ⚡ **One-time test check** – Verify your setup before starting continuous monitoring
- ⏱️ **Custom check intervals** – Set decimal intervals (e.g., 0.5 minutes) for flexible scheduling

---

## 📦 How to Use

### Requirements
- **Python 3.12** (required version)

### Installation & Setup

1. **Download** the `main.py` file from this repository

2. **Install dependencies:**
   ```bash
   pip install requests beautifulsoup4 lxml
   ```

3. **Set up Telegram Bot:**
   
   **a) Create your bot and get the token:**
   - Open Telegram and search for [@BotFather](https://t.me/botfather)
   - Send `/newbot` and follow the instructions
   - Choose a name and username for your bot
   - **Copy the bot token** you receive (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
   
   **b) Get your Chat ID:**
   - Search for [@userinfobot](https://t.me/userinfobot) on Telegram
   - Start a conversation with it
   - **Copy your Chat ID** (a numeric value)

4. **Run the application:**
   ```bash
   python3.12 main.py
   ```

5. **Configure on first launch:**
   - Enter your Telegram bot token (from BotFather)
   - Provide your Telegram chat ID (from userinfobot)
   - Set your preferred city and monitoring interval

---

## 🛠️ Developer Notes

- This repository contains only the Python script
- The app is buildable into an executable, but no build files or instructions are currently provided
- Feedback, criticism, and contributions are welcome!

---

## ⚠️ Usage Notes

- This tool scrapes data from https://trouverunlogement.lescrous.fr/
- **Use responsibly** – Avoid aggressive check intervals that could overload the server
- **Never share your Telegram bot token** publicly or commit it to version control
- Respect the CROUS website's terms of service

---

## 🤝 Contributing & Contact

This project was made with ❤️ for students and anyone searching for CROUS housing.  
It's open source, and contributions are welcome!

If you have:
- 🐞 Bugs to report  
- 💡 Ideas to share  
- ✨ New feature suggestions  

📩 **Contact me at:** daass.maram@gmail.com  
💼 **Connect on LinkedIn:** [Maram Daas](https://www.linkedin.com/in/maram-daas/)

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) — you are free to use, modify, and share it.
