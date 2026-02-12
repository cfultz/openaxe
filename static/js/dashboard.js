let currentMinerIP = null;
let allMiners = []; 
let rebootConfirmState = false;
let hashChart = null;
let lastKnownBlockCount = null;
let lastTotalShares = null; 

const VERBS = ["Running", "Flying", "Swimming", "Mining", "Sleeping", "Hunting", "Jumping", "Hashing", "Hidden", "Silent", "Rapid", "Turbo"];
const COLORS = ["Red", "Blue", "Green", "Cyan", "Purple", "Golden", "Silver", "Black", "White", "Neon", "Amber", "Indigo"];
const ANIMALS = ["Badger", "Fox", "Eagle", "Bear", "Wolf", "Tiger", "Shark", "Panda", "Hawk", "Viper", "Cobra", "Falcon"];

document.addEventListener('DOMContentLoaded', () => {
    const ctx = document.getElementById('hashChart').getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.5)'); 
    gradient.addColorStop(1, 'rgba(99, 102, 241, 0.0)');
    hashChart = new Chart(ctx, {
        type: 'line',
        data: { labels: Array(30).fill(''), datasets: [{ label: 'Hashrate (TH/s)', data: Array(30).fill(0), borderColor: '#818cf8', backgroundColor: gradient, borderWidth: 2, tension: 0.4, fill: true, pointRadius: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: true, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748b' }}}, animation: false }
    });
});

function showView(view) {
    if (view === 'settings') {
        document.getElementById('view-dashboard').classList.add('hidden');
        document.getElementById('view-settings').classList.remove('hidden');
    } else {
        document.getElementById('view-settings').classList.add('hidden');
        document.getElementById('view-dashboard').classList.remove('hidden');
    }
}

function copyToClipboard(text, btnId) {
    if (!navigator.clipboard) {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            updateCopyButton(btnId);
        } catch (err) {
            console.error('Fallback: Oops, unable to copy', err);
        }
        document.body.removeChild(textArea);
        return;
    }
    navigator.clipboard.writeText(text).then(() => {
        updateCopyButton(btnId);
    }, (err) => {
        console.error('Async: Could not copy text: ', err);
    });
}

function updateCopyButton(btnId) {
    const btn = document.getElementById(btnId);
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i class="ph-bold ph-check text-green-500"></i>';
    btn.classList.add('text-green-500');
    setTimeout(() => { 
        btn.innerHTML = originalHtml; 
        btn.classList.remove('text-green-500');
    }, 2000);
}

function setCurrentAndOpen(ip) {
    currentMinerIP = ip;
    openDetail(ip);
}

function renderMiners(data) {
    allMiners = data.miners;
    const grid = document.getElementById('miners-grid');
    grid.innerHTML = '';
    if(data.miners.length === 0) {
        grid.innerHTML = `<div class="col-span-full text-center py-12 text-slate-400 theme-card rounded-xl border-dashed border-2 border-slate-700/50"><p>No miners found.</p></div>`;
        return;
    }
    data.miners.forEach(miner => {
        const s = miner.stats || {};
        const isOnline = s.connected;
        let hrVal = s.hashrate_10m || 0; 
        let hrUnit = 'GH/s';
        if(hrVal > 1000) { hrVal = hrVal/1000; hrUnit = 'TH/s'; }
        const dName = miner.display_name || miner.name;
        const statusBadge = isOnline ? '<span class="bg-green-900/30 text-green-400 px-2 py-0.5 rounded text-[10px] font-bold">LIVE</span>' : '<span class="bg-red-900/30 text-red-400 px-2 py-0.5 rounded text-[10px] font-bold">OFFLINE</span>';
        const cardHTML = `<div class="theme-card p-5 rounded-xl shadow-sm border border-slate-700/50 hover:border-indigo-500/50 transition relative overflow-hidden group cursor-pointer z-10" onclick="setCurrentAndOpen('${miner.ip}')">
                <div class="flex justify-between items-start mb-4 relative z-20">
                    <div class="flex items-center gap-3">
                        <div class="w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-red-500'}"></div>
                        <div><h3 class="font-bold text-sm text-slate-200">${dName}</h3><div class="flex items-center gap-2 mt-1"><p class="text-xs text-slate-500 font-mono">${miner.ip}</p>${statusBadge}</div></div>
                    </div>
                    <button onclick="event.stopPropagation(); removeMiner('${miner.ip}')" class="text-slate-500 hover:text-red-400 transition z-30 p-2 rounded-full hover:bg-slate-800"><i class="ph-bold ph-trash"></i></button>
                </div>
                <div class="flex justify-between items-end relative z-20">
                    <div><p class="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-0.5">Hashrate</p><p class="text-2xl font-bold text-white">${hrVal.toFixed(2)} <span class="text-sm font-normal text-slate-400">${hrUnit}</span></p></div>
                    <div class="text-right"><p class="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-0.5">Temp</p><p class="text-lg font-bold text-white">${(s.temp || 0).toFixed(0)}°C</p></div>
                </div>
            </div>`;
        grid.insertAdjacentHTML('beforeend', cardHTML);
    });
}

function updateStats(data) {
    if(hashChart) {
        const valInTh = data.fleet.hash / 1000;
        const d = hashChart.data.datasets[0].data;
        d.push(valInTh); d.shift(); hashChart.update();
    }
    const currentShares = data.fleet.total_shares || 0;
    if (lastTotalShares !== null && currentShares > lastTotalShares) {
        const diff = currentShares - lastTotalShares;
        const drops = Math.min(diff, 15);
        for(let i=0; i<drops; i++) setTimeout(() => spawnCoin(), i * 150);
    }
    lastTotalShares = currentShares;

    let dHash = data.fleet.hash; let dUnit = 'GH/s';
    if(dHash > 1000) { dHash = dHash/1000; dUnit = 'TH/s'; }
    document.getElementById('hero-hash').innerHTML = `${dHash.toFixed(2)} <span class="text-xl text-slate-400 font-normal">${dUnit}</span>`;
    document.getElementById('fleet-power').innerText = data.fleet.power.toFixed(0) + " W";
    document.getElementById('fleet-count').innerText = data.miners.length;
    let eff = data.fleet.hash > 0 ? data.fleet.power / (data.fleet.hash / 1000) : 0;
    const effEl = document.getElementById('fleet-eff');
    if(effEl) effEl.innerText = eff.toFixed(2) + " J/TH";
    const curr = data.market.currency || 'USD';
    const sym = { 'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'CAD': 'C$', 'AUD': 'A$' }[curr] || '$';
    const price = data.market.price || 0;
    let pStr = price < 1.0 ? sym + price.toFixed(6) : sym + price.toLocaleString(undefined, {minimumFractionDigits: 2});
    document.getElementById('market-price').innerText = pStr;
    const netDiffEl = document.getElementById('network-diff');
    if(netDiffEl) netDiffEl.innerText = formatBigNum(data.market.diff || 0);
    document.getElementById('net-hash').innerText = formatBigNum(data.market.net_hash, "H/s");
    
    const coinSymbol = data.settings && data.settings.coin ? data.settings.coin : "BC2";
    document.getElementById('block-reward').innerText = data.market.reward + " " + coinSymbol;
    
    const headerEl = document.getElementById('app-header-subtitle');
    if(headerEl) {
        let editionText = coinSymbol === 'BTC' ? "Bitcoin Edition" : "Bitcoin II Edition";
        headerEl.innerHTML = `${coinSymbol} <span class="text-yellow-500">${editionText}</span>`;
    }

    const luck = calculateLuck(data.fleet.hash, data.market.diff);
    document.getElementById('luck-time').innerText = luck.text;
    document.getElementById('luck-prob').innerText = luck.prob < 0.01 ? "< 0.01% daily" : `${luck.prob.toFixed(4)}% daily`;
    document.getElementById('blocks-found').innerText = data.fleet.blocks_found || 0;
    document.getElementById('global-best-share').innerText = formatBigNum(data.fleet.best_share);
    if(data.system) {
        const bytes = data.system.db_size_bytes;
        document.getElementById('sys-db-size').innerText = bytes > 1024 ? (bytes/1024).toFixed(2) + " KB" : bytes + " B";
    }
    const currentBlocks = data.fleet.blocks_found || 0;
    if (lastKnownBlockCount !== null && currentBlocks > lastKnownBlockCount) triggerFanfare();
    lastKnownBlockCount = currentBlocks;
}

function spawnCoin() {
    const card = document.getElementById('graph-card');
    if(!card) return;
    const coin = document.createElement('span');
    coin.innerText = '🪙';
    coin.style.position = 'absolute';
    coin.style.zIndex = '50';
    coin.style.fontSize = Math.random() > 0.5 ? '24px' : '18px';
    coin.style.left = (Math.random() * 90) + '%';
    coin.style.top = '-30px';
    coin.style.opacity = '1';
    coin.style.transition = 'all 1.5s ease-in';
    coin.style.pointerEvents = 'none';
    card.appendChild(coin);
    setTimeout(() => {
        coin.style.top = '120%';
        coin.style.opacity = '0';
        coin.style.transform = `rotate(${Math.random() * 360}deg)`;
    }, 50);
    setTimeout(() => { coin.remove(); }, 1600);
}

function triggerFanfare() {
    const duration = 5 * 1000; const animationEnd = Date.now() + duration;
    const defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 0 };
    const random = (min, max) => Math.random() * (max - min) + min;
    const interval = setInterval(function() {
      const timeLeft = animationEnd - Date.now();
      if (timeLeft <= 0) return clearInterval(interval);
      const particleCount = 50 * (timeLeft / duration);
      confetti(Object.assign({}, defaults, { particleCount, origin: { x: random(0.1, 0.3), y: Math.random() - 0.2 } }));
      confetti(Object.assign({}, defaults, { particleCount, origin: { x: random(0.7, 0.9), y: Math.random() - 0.2 } }));
    }, 250);
}

function openDetail(ip) {
    document.getElementById('detailModal').setAttribute('data-ip', ip);
    const miner = allMiners.find(m => m.ip === ip);
    if(!miner) return;
    const s = miner.stats || {};
    
    const setText = (id, val) => { const el = document.getElementById(id); if(el) el.innerText = val; };
    const setHtml = (id, val) => { const el = document.getElementById(id); if(el) el.innerHTML = val; };
    const setVal = (id, val) => { const el = document.getElementById(id); if(el) el.value = val; };

    setText('detailName', miner.display_name || miner.name);
    setText('detailIP', miner.ip);

    let hr = s.hashrate_10m || 0; let hrUnit = "GH/s"; if(hr > 1000) { hr = hr/1000; hrUnit = "TH/s"; }
    setHtml('detailHash', `${hr.toFixed(2)} <span class="text-base font-normal text-slate-400">${hrUnit}</span>`);
    setText('detailHashRaw', (s.hashrate_raw || 0).toFixed(0) + " GH/s");
    
    let tStr = `${(s.temp || 0).toFixed(1)} <span class="text-lg font-normal opacity-70">°C</span>`;
    if(s.vrTemp && s.vrTemp > 0) tStr += ` <span class="text-sm opacity-50 ml-2 font-mono">VR:${s.vrTemp.toFixed(0)}°</span>`;
    setHtml('detailTemp', tStr);

    setText('detailWatts', (s.power || 0).toFixed(0) + " W");
    let eff = hr > 0 ? (s.power || 0) / (hrUnit === "TH/s" ? hr : hr/1000) : 0;
    setText('detailEff', eff.toFixed(2) + " J/TH");
    setText('detailBestDiff', formatBigNum(s.bestDiff || 0));
    setText('detailUptime', "Uptime: " + formatUptime(s.uptime || 0));

    setVal('inputFreq', s.frequency || 485);
    setText('valFreq', s.frequency || 485);
    setVal('inputVolt', s.voltage || 1200);
    setText('valVolt', s.voltage || 1200);

    setVal('poolURL', s.stratumURL || "");
    setVal('poolUser', s.stratumUser || "");
    setVal('poolPass', ""); 

    resetRebootBtn();
    document.getElementById('detailModal').classList.remove('hidden');
    document.getElementById('detailModal').classList.add('flex');
}

function closeDetail() {
    document.getElementById('detailModal').classList.add('hidden');
    document.getElementById('detailModal').classList.remove('flex');
}

function formatBigNum(num, unit='') {
    if (num >= 1e24) return (num / 1e24).toFixed(2) + " Y" + unit; 
    if (num >= 1e21) return (num / 1e21).toFixed(2) + " Z" + unit; 
    if (num >= 1e18) return (num / 1e18).toFixed(2) + " E" + unit; 
    if (num >= 1e15) return (num / 1e15).toFixed(2) + " P" + unit; 
    if (num >= 1e12) return (num / 1e12).toFixed(2) + " T" + unit; 
    if (num >= 1e9)  return (num / 1e9).toFixed(2) + " G" + unit;  
    if (num >= 1e6)  return (num / 1e6).toFixed(2) + " M" + unit;  
    if (num >= 1e3)  return (num / 1e3).toFixed(2) + " k" + unit;  
    return num.toLocaleString() + " " + unit;
}

function formatUptime(seconds) {
    if(!seconds) return "0m";
    const d = Math.floor(seconds / 86400), h = Math.floor(seconds % 86400 / 3600), m = Math.floor(seconds % 3600 / 60);
    return d > 0 ? `${d}d ${h}h` : h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function calculateLuck(hashrateGh, difficulty) {
    if (hashrateGh <= 0 || difficulty <= 0) return { text: "∞", prob: 0 };
    const seconds = (difficulty * 4294967296) / (hashrateGh * 1e9), daily_prob = (86400 / seconds) * 100;
    let timeStr = "", days = seconds / 86400, years = days / 365;
    if (years > 100) timeStr = "> 100 Yrs"; else if (years >= 1) timeStr = `${years.toFixed(1)} Years`;
    else if (days >= 30) timeStr = `${(days/30).toFixed(1)} Months`; else if (days >= 1) timeStr = `${days.toFixed(1)} Days`;
    else timeStr = `${(seconds/3600).toFixed(1)} Hours`;
    return { text: timeStr, prob: daily_prob };
}

function generateRandomName() {
    const v = VERBS[Math.floor(Math.random() * VERBS.length)], c = COLORS[Math.floor(Math.random() * COLORS.length)], a = ANIMALS[Math.floor(Math.random() * ANIMALS.length)];
    document.getElementById('newNameInput').value = `${v} ${c} ${a}`;
}

function openRenameModal() {
    document.getElementById('renameModal').classList.remove('hidden');
    document.getElementById('renameModal').classList.add('flex');
    document.getElementById('newNameInput').value = document.getElementById('detailName').innerText;
}

async function saveName() {
    const ip = document.getElementById('detailModal').getAttribute('data-ip'), name = document.getElementById('newNameInput').value;
    if(!name) return;
    await fetch('/api/miners/rename', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ip: ip, name: name}) });
    document.getElementById('detailName').innerText = name;
    document.getElementById('renameModal').classList.add('hidden');
    document.getElementById('renameModal').classList.remove('flex');
    pollData();
}

