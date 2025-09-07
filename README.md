# 🏠 CROUS City Monitor

**A desktop application that monitors CROUS housing listings in France and instantly notifies you via Telegram.**  

It works **only** with the official CROUS website:  
🔗 [https://trouverunlogement.lescrous.fr/](https://trouverunlogement.lescrous.fr/)  

---

## ✨ Features

- 🎯 Monitors your **target city** on CROUS housing listings  
- 📱 **Telegram integration** for instant alerts  
- 💾 **Auto-save settings** (remembers your city, token, chat ID, and interval)  
- ▶️ **Start Monitoring** → begins checking at your chosen interval and sends a **Telegram message** confirming monitoring has started  
- ⏹ **Stop Monitoring** → ends checks and sends a **Telegram message** confirming monitoring has stopped (whether manually or due to an issue)  
- 🧪 **Test Check** → performs a one-time full scan and sends you the results immediately  
- 🔄 **Custom intervals** (supports decimals like `0.1` or `0.5` minutes for very frequent checks)  

---

## 👥 Who is it for?

- 🧑 Non-developers → Just run the ready-to-use app `CrousAlert.exe`  
- 👩‍💻 Developers → Explore or modify the source code in `main.py`    

---

## 📦 How to use (non-developers)

1. Download and run the provided **`CrousAlert.exe`**  
2. Enter your **Target City** (e.g. *Paris*)  
3. Enter your **Telegram Bot Token**  
   - Create a bot via [BotFather](https://t.me/BotFather)  
   - Keep your token safe — **do not share it with anyone**!  
4. Enter your **Telegram Chat ID**  
   - Go to [@userinfobot](https://t.me/userinfobot) on Telegram  
   - Send `/start` and copy your numeric **ID**  
5. Choose the **check interval** (in minutes — supports decimals like `0.5`)  
6. Click **▶ Start Monitoring**  

The app will send you a Telegram message when it starts, when it stops, and whenever your city is found on the CROUS site.  

---

## ⚠️ Troubleshooting

- ❌ **Settings not saving?**  
  Make sure the app has permission to write to the repository folder (check file permissions).  

- 🔑 **Never share your Telegram Bot Token!**  
  Anyone with it could control your bot. Keep it private.  

---

## 🛠 For Developers

If you’d like to explore or modify the app, use the `main.py` file.  
You’ll need the following Python libraries (install via `pip install`):  

- `tkinter` (usually preinstalled with Python)  
- `requests`  
- `beautifulsoup4`  
- `lxml` (recommended for parsing)  

---

## 🤝 Contributing & Contact

This project was made with ❤️ for students and anyone searching for CROUS housing.  
It’s open source, and contributions are welcome!  

If you have:  
- 🐞 Bugs to report  
- 💡 Ideas to share  
- ✨ New feature suggestions  

📩 Contact me at **daass.maram@gmail.com**  
💼 Or connect on [LinkedIn](https://www.linkedin.com/in/maram-daas/)  

---

## 📄 License

This project is licensed under the **MIT License** — you are free to use, modify, and share it.  

---

*P.S. If you ever find this useful, please keep me in your prayers ☁️*  

