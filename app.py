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
NOSTR_QUEUE = queue.Queue()

def load_db():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f: return json.load(f)
        except: pass
    return []

def save_db(miners):
    try:
        with open(DATA_FILE, 'w') as f: json.dump(miners, f)
    except: pass

def load_settings():
    defaults = {
        "coin": "BC2", 
        "subnet": "192.168.1.0/24", 
        "currency": "USD",
        "kwh_price": 0.12, 
        "ntfy_server": "https://ntfy.sh", 
        "ntfy_topic": f"openaxe_{os.urandom(4).hex()}", 
        "ntfy_timeout": 30,
        "notify_offline": True, "notify_blocks": True, "notify_tuning": True,
        "nostr_privkey": "", "nostr_recipient_pubkey": "", 
        "nostr_relays": ["wss://nostr.mom/", "wss://nostrelites.org/", "wss://relay.damus.io/", "wss://wot.nostr.net/"]
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f: defaults.update(json.load(f))
        except: pass
    return defaults

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w') as f: json.dump(settings, f)
    except: pass

DB = {"miners": load_db(), "settings": load_settings()}

COINS = {
    "BC2": { "name": "Bitcoin 2", "api_id": "bitcoin-2", "type": "blockhunters", "api_url": "https://blockhunters.work/api/network" },
    "BTC": { "name": "Bitcoin", "api_id": "bitcoin", "type": "mempool", "api_url": "https://mempool.space/api" },
    "BCH": { "name": "Bitcoin Cash", "api_id": "bitcoin-cash", "type": "blockchair", "api_url": "https://api.blockchair.com/bitcoin-cash/stats" }
}

MARKET_DATA = { "price_usd": 0, "diff": 0, "net_hash": 0, "reward": 0, "rates": {"USD": 1.0} }
OFFLINE_TRACKER, LAST_BLOCK_COUNT = {}, 0

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
    t, s = DB['settings'].get('ntfy_topic', ''), DB['settings'].get('ntfy_server', 'https://ntfy.sh').rstrip('/')
    if t:
        try: requests.post(f"{s}/{t}", data=message.encode('utf-8'), headers={"Title": title.encode('utf-8'), "Tags": tags}, timeout=5)
        except: pass

def send_nostr(message):
    p, r_pub, relays = DB['settings'].get('nostr_privkey', '').strip(), DB['settings'].get('nostr_recipient_pubkey', '').strip(), DB['settings'].get('nostr_relays', [])
    if p and r_pub: NOSTR_QUEUE.put((message, p, r_pub, relays))

def fetch_market_data():
    global MARKET_DATA
    while True:
        try:
            coin, cfg = DB['settings'].get('coin', 'BC2'), COINS.get(DB['settings'].get('coin', 'BC2'), COINS['BC2'])
            try:
                cg = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={cfg['api_id']}&vs_currencies=usd", timeout=5).json()
                MARKET_DATA["price_usd"] = float(cg[cfg['api_id']]['usd'])
            except: pass 
            
            if cfg['type'] == 'blockhunters':
                r = requests.get(cfg['api_url'], timeout=10).json()
                MARKET_DATA["diff"], MARKET_DATA["net_hash"], MARKET_DATA["reward"] = float(r.get('difficulty', 0)), float(r.get('network_hashrate', 0)) * 1e9, float(r.get('reward_btc', 50))
            elif cfg['type'] == 'mempool':
                r = requests.get(f"{cfg['api_url']}/v1/mining/hashrate/3d", timeout=10).json()
                MARKET_DATA["diff"], MARKET_DATA["net_hash"], MARKET_DATA["reward"] = float(r.get('currentDifficulty', 0)), float(r.get('currentHashrate', 0)), 3.125
            elif cfg['type'] == 'blockchair':
                r = requests.get(cfg['api_url'], timeout=10).json()
                data = r.get('data', {})
                MARKET_DATA["diff"], MARKET_DATA["net_hash"], MARKET_DATA["reward"] = float(data.get('difficulty', 0)), float(data.get('hashrate_24h', 0)), 3.125

            try: MARKET_DATA["rates"] = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5).json().get('rates', {})
            except: pass
        except: pass
        time.sleep(60)