async function updateCoin() {
    const coin = document.getElementById('coinSelect').value;
    await fetch('/api/settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({coin: coin}) });
    pollData();
}

async function updateCurrency() {
    const curr = document.getElementById('currencySelect').value;
    await fetch('/api/settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({currency: curr}) });
    pollData();
}

async function savePoolSettings() {
    const ip = document.getElementById('detailModal').getAttribute('data-ip'), url = document.getElementById('poolURL').value, user = document.getElementById('poolUser').value, pass = document.getElementById('poolPass').value;
    if(!ip) return;
    await fetch('/api/miners/pool', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ip: ip, url: url, user: user, pass: pass }) });
    alert("Miner restarting...");
    closeDetail();
}

async function resetSystem() {
    if(!confirm("Factory reset?")) return;
    await fetch('/api/system/reset', { method: 'POST' });
    location.reload();
}

async function removeMiner(ip) {
    if(!confirm("Remove device?")) return;
    await fetch('/api/miners/delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ip: ip}) });
    pollData();
}

async function testNtfy() {
    const btn = document.querySelector('button[onclick="testNtfy()"]'), originalHtml = btn.innerHTML;
    btn.disabled = true; btn.innerHTML = '<i class="ph-bold ph-circle-notched animate-spin"></i> Sending...';
    try {
        const res = await fetch('/api/test_ntfy', { method: 'POST' }), data = await res.json();
        alert(data.status === "ok" ? "Test notification fired!" : "Error: " + data.msg);
    } catch (e) { alert("Failed: " + e.message); } finally { btn.disabled = false; btn.innerHTML = originalHtml; }
}

async function testNostr() {
    const btn = document.querySelector('button[onclick="testNostr()"]'), originalHtml = btn.innerHTML;
    btn.disabled = true; btn.innerHTML = '<i class="ph-bold ph-circle-notched animate-spin"></i> Sending...';
    try {
        const res = await fetch('/api/test_nostr', { method: 'POST' }), data = await res.json();
        alert(data.status === "ok" ? "Nostr test notification fired!" : "Error: " + data.msg);
    } catch (e) { alert("Failed: " + e.message); } finally { btn.disabled = false; btn.innerHTML = originalHtml; }
}

async function saveNotificationSettings() {
    const config = {
        ntfy_server: document.getElementById('ntfyServer').value,
        ntfy_topic: document.getElementById('ntfyTopic').value,
        ntfy_timeout: parseInt(document.getElementById('ntfyTimeout').value),
        nostr_privkey: document.getElementById('nostrPrivKey').value,
        nostr_recipient_pubkey: document.getElementById('nostrPubKey').value,
        notify_offline: document.getElementById('notifyOffline').checked,
        notify_blocks: document.getElementById('notifyBlocks').checked,
        notify_tuning: document.getElementById('notifyTuning').checked
    };
    await fetch('/api/settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(config) });
    alert("Settings updated!");
}

function resetRebootBtn() {
    rebootConfirmState = false;
    const btn = document.getElementById('rebootBtn');
    if(btn) { btn.innerText = "Reboot"; btn.className = "bg-slate-700 border border-slate-600 text-red-400 px-4 py-3 rounded-xl font-bold hover:bg-red-900/30 transition w-1/3"; }
}

async function rebootMiner() {
    const btn = document.getElementById('rebootBtn'), ip = document.getElementById('detailModal').getAttribute('data-ip');
    if(!rebootConfirmState) { rebootConfirmState = true; btn.innerText = "Confirm?"; btn.className = "bg-red-600 text-white px-4 py-3 rounded-xl font-bold animate-pulse w-1/3"; setTimeout(resetRebootBtn, 3000); return; }
    await fetch('/api/reboot', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ip: ip }) });
    closeDetail();
}

