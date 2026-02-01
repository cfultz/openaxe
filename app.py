import json
import requests
import threading
import time
import os
from flask import Flask, render_template, request, jsonify
from scanner import scan_network

app = Flask(__name__)

DATA_FILE = "miners.json"
UPDATE_EVENT = threading.Event()

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

DB = {
    "miners": load_db(),
    "settings": {
        "coin": "BC2", 
        "subnet": "192.168.1.0/24",
        "currency": "USD",
        "ntfy_server": "https://ntfy.sh",
        "ntfy_topic": f"openaxe_monitor_{os.urandom(4).hex()}",
        "ntfy_timeout": 30,
        "notify_offline": True,
        "notify_blocks": True,
        "notify_tuning": True
    }
}

COINS = {
    "BC2": { 
        "name": "Bitcoin 2", "api_id": "bitcoin-2", "type": "blockhunters", 
        "api_url": "https://blockhunters.work/api/network" 
    },
    "BTC": { 
        "name": "Bitcoin", "api_id": "bitcoin", "type": "mempool", 
        "api_url": "https://mempool.space/api" 
    },
    "BCH": { 
        "name": "Bitcoin Cash", "api_id": "bitcoin-cash", "type": "blockchair", 
        "api_url": "https://api.blockchair.com/bitcoin-cash/stats" 
    },
    "DGB": { 
        "name": "DigiByte", "api_id": "digibyte", "type": "chainz", 
        "api_url": "https://chainz.cryptoid.info/dgb/api.dws" 
    },
    "XEC": {
        "name": "eCash", "api_id": "ecash", "type": "blockchair",
        "api_url": "https://api.blockchair.com/ecash/stats"
    }
}

MARKET_DATA = { "price": 0, "diff": 0, "net_hash": 0, "reward": 50, "rates": {"USD": 1.0} }
OFFLINE_TRACKER = {}
LAST_BLOCK_COUNT = 0

def send_ntfy(message, title="OpenAxe Alert", tags="cpu"):
    topic = DB['settings'].get('ntfy_topic', '').strip()
    server = DB['settings'].get('ntfy_server', 'https://ntfy.sh').strip().rstrip('/')
    if not topic:
        return
    try:
        requests.post(f"{server}/{topic}", 
            data=message.encode('utf-8'),
            headers={
                "Title": title.encode('utf-8') if isinstance(title, str) else title, 
                "Tags": tags
            }, 
            timeout=5)
    except Exception as e:
        print(f"[System] Ntfy Error: {e}")

def fetch_market_data():
    global MARKET_DATA
    while True:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            coin_code = DB['settings'].get('coin', 'BC2')
            coin_config = COINS.get(coin_code, COINS['BC2'])
            
            try:
                cg_id = coin_config.get('api_id')
                if cg_id:
                    p_r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=usd", timeout=5)
                    if p_r.status_code == 200:
                        MARKET_DATA["price_usd"] = float(p_r.json()[cg_id]['usd'])
            except:
                pass 

            if coin_config['type'] == 'blockhunters':
                r = requests.get(coin_config['api_url'], headers=headers, timeout=10)
                if r.status_code == 200:
                    d = r.json()
                    MARKET_DATA["diff"] = float(d.get('difficulty', 0))
                    MARKET_DATA["net_hash"] = float(d.get('network_hashrate', 0)) * 1e9
                    MARKET_DATA["reward"] = float(d.get('reward_btc', 50))
                    MARKET_DATA["price_usd"] = float(d.get('price_usd', 0))

            elif coin_config['type'] == 'mempool':
                r_diff = requests.get(f"{coin_config['api_url']}/v1/difficulty-adjustment", timeout=10)
                r_hash = requests.get(f"{coin_config['api_url']}/v1/mining/hashrate/3d", timeout=10)
                
                if r_diff.status_code == 200:
                    MARKET_DATA["diff"] = float(r_diff.json().get('difficulty', 0))
                
                if r_hash.status_code == 200:
                    data = r_hash.json()
                    if isinstance(data, list) and len(data) > 0:
                        MARKET_DATA["net_hash"] = float(data[-1]['currentHashrate'])
                
                if coin_code == 'BTC': MARKET_DATA["reward"] = 3.125
                else: MARKET_DATA["reward"] = 0

            elif coin_config['type'] == 'blockchair':
                r = requests.get(coin_config['api_url'], timeout=10)
                if r.status_code == 200:
                    d = r.json()['data']
                    MARKET_DATA["diff"] = float(d['difficulty'])
                    MARKET_DATA["net_hash"] = float(d['hashrate_24h'])
                    if coin_code == 'BCH': MARKET_DATA["reward"] = 3.125
                    elif coin_code == 'XEC': MARKET_DATA["reward"] = 3125000.0

            elif coin_config['type'] == 'chainz':
                r_diff = requests.get(f"{coin_config['api_url']}?q=getdifficulty", timeout=10)
                r_hash = requests.get(f"{coin_config['api_url']}?q=hashrate", timeout=10)
                
                if r_diff.status_code == 200:
                    MARKET_DATA["diff"] = float(r_diff.text)
                
                if r_hash.status_code == 200:
                    MARKET_DATA["net_hash"] = float(r_hash.text) * 1e9
                
                if coin_code == 'DGB': MARKET_DATA["reward"] = 630.0 

            try:
                fr = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5)
                if fr.status_code == 200:
                    MARKET_DATA["rates"] = fr.json().get('rates', {})
            except:
                pass

        except Exception as e:
            print(f"[System] Oracle Error: {e}")
        
        UPDATE_EVENT.wait(60)
        UPDATE_EVENT.clear()