def gentle_miner_poller():
    global LAST_BLOCK_COUNT
    while True:
        blocks = 0
        for m in DB['miners']:
            ip = m['ip']
            try:
                r = requests.get(f"http://{ip}/api/system/info", timeout=1.5).json()
                m['stats'] = {'connected': True, 'hashrate_10m': r.get('hashRate_10m', 0), 'temp': r.get('temp', 0), 'power': r.get('power', 0), 'voltage': r.get('coreVoltage', 0), 'frequency': r.get('frequency', 0), 'uptime': r.get('uptimeSeconds', 0), 'bestDiff': r.get('bestDiff', 0), 'blocks': r.get('blocks', 0), 'shares': r.get('sharesAccepted', 0), 'stratumURL': r.get('stratumURL', ''), 'stratumUser': r.get('stratumUser', '')}
                blocks += m['stats']['blocks']
                if ip in OFFLINE_TRACKER: del OFFLINE_TRACKER[ip]
            except:
                if 'stats' not in m: m['stats'] = {'connected': False}
                m['stats']['connected'] = False
                now = time.time()
                if ip not in OFFLINE_TRACKER: OFFLINE_TRACKER[ip] = now
                else:
                    if DB['settings'].get('notify_offline') and (now - OFFLINE_TRACKER[ip] >= DB['settings'].get('ntfy_timeout', 30)) and (now - OFFLINE_TRACKER[ip] < DB['settings'].get('ntfy_timeout', 30) + 25):
                        msg = f"Miner {m.get('custom_name') or ip} offline"
                        send_ntfy(msg, "MINER DOWN", "warning,skull"); send_nostr(msg)
                        OFFLINE_TRACKER[ip] = now + 86400
        if DB['settings'].get('notify_blocks') and LAST_BLOCK_COUNT > 0 and blocks > LAST_BLOCK_COUNT:
            msg = f"Fleet found block! Total: {blocks}"
            send_ntfy(msg, "BLOCK FOUND!", "moneybag"); send_nostr(msg)
        LAST_BLOCK_COUNT = blocks
        time.sleep(15)

threading.Thread(target=fetch_market_data, daemon=True).start()
threading.Thread(target=gentle_miner_poller, daemon=True).start()

@app.route('/')
def index(): return render_template('dashboard.html', coins=COINS, settings=DB['settings'])

@app.route('/api/miners')
def get_miners():
    thr = tpwr = gb = tb = ts = 0; best = "-"
    for m in DB['miners']:
        s = m.get('stats', {'connected': False})
        if s.get('connected'):
            thr += s.get('hashrate_10m', 0); tpwr += s.get('power', 0); tb += s.get('blocks', 0); ts += s.get('shares', 0)
            if s.get('bestDiff', 0) > gb: gb = s.get('bestDiff'); best = m.get('custom_name') or m['ip']
    curr = DB['settings'].get('currency', 'USD')
    dp = MARKET_DATA.get("price_usd", 0) * MARKET_DATA.get('rates', {}).get(curr, 1.0)
    return jsonify({
        "miners": DB['miners'], "settings": DB['settings'], 
        "market": {"price": dp, "currency": curr, "diff": MARKET_DATA["diff"], "net_hash": MARKET_DATA["net_hash"], "reward": MARKET_DATA["reward"]}, 
        "fleet": {"hash": thr, "power": tpwr, "best_share": gb, "best_miner": best, "blocks_found": tb, "total_shares": ts}, 
        "system": {"db_size_bytes": os.path.getsize(DATA_FILE) if os.path.exists(DATA_FILE) else 0}
    })

