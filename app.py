
import json
import requests
import threading
import time
import os
from flask import Flask, render_template, request, jsonify
from scanner import scan_network

app = Flask(__name__)

# Configuration
DATA_FILE = "miners.json"

# -- Persistence Layer --
def load_db():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return []

def save_db(miners):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(miners, f)
    except:
        pass

# In-Memory State
DB = {
    "miners": load_db(),
    "settings": {
        "coin": "BC2", 
        "subnet": "192.168.1.0/24",
        "currency": "USD"
    }
}

COINS = {
    "BC2": { "name": "Bitcoin 2", "api_url": "https://blockhunters.work/api/network" },
    "BTC": { "name": "Bitcoin", "api_url": None } 
}

MARKET_DATA = { "price": 0, "diff": 0, "net_hash": 0, "reward": 50, "rates": {"USD": 1.0} }

# -- Background Tasks --
def fetch_market_data():
    """Fetches crypto price, difficulty, and forex rates."""
    global MARKET_DATA
    while True:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            
            # Crypto Stats
            if DB['settings']['coin'] == 'BC2':
                url = COINS['BC2']['api_url']
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 200:
                    d = r.json()
                    raw_hash = float(d.get('network_hashrate', 0))
                    MARKET_DATA["price_usd"] = float(d.get('price_usd', 0))
                    MARKET_DATA["diff"] = float(d.get('difficulty', 0))
                    MARKET_DATA["net_hash"] = raw_hash * 1e9
                    MARKET_DATA["reward"] = float(d.get('reward_btc', 50))
            
            # Forex Rates
            try:
                fr = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
                if fr.status_code == 200:
                    MARKET_DATA["rates"] = fr.json().get('rates', {})
            except:
                pass

        except Exception as e:
            print(f"[System] Oracle Error: {e}")
        time.sleep(60)

def gentle_miner_poller():
    """Updates miner stats without overwhelming devices."""
    while True:
        for m in DB['miners']:
            try:
                r = requests.get(f"http://{m['ip']}/api/system/info", timeout=1.5)
                if r.status_code == 200:
                    d = r.json()
                    m['stats'] = {
                        'connected': True,
                        'hashrate_10m': d.get('hashRate_10m', d.get('hashRate', 0)),
                        'hashrate_raw': d.get('hashRate', 0),
                        'temp': d.get('temp', 0),
                        'vrTemp': d.get('vrTemp', 0),
                        'power': d.get('power', 0),
                        'voltage': d.get('coreVoltage', 0),
                        'frequency': d.get('frequency', 0),
                        'uptime': d.get('uptimeSeconds', d.get('uptime', 0)),
                        'bestDiff': d.get('bestDiff', 0),
                        'blocks': d.get('blocks', 0),
                        'stratumURL': d.get('stratumURL', ''),
                        'stratumUser': d.get('stratumUser', ''),
                        'version': d.get('version', 'unknown'),
                        'model': d.get('model', 'Bitaxe'),
                        'last_seen': time.time()
                    }
                else:
                    m['stats']['connected'] = False
            except: 
                if 'stats' not in m:
                    m['stats'] = {'connected': False}
                m['stats']['connected'] = False
            time.sleep(0.5) 
        time.sleep(20) 

# Start Threads
t1 = threading.Thread(target=fetch_market_data, daemon=True)
t1.start()
t2 = threading.Thread(target=gentle_miner_poller, daemon=True)
t2.start()

# -- Routes --
@app.route('/')
def index():
    return render_template('dashboard.html', coins=COINS, settings=DB['settings'])

