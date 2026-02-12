# OpenAxe: Bitaxe Fleet Manager

**OpenAxe** is a lightweight, self-hosted dashboard designed for monitoring and managing a fleet of Bitaxe (AxeOS) and NerdAxe devices.

## 🚀 Features
* **Network Scanner:** Discover Bitaxe devices on your LAN.
* **Fleet Statistics:** Aggregated hashrate, power, and block data.
* **Multi-Coin:** Support for **Bitcoin (BTC)** and **Bitcoin 2 (BC2)**.
* **🔔 Notifications:** Integrated **Ntfy.sh** alerts and **Nostr** Encrypted DMs for status changes.

## ☕ Support the Project
If you find this tool useful, consider supporting the developer:
* **⚡Lightning:** lightning@cfultz.com
* **₿TC:** bc1qg4qq5xmtk59tef5n729nn7v2y30sgkgkducwru
* **₿C2:** bc1qrkakhz9lr9jg6hzprfch83q9yk3fstnyre3a2m

---

## 🛠️ Installation
1. `git clone https://github.com/cfultz/openaxe.git`
2. `cd openaxe`
3. `docker-compose up -d --build`
4. Access at `http://<your-host-ip>:5055`

## 📡 Nostr Configuration
To receive encrypted notifications via Nostr:
1. **Create a Dedicated Bot Account:** Generate a *new, separate* Nostr keypair (nsec/npub) specifically for this application. **Do not use your main personal private key in the configuration.**
2. **Configure:** In the OpenAxe Settings, enter the **Bot's Private Key** (sender) and your **Personal Public Key** (recipient).
3. **Visibility:** Ensure your main account follows the bot account so that notifications appear in your main inbox (depending on your client's spam filters).

## ⚖️ License
This project is licensed under a **Modified MIT License**. 
Permission is hereby granted to use, copy, modify, and merge the software, provided that the **"Buy Me a Coffee" / Donation section** in the web interface and the README remain intact and visible. Removing or altering the developer's donation addresses is strictly prohibited.