@app.route('/api/miners/pool/all', methods=['POST'])
def update_pool_all():
    d = request.json
    p = {
        "stratumURL": d.get('url'), "stratumUser": d.get('user'), "stratumPass": d.get('pass'),
        "fallbackStratumURL": d.get('fallbackUrl'), "fallbackStratumUser": d.get('fallbackUser'), "fallbackStratumPass": d.get('fallbackPass')
    }
    c = 0
    for m in DB['miners']:
        try:
            requests.patch(f"http://{m['ip']}/api/system", json=p, timeout=2)
            requests.post(f"http://{m['ip']}/api/system/restart", timeout=2)
            c += 1
        except: pass
    return jsonify({"status": "ok", "updated": c})

@app.route('/api/miners/pool', methods=['POST'])
def update_pool():
    d = request.json
    try:
        p = {
            "stratumURL": d.get('url'), "stratumUser": d.get('user'), "stratumPass": d.get('pass'),
            "fallbackStratumURL": d.get('fallbackUrl'), "fallbackStratumUser": d.get('fallbackUser'), "fallbackStratumPass": d.get('fallbackPass')
        }
        requests.patch(f"http://{d['ip']}/api/system", json=p, timeout=5)
        requests.post(f"http://{d['ip']}/api/system/restart", timeout=5)
        return jsonify({"status": "ok"})
    except: return jsonify({"status": "error"}), 500

@app.route('/api/miners/rename', methods=['POST'])
def rename_miner():
    d = request.json
    for m in DB['miners']:
        if m['ip'] == d.get('ip'):
            m['custom_name'] = d.get('name'); save_db(DB['miners'])
            return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 404

@app.route('/api/scan', methods=['POST'])
def run_scan():
    found = scan_network(request.json.get('subnet', '192.168.1.0/24'))
    ips = {m['ip'] for m in DB['miners']}
    for d in found:
        if d['ip'] not in ips: DB['miners'].append(d)
    save_db(DB['miners']); return jsonify({"status": "ok", "found": found})

@app.route('/api/miners/delete', methods=['POST'])
def delete_miner():
    DB['miners'] = [m for m in DB['miners'] if m['ip'] != request.json.get('ip')]
    save_db(DB['miners']); return jsonify({"status": "ok"})

@app.route('/api/overclock', methods=['POST'])
def overclock():
    d = request.json
    try:
        p = {"frequency": int(d['freq']), "coreVoltage": int(d['volt'])}
        requests.patch(f"http://{d['ip']}/api/system", json=p, timeout=5)
        if DB['settings'].get('notify_tuning'):
            msg = f"Tuning applied to {d['ip']}: {d['freq']}MHz / {d['volt']}mV"
            send_ntfy(msg, "TUNING SUCCESS", "zap"); send_nostr(msg)
        return jsonify({"status": "ok"})
    except: return jsonify({"status": "error"}), 500

@app.route('/api/reboot', methods=['POST'])
def reboot():
    try: requests.post(f"http://{request.json['ip']}/api/system/reboot", timeout=3); return jsonify({"status": "ok"})
    except: return jsonify({"status": "error"}), 500

@app.route('/api/settings', methods=['POST'])
def update_settings():
    DB['settings'].update(request.json); save_settings(DB['settings']); return jsonify({"status": "ok"})

@app.route('/api/system/reset', methods=['POST'])
def reset_db():
    if os.path.exists(DATA_FILE): os.remove(DATA_FILE)
    if os.path.exists(SETTINGS_FILE): os.remove(SETTINGS_FILE)
    DB['miners'] = []; DB['settings'] = load_settings()
    return jsonify({"status": "ok"})

@app.route('/api/test_ntfy', methods=['POST'])
def test_ntfy(): send_ntfy("OpenAxe Test!", "TEST"); return jsonify({"status": "ok"})

@app.route('/api/test_nostr', methods=['POST'])
def test_nostr(): send_nostr("OpenAxe Test Notification!"); return jsonify({"status": "ok"})

@app.route('/donate')
def donate_page(): return app.send_static_file('donate.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5055, debug=True)