async function applyOverclock() {
    const ip = document.getElementById('detailModal').getAttribute('data-ip'), freq = document.getElementById('inputFreq').value, volt = document.getElementById('inputVolt').value;
    confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
    closeDetail();
    await fetch('/api/overclock', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ip: ip, freq: freq, volt: volt }) });
}

async function pollData() {
    try {
        const res = await fetch('/api/miners'), data = await res.json();
        renderMiners(data); updateStats(data);
    } catch(e) { console.error(e); }
}

setInterval(pollData, 5000); pollData();

async function runScan() {
    const subnet = document.getElementById('subnetInput').value;
    const overlay = document.createElement('div');
    overlay.id = 'scanOverlay';
    overlay.className = 'fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/90 backdrop-blur-md';
    overlay.innerHTML = `<div class="text-center p-8 bg-slate-800 rounded-2xl border border-slate-700 shadow-2xl max-w-sm w-full">
            <div id="scanLoading"><div class="inline-block w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin mb-4"></div><h2 class="text-xl font-bold text-white mb-2">Scanning</h2><p class="text-slate-400 text-sm">Probing ${subnet}...</p></div>
            <div id="scanResult" class="hidden"><div id="scanIcon" class="text-5xl mb-4"></div><h2 id="scanTitle" class="text-xl font-bold text-white mb-2"></h2><p id="scanDesc" class="text-slate-400 text-sm mb-6"></p><button onclick="document.getElementById('scanOverlay').remove()" class="w-full bg-indigo-600 text-white font-bold py-3 rounded-xl">Okay</button></div>
        </div>`;
    document.body.appendChild(overlay);
    try {
        const res = await fetch('/api/scan', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ subnet: subnet }) }), data = await res.json();
        document.getElementById('scanLoading').classList.add('hidden');
        document.getElementById('scanResult').classList.remove('hidden');
        if (data.found.length > 0) {
            document.getElementById('scanIcon').innerHTML = '<i class="ph-fill ph-check-circle text-green-500"></i>';
            document.getElementById('scanTitle').innerText = "Complete";
            document.getElementById('scanDesc').innerText = `Found ${data.found.length} miners.`;
            pollData();
        } else {
            document.getElementById('scanIcon').innerHTML = '<i class="ph-fill ph-warning-circle text-amber-500"></i>';
            document.getElementById('scanTitle').innerText = "None Found";
            document.getElementById('scanDesc').innerText = "Check your subnet and power.";
        }
    } catch (e) { document.getElementById('scanOverlay').remove(); alert("Failed: " + e.message); }
}