@app.route('/api/miners', methods=['GET'])
def get_miners():
    results = []
    total_hr = 0
    total_pwr = 0
    global_best = 0
    total_blocks = 0
    best_miner = "-"
    
    for m in DB['miners']:
        if 'stats' not in m:
            m['stats'] = {'connected': False}
        s = m['stats']
        m['display_name'] = m.get('custom_name') or m.get('name') or m['ip']
        
        if s.get('connected'):
            total_hr += s.get('hashrate_10m', 0)
            total_pwr += s.get('power', 0)
            total_blocks += s.get('blocks', 0)
            if s.get('bestDiff', 0) > global_best:
                global_best = s.get('bestDiff')
                best_miner = m['display_name']
        results.append(m)
    
    curr = DB['settings'].get('currency', 'USD')
    rate = MARKET_DATA.get('rates', {}).get(curr, 1.0)
    display_price = MARKET_DATA["price_usd"] * rate
    db_size = os.path.getsize(DATA_FILE) if os.path.exists(DATA_FILE) else 0

    return jsonify({
        "miners": results, 
        "market": {
            "price": display_price,
            "currency": curr,
            "diff": MARKET_DATA["diff"],
            "net_hash": MARKET_DATA["net_hash"],
            "reward": MARKET_DATA["reward"]
        },
        "fleet": {
            "hash": total_hr, 
            "power": total_pwr, 
            "best_share": global_best, 
            "best_miner": best_miner,
            "blocks_found": total_blocks
        },
        "system": { "db_size_bytes": db_size, "uptime": "100%" }
    })

@app.route('/api/miners/pool', methods=['POST'])
def update_miner_pool():
    d = request.json
    if not d.get('ip'):
        return jsonify({"status": "error", "msg": "No IP"}), 400
    try:
        payload = {
            "stratumURL": d.get('url'),
            "stratumUser": d.get('user'),
            "stratumPass": d.get('pass')
        }
        # Apply config
        requests.patch(f"http://{d['ip']}/api/system", json=payload, timeout=5)
        # Restart required
        requests.post(f"http://{d['ip']}/api/system/restart", timeout=5)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "details": str(e)}), 500

@app.route('/api/miners/rename', methods=['POST'])
def rename_miner():
    data = request.json
    for m in DB['miners']:
        if m['ip'] == data.get('ip'):
            m['custom_name'] = data.get('name')
            save_db(DB['miners'])
            return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 404

@app.route('/api/scan', methods=['POST'])
def run_scan():
    subnet = request.json.get('subnet', '192.168.1.0/24')
    found = scan_network(subnet)
    existing_map = {m['ip']: m for m in DB['miners']}
    added = 0
    
    for d in found:
        ip = d['ip']
        if ip in existing_map:
            existing_map[ip]['name'] = d.get('name')
            existing_map[ip]['model'] = d.get('model')
        else:
            DB['miners'].append(d)
            added += 1
            
    save_db(DB['miners'])
    return jsonify({"status": "ok", "added": added, "found": found})

@app.route('/api/miners/delete', methods=['POST'])
def delete_miner():
    DB['miners'] = [m for m in DB['miners'] if m['ip'] != request.json.get('ip')]
    save_db(DB['miners'])
    return jsonify({"status": "ok"})

@app.route('/api/system/reset', methods=['POST'])
def reset_db():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    DB['miners'] = []
    return jsonify({"status": "ok"})

@app.route('/api/overclock', methods=['POST'])
def overclock():
    d = request.json
    if not d.get('ip'):
        return jsonify({"status": "error"}), 400
    
    try:
        payload = {"frequency": int(d['freq']), "coreVoltage": int(d['volt'])}
        
        # Attempt PATCH (Standard AxeOS)
        requests.patch(f"http://{d['ip']}/api/system", json=payload, timeout=5)
        return jsonify({"status": "ok"})
    except:
        # Fallback to POST (Legacy/NerdMiner)
        try:
            requests.post(f"http://{d['ip']}/api/system/update", json=payload, timeout=5)
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "details": str(e)}), 500

@app.route('/api/reboot', methods=['POST'])
def reboot():
    try:
        requests.post(f"http://{request.json['ip']}/api/system/reboot", timeout=3)
        return jsonify({"status": "ok"})
    except:
        return jsonify({"status": "error"}), 500

@app.route('/api/settings', methods=['POST'])
def update_settings():
    DB['settings'].update(request.json)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5055, debug=True)
