import json
import requests
import threading
import time
import os
import queue
from flask import Flask, render_template, request, jsonify
from scanner import scan_network
from pynostr.key import PrivateKey
from pynostr.relay_manager import RelayManager
from pynostr.encrypted_dm import EncryptedDirectMessage

app = Flask(__name__)

DATA_FILE = "miners.json"
SETTINGS_FILE = "settings.json"
UPDATE_EVENT = threading.Event()
NOSTR_QUEUE = queue.Queue()

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

def load_settings():
    defaults = {
        "coin": "BC2", 
        "subnet": "192.168.1.0/24",
        "currency": "USD",
        "ntfy_server": "https://ntfy.sh",
        "ntfy_topic": f"openaxe_monitor_{os.urandom(4).hex()}",
        "ntfy_timeout": 30,
        "notify_offline": True,
        "notify_blocks": True,
        "notify_tuning": True,
        "nostr_privkey": "",
        "nostr_recipient_pubkey": "",
        "nostr_relays": ["wss://nostr.mom/", "wss://nostrelites.org/", "wss://relay.damus.io/", "wss://wot.nostr.net/"]
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                defaults.update(json.load(f))
        except:
            pass
    return defaults

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f)
    except:
        pass

DB = {
    "miners": load_db(),
    "settings": load_settings()
}

COINS = {
    "BC2": { 
        "name": "Bitcoin 2", "api_id": "bitcoin-2", "type": "blockhunters", 
        "api_url": "https://blockhunters.work/api/network" 
    },
    "BTC": { 
        "name": "Bitcoin", "api_id": "bitcoin", "type": "mempool", 
        "api_url": "https://mempool.space/api" 
    }
}

MARKET_DATA = { "price_usd": 0, "diff": 0, "net_hash": 0, "reward": 0, "rates": {"USD": 1.0} }
OFFLINE_TRACKER = {}
LAST_BLOCK_COUNT = 0

def nostr_queue_worker():
    while True:
        try:
            item = NOSTR_QUEUE.get()
            if item is None: break
            message, priv, pub, relays = item
            try:
                pk = PrivateKey.from_hex(priv)
                dm = EncryptedDirectMessage()
                dm.encrypt(pk.hex(), recipient_pubkey=pub, cleartext_content=message)
                event = dm.to_event()
                event.pubkey = pk.public_key.hex()
                event.add_tag("p", pub)
                event.sign(pk.hex())
                rm = RelayManager(timeout=6)
                for r in relays: rm.add_relay(r.strip())
                time.sleep(1.5)
                rm.publish_event(event)
                rm.run_sync()
                time.sleep(2)
                rm.close_connections()
            except Exception as e: print(f"Nostr Error: {e}")
            NOSTR_QUEUE.task_done()
        except: time.sleep(1)

threading.Thread(target=nostr_queue_worker, daemon=True).start()

def send_ntfy(message, title="OpenAxe Alert", tags="cpu"):
    topic = DB['settings'].get('ntfy_topic', '').strip()
    server = DB['settings'].get('ntfy_server', 'https://ntfy.sh').strip().rstrip('/')
    if not topic:
        return
    try:
        requests.post(f"{server}/{topic}", 
            data=message.encode('utf-8'),
            headers={"Title": title.encode('utf-8'), "Tags": tags}, 
            timeout=5)
    except:
        pass

def send_nostr(message):
    p = DB['settings'].get('nostr_privkey', '').strip()
    r_pub = DB['settings'].get('nostr_recipient_pubkey', '').strip()
    relays = DB['settings'].get('nostr_relays', [])
    if p and r_pub: NOSTR_QUEUE.put((message, p, r_pub, relays))

