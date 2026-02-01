# OpenAxe: Bitaxe Fleet Manager

**OpenAxe** is a lightweight, self-hosted dashboard designed for monitoring and managing a fleet of Bitaxe (AxeOS) and NerdMiner devices. It provides real-time hashrate aggregation, market data integration, and batch configuration tools.

## 🚀 Features

* **Network Scanner:** Automatically discover Bitaxe devices on your LAN.
* **Fleet Statistics:** Real-time aggregation of hashrate, power consumption, total blocks found, and shares accepted.
* **Individual Miner Control:** Rename devices, update stratum settings, and manage overclocking (Frequency/Voltage) directly from the dashboard.
* **Multi-Coin Market Insights:** Live price and network difficulty tracking for **Bitcoin (BTC)**, **Bitcoin Cash (BCH)**, **DigiByte (DGB)**, **eCash (XEC)**, and **Bitcoin 2 (BC2)**. Data sourced via Mempool, Blockchair, Chainz, and Blockhunters.
* **🔔 Notification Engine:** Integrated **Ntfy.sh** alerts for miner offline events, block discovery, and successful tuning adjustments.
* **Persistence:** Miner configurations are saved to a local JSON database, ensuring your fleet remains organized after restarts.

## ⌛ Coming Soon
* **Dual Pool Settings for NerdAxe Devices:** Add the ability to set your failover or dual pool settings in the web interface
* **Make a change? Do a Pull Request:** Add something to the web app? Submit a pull request!

---

## 🛠️  Installation & Setup

### Prerequisites
* Docker and Docker Compose
* Linux Host (Required for **Host Networking** to allow LAN scanning)

### Quick Start
1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/cfultz/openaxe.git](https://github.com/cfultz/openaxe.git)
    cd openaxe
    ```

2.  **Build and launch with Docker Compose:**
    ```bash
    docker-compose up -d --build
    ```

3.  **Access the Dashboard:**
    Open your browser and navigate to `http://<your-host-ip>:5055`

---

## 🐳 Docker Configuration

OpenAxe utilizes **Host Networking** mode. This allows the internal `scanner.py` to communicate directly with your local subnet to find your miners.

> **Note:** Port mapping (`-p 5055:5000`) is disabled in host mode. The application binds directly to port **5055** as defined in `app.py`.

### Volume Persistence
Persist the app directory so settings aren't lost like custom miner names, changes to the app, etc.
```yaml
      - ./:/app

```

## 📂 Project Structure

The project follows a standard Flask application layout optimized for Docker containerization.

```text
openaxe/
├── app.py              # Main Flask server & background worker threads
├── scanner.py          # Network scanning logic (ARP/ICMP/HTTP)
├── miners.json         # Local JSON database for persistent miner data
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container build instructions
├── docker-compose.yml  # Docker service orchestration
├── static/             # Static assets
│   └── js/
│       └── dashboard.js # Frontend API polling and UI logic
└── templates/          # HTML templates
    └── dashboard.html  # Main dashboard interface

```

---

### API Reference

## 🔧 API Endpoints

All endpoints return JSON responses.

### Miner Management

| Endpoint | Method | Payload | Description |
| --- | --- | --- | --- |
| `/api/miners` | GET | None | Returns aggregated fleet stats, market data, and individual miner statuses. |
| `/api/scan` | POST | `{"subnet": "192.168.1.0/24"}` | Scans the specified subnet for Bitaxe/AxeOS devices. |
| `/api/miners/rename` | POST | `{"ip": "192.168.1.50", "name": "Neo"}` | Updates the local display name for a miner. |
| `/api/miners/delete` | POST | `{"ip": "192.168.1.50"}` | Removes a miner from the local database. |

### Device Control

| Endpoint | Method | Payload | Description |
| --- | --- | --- | --- |
| `/api/miners/pool` | POST | `{"ip": "...", "url": "...", "user": "..."}` | Updates stratum settings and restarts the device. |
| `/api/overclock` | POST | `{"ip": "...", "freq": 500, "volt": 1100}` | Adjusts frequency and voltage via AxeOS API. |
| `/api/reboot` | POST | `{"ip": "192.168.1.50"}` | Sends a hardware reboot command to the miner. |

### System & Notifications

| Endpoint | Method | Payload | Description |
| --- | --- | --- | --- |
| `/api/settings` | POST | `{"coin": "BTC", "currency": "USD", "ntfy_server": "...", "ntfy_topic": "..."}` | Updates global dashboard preferences and notification settings. |
| `/api/test_ntfy` | POST | None | Sends a test alert to the configured Ntfy server/topic. |
| `/api/system/reset` | POST | None | Clears all miners from `miners.json`. |