def gentle_miner_poller():
    global LAST_BLOCK_COUNT
    while True:
        current_total_blocks = 0
        for m in DB['miners']:
            ip = m['ip']
            try:
                r = requests.get(f"http://{ip}/api/system/info", timeout=1.5)
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
                        'shares': d.get('sharesAccepted', 0),
                        'stratumURL': d.get('stratumURL', ''),
                        'stratumUser': d.get('stratumUser', ''),
                        'version': d.get('version', 'unknown'),
                        'model': d.get('model', 'Bitaxe'),
                        'last_seen': time.time()
                    }
                    current_total_blocks += m['stats']['blocks']
                    if ip in OFFLINE_TRACKER:
                        del OFFLINE_TRACKER[ip]
                else:
                    raise Exception("Status not 200")
            except:
                if 'stats' not in m:
                    m['stats'] = {'connected': False}
                m['stats']['connected'] = False
                now = time.time()
                if ip not in OFFLINE_TRACKER:
                    OFFLINE_TRACKER[ip] = now
                else:
                    downtime = now - OFFLINE_TRACKER[ip]
                    threshold = DB['settings'].get('ntfy_timeout', 30)
                    if threshold <= downtime < threshold + 25:
                        if DB['settings'].get('notify_offline'):
                            name = m.get('custom_name') or m.get('name') or ip
                            send_ntfy(f"Miner {name} offline for {int(downtime)}s", "MINER DOWN", "warning,skull")
                        OFFLINE_TRACKER[ip] = now + 86400
            time.sleep(0.5)

        if DB['settings'].get('notify_blocks') and LAST_BLOCK_COUNT > 0 and current_total_blocks > LAST_BLOCK_COUNT:
            send_ntfy(f"Fleet found a new block! Total: {current_total_blocks}", "BLOCK FOUND!", "moneybag,tada")
        LAST_BLOCK_COUNT = current_total_blocks
        time.sleep(20)

t1 = threading.Thread(target=fetch_market_data, daemon=True)
t1.start()
t2 = threading.Thread(target=gentle_miner_poller, daemon=True)
t2.start()

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
    total_shares = 0
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
            total_shares += s.get('shares', 0)
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
        "settings": {"coin": DB['settings'].get('coin', 'BC2')},
        "market": {"price": display_price, "currency": curr, "diff": MARKET_DATA["diff"], "net_hash": MARKET_DATA["net_hash"], "reward": MARKET_DATA["reward"]},
        "fleet": {"hash": total_hr, "power": total_pwr, "best_share": global_best, "best_miner": best_miner, "blocks_found": total_blocks, "total_shares": total_shares},
        "system": { "db_size_bytes": db_size, "uptime": "100%" }
    })

@app.route('/api/miners/pool', methods=['POST'])
def update_miner_pool():
    d = request.json
    if not d.get('ip'):
        return jsonify({"status": "error", "msg": "No IP"}), 400
    try:
        payload = {"stratumURL": d.get('url'), "stratumUser": d.get('user'), "stratumPass": d.get('pass')}
        requests.patch(f"http://{d['ip']}/api/system", json=payload, timeout=5)
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
    if not d.get('ip'): return jsonify({"status": "error"}), 400
    try:
        payload = {"frequency": int(d['freq']), "coreVoltage": int(d['volt'])}
        requests.patch(f"http://{d['ip']}/api/system", json=payload, timeout=5)
        if DB['settings'].get('notify_tuning'):
            send_ntfy(f"Tuning applied to {d['ip']}: {d['freq']}MHz / {d['volt']}mV", "TUNING SUCCESS", "zap")
        return jsonify({"status": "ok"})
    except:
        try:
            requests.post(f"http://{d['ip']}/api/system/update", json=payload, timeout=5)
            if DB['settings'].get('notify_tuning'):
                send_ntfy(f"Tuning (Legacy) applied to {d['ip']}", "TUNING SUCCESS", "zap")
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
    UPDATE_EVENT.set()
    return jsonify({"status": "ok"})

@app.route('/api/test_ntfy', methods=['POST'])
def test_ntfy():
    topic = DB['settings'].get('ntfy_topic', '').strip()
    server = DB['settings'].get('ntfy_server', 'https://ntfy.sh').strip().rstrip('/')
    
    if not topic:
        return jsonify({"status": "error", "msg": "Topic is empty. Please save settings first."}), 400

    try:
        r = requests.post(f"{server}/{topic}", 
            data="Testing OpenAxe notification system. If you see this, it works!".encode('utf-8'),
            headers={"Title": "TEST SUCCESS", "Tags": "test_tube,white_check_mark"}, 
            timeout=5)
        
        if r.status_code == 200:
            return jsonify({"status": "ok", "msg": f"Sent! Server responded: {r.status_code}"})
        else:
            return jsonify({"status": "error", "msg": f"Server Error {r.status_code}: {r.text}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "msg": f"Connection Failed: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5055, debug=True)