def fetch_market_data():
    global MARKET_DATA
    while True:
        try:
            coin_code = DB['settings'].get('coin', 'BC2')
            coin_config = COINS.get(coin_code, COINS['BC2'])
            
            try:
                cg_id = coin_config.get('api_id')
                p_r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=usd", timeout=5)
                if p_r.status_code == 200:
                    MARKET_DATA["price_usd"] = float(p_r.json()[cg_id]['usd'])
            except:
                pass 

            if coin_config['type'] == 'blockhunters':
                r = requests.get(coin_config['api_url'], timeout=10)
                if r.status_code == 200:
                    d = r.json()
                    MARKET_DATA["diff"] = float(d.get('difficulty', 0))
                    MARKET_DATA["net_hash"] = float(d.get('network_hashrate', 0)) * 1e9
                    MARKET_DATA["reward"] = float(d.get('reward_btc', 50))

            elif coin_config['type'] == 'mempool':
                r_stats = requests.get(f"{coin_config['api_url']}/v1/mining/hashrate/3d", timeout=10)
                if r_stats.status_code == 200:
                    data = r_stats.json()
                    MARKET_DATA["diff"] = float(data.get('currentDifficulty', 0))
                    MARKET_DATA["net_hash"] = float(data.get('currentHashrate', 0))
                
                MARKET_DATA["reward"] = 3.125 if coin_code == 'BTC' else 0

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
                    raise Exception("Offline")
            except:
                if 'stats' not in m: m['stats'] = {'connected': False}
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
                            msg = f"Miner {name} offline for {int(downtime)}s"
                            send_ntfy(msg, "MINER DOWN", "warning,skull")
                            send_nostr(msg)
                        OFFLINE_TRACKER[ip] = now + 86400
            time.sleep(0.5)
        if DB['settings'].get('notify_blocks') and LAST_BLOCK_COUNT > 0 and current_total_blocks > LAST_BLOCK_COUNT:
            msg = f"Fleet found a new block! Total: {current_total_blocks}"
            send_ntfy(msg, "BLOCK FOUND!", "moneybag,tada")
            send_nostr(msg)
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
        if 'stats' not in m: m['stats'] = {'connected': False}
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
    display_price = MARKET_DATA.get("price_usd", 0) * rate
    db_size = os.path.getsize(DATA_FILE) if os.path.exists(DATA_FILE) else 0
    return jsonify({
        "miners": results, 
        "settings": DB['settings'],
        "market": {"price": display_price, "currency": curr, "diff": MARKET_DATA["diff"], "net_hash": MARKET_DATA["net_hash"], "reward": MARKET_DATA["reward"]},
        "fleet": {"hash": total_hr, "power": total_pwr, "best_share": global_best, "best_miner": best_miner, "blocks_found": total_blocks, "total_shares": total_shares},
        "system": { "db_size_bytes": db_size, "uptime": "100%" }
    })

@app.route('/api/miners/pool', methods=['POST'])
def update_miner_pool():
    d = request.json
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
    if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
    DB['miners'] = []
    return jsonify({"status": "ok"})

@app.route('/api/overclock', methods=['POST'])
def overclock():
    d = request.json
    try:
        payload = {"frequency": int(d['freq']), "coreVoltage": int(d['volt'])}
        requests.patch(f"http://{d['ip']}/api/system", json=payload, timeout=5)
        if DB['settings'].get('notify_tuning'):
            msg = f"Tuning applied to {d['ip']}: {d['freq']}MHz / {d['volt']}mV"
            send_ntfy(msg, "TUNING SUCCESS", "zap")
            send_nostr(msg)
        return jsonify({"status": "ok"})
    except:
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
    save_settings(DB['settings'])
    UPDATE_EVENT.set()
    return jsonify({"status": "ok"})

@app.route('/api/test_ntfy', methods=['POST'])
def test_ntfy():
    topic = DB['settings'].get('ntfy_topic', '').strip()
    server = DB['settings'].get('ntfy_server', 'https://ntfy.sh').strip().rstrip('/')
    if not topic: return jsonify({"status": "error", "msg": "Empty topic"}), 400
    try:
        r = requests.post(f"{server}/{topic}", 
            data="Testing notification system.".encode('utf-8'),
            headers={"Title": "TEST SUCCESS", "Tags": "test_tube,white_check_mark"}, timeout=5)
        return jsonify({"status": "ok"}) if r.status_code == 200 else jsonify({"status": "error"}), 500
    except:
        return jsonify({"status": "error"}), 500

@app.route('/api/test_nostr', methods=['POST'])
def test_nostr():
    try:
        send_nostr("Testing Nostr notification system. If you see this, it works!")
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "msg": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5055, debug=True)
