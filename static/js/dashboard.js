let allMiners = []; 
let isModalOpen = false;
let hashChart = null;
let lastTotalShares = null; 
let lastBlockCount = null; 

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
        data: { 
            labels: Array(30).fill(''), 
            datasets: [{ 
                label: 'Hashrate (TH/s)', 
                data: Array(30).fill(0), 
                borderColor: '#818cf8', 
                backgroundColor: gradient,
                borderWidth: 2,
                tension: 0.4, 
                fill: true, 
                pointRadius: 0 
            }] 
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false, 
            plugins: { legend: { display: false } }, 
            scales: { 
                x: { display: false }, 
                y: { display: true, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#64748b' }}
            }, 
            animation: false 
        }
    });
});

function showView(view) {
    document.getElementById('view-dashboard').classList.toggle('hidden', view === 'settings');
    document.getElementById('view-settings').classList.toggle('hidden', view === 'dashboard');
}

function copyToClipboard(text, btnId) {
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById(btnId);
        const old = btn.innerHTML;
        btn.innerHTML = '<i class="ph-bold ph-check text-green-500"></i>';
        setTimeout(() => { btn.innerHTML = old; }, 2000);
    });
}

function renderMiners(data) {
    if (isModalOpen) return;
    allMiners = data.miners;
    const grid = document.getElementById('miners-grid');
    grid.innerHTML = '';
    
    if (data.miners.length === 0) {
        grid.innerHTML = `<div class="col-span-full text-center py-12 text-slate-500 theme-card rounded-xl border border-dashed border-slate-700/50"><p>No miners found.</p></div>`;
        return;
    }

    data.miners.forEach(miner => {
        const s = miner.stats || {connected: false};
        const isOnline = s.connected;
        let hrVal = s.hashrate_10m || 0; let hrUnit = 'GH/s';
        if(hrVal > 1000) { hrVal = hrVal/1000; hrUnit = 'TH/s'; }
        
        const card = `
            <div class="theme-card p-5 rounded-xl border border-slate-700/50 cursor-pointer hover:border-indigo-500/50 transition relative group" onclick="openDetail('${miner.ip}')">
                <div class="flex justify-between items-start mb-4">
                    <div class="flex items-center gap-3">
                        <div class="w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' : 'bg-red-500'}"></div>
                        <div><h3 class="font-bold text-sm text-slate-200">${miner.custom_name || miner.name || miner.ip}</h3><p class="text-xs text-slate-500 font-mono">${miner.ip} ${isOnline ? '<span class="text-green-500 font-bold ml-1">LIVE</span>' : ''}</p></div>
                    </div>
                </div>
                <div class="flex justify-between items-end">
                    <div><p class="text-[10px] font-bold uppercase text-slate-500 mb-0.5">Hashrate</p><p class="text-2xl font-bold text-white">${hrVal.toFixed(2)} <span class="text-sm font-normal text-slate-400">${hrUnit}</span></p></div>
                    <div class="text-right"><p class="text-[10px] font-bold uppercase text-slate-500 mb-0.5">Temp</p><p class="text-lg font-bold text-white">${(s.temp || 0).toFixed(0)}°C</p></div>
                </div>
            </div>`;
        grid.insertAdjacentHTML('beforeend', card);
    });
}

function updateStats(data) {
    if (isModalOpen) return;
    
    const valInTh = data.fleet.hash / 1000;
    hashChart.data.datasets[0].data.push(valInTh);
    hashChart.data.datasets[0].data.shift();
    hashChart.update();
    document.getElementById('hero-hash').innerHTML = `${valInTh.toFixed(2)} <span class="text-xl text-slate-400">TH/s</span>`;

    document.getElementById('net-hash').innerText = formatBigNum(data.market.net_hash, "H/s");
    document.getElementById('network-diff').innerText = formatBigNum(data.market.diff);
    document.getElementById('blocks-found').innerText = data.fleet.blocks_found || 0;
    document.getElementById('global-best-share').innerText = formatBigNum(data.fleet.best_share);
    
    const coinSymbol = data.settings.coin || "BC2";
    document.getElementById('block-reward').innerText = (data.market.reward || 0) + " " + coinSymbol;

    const luck = calculateLuck(data.fleet.hash, data.market.diff);
    const luckTimeEl = document.getElementById('luck-time');
    const luckProbEl = document.getElementById('luck-prob');
    if (luckTimeEl) luckTimeEl.innerText = luck.text;
    if (luckProbEl) luckProbEl.innerText = luck.prob > 0 ? `${luck.prob.toFixed(4)}% daily` : "--% daily";

    const watts = data.fleet.power || 0;
    const kwhPrice = parseFloat(data.settings.kwh_price) || 0.12;
    const dailyCost = (watts / 1000) * 24 * kwhPrice;
    
    document.getElementById('fleet-power').innerText = watts.toFixed(0) + " W";
    document.getElementById('pill-daily-cost').innerText = "$" + dailyCost.toFixed(2);
    document.getElementById('pill-monthly-cost').innerText = "$" + (dailyCost * 30).toFixed(2);
    
    const curr = data.settings.currency || 'USD';
    const sym = { 'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥' }[curr] || '$';
    document.getElementById('market-price').innerText = sym + (data.market.price || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 6});

    const currentShares = data.fleet.total_shares || 0;
    if (lastTotalShares !== null && currentShares > lastTotalShares) {
        const diff = currentShares - lastTotalShares;
        const drops = Math.min(diff, 10);
        for(let i=0; i<drops; i++) setTimeout(() => spawnCoin(), i * 200);
    }
    lastTotalShares = currentShares;

    const currentBlocks = data.fleet.blocks_found || 0;
    if (lastBlockCount !== null && currentBlocks > lastBlockCount) {
        triggerFanfare(); 
    }
    lastBlockCount = currentBlocks;
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

function spawnCelebrationIcon() {
    const icons = ['🚀', '🧱', '⛏️', '💰', '🤑', '💎', '🚀'];
    const icon = document.createElement('div');
    icon.innerText = icons[Math.floor(Math.random() * icons.length)];
    icon.style.position = 'fixed';
    icon.style.zIndex = '9999';
    icon.style.fontSize = (Math.random() * 30 + 30) + 'px'; 
    icon.style.left = (Math.random() * 80 + 10) + 'vw'; 
    icon.style.bottom = '-60px'; 
    icon.style.transition = `transform ${Math.random() * 2 + 1}s ease-in, opacity 2.5s ease-in`; 
    icon.style.pointerEvents = 'none';
    document.body.appendChild(icon);

    setTimeout(() => {
        const wiggle = (Math.random() - 0.5) * 100; 
        icon.style.transform = `translate(${wiggle}px, -120vh)`; 
        icon.style.opacity = '0.5'; 
    }, 50);

    setTimeout(() => { icon.remove(); }, 4000);
}

function triggerFanfare() {
    const duration = 5 * 1000;
    const animationEnd = Date.now() + duration;
    const defaults = { startVelocity: 30, spread: 360, ticks: 60, zIndex: 9998 };
    const random = (min, max) => Math.random() * (max - min) + min;

    const interval = setInterval(function() {
      const timeLeft = animationEnd - Date.now();
      if (timeLeft <= 0) return clearInterval(interval);
      const particleCount = 50 * (timeLeft / duration);
      confetti(Object.assign({}, defaults, { particleCount, origin: { x: random(0.1, 0.3), y: Math.random() - 0.2 } }));
      confetti(Object.assign({}, defaults, { particleCount, origin: { x: random(0.7, 0.9), y: Math.random() - 0.2 } }));
    }, 250);

    let launchCount = 0;
    const launchInterval = setInterval(() => {
        spawnCelebrationIcon();
        launchCount++;
        if (launchCount >= 25) clearInterval(launchInterval);
    }, 80); 
}

function calculateLuck(hashrateGh, difficulty) {
    if (!hashrateGh || hashrateGh <= 0 || !difficulty || difficulty <= 0) return { text: "∞", prob: 0 };
    const hashrateH = hashrateGh * 1e9;
    const hashesToFindBlock = difficulty * 4294967296; 
    const secondsPerBlock = hashesToFindBlock / hashrateH;
    const dailyProb = (86400 / secondsPerBlock) * 100;
    
    let timeStr = "";
    const days = secondsPerBlock / 86400;
    const years = days / 365;
    
    if (years >= 100) timeStr = "> 100 Yrs";
    else if (years >= 1) timeStr = `${years.toFixed(1)} Years`;
    else if (days >= 30) timeStr = `${(days/30).toFixed(1)} Months`;
    else if (days >= 1) timeStr = `${days.toFixed(1)} Days`;
    else timeStr = `${(secondsPerBlock/3600).toFixed(1)} Hours`;
    
    return { text: timeStr, prob: dailyProb };
}

// Logic to separate Host and Port from full URL
function parseStratumUrl(fullUrl) {
    if (!fullUrl) return { host: "", port: "" };
    // Find the last colon to separate port, unless it's part of the protocol
    // Typically stratum+tcp://host:port
    const protocolEnd = fullUrl.indexOf('://');
    const lastColon = fullUrl.lastIndexOf(':');
    
    // If the last colon is after the protocol definition, we assume it's the port separator
    if (lastColon > protocolEnd + 2) {
        const host = fullUrl.substring(0, lastColon);
        const port = fullUrl.substring(lastColon + 1);
        return { host, port };
    }
    // No port found
    return { host: fullUrl, port: "" };
}

function openDetail(ip) {
    const miner = allMiners.find(m => m.ip === ip);
    if(!miner) return;
    isModalOpen = true;
    const s = miner.stats || {};
    document.getElementById('detailModal').setAttribute('data-ip', ip);
    document.getElementById('detailName').innerText = miner.custom_name || ip;
    document.getElementById('detailIP').innerText = ip;
    
    let hr = s.hashrate_10m || 0;
    document.getElementById('detailHash').innerText = (hr / (hr > 1000 ? 1000 : 1)).toFixed(2) + (hr > 1000 ? " TH/s" : " GH/s");
    document.getElementById('detailTemp').innerText = (s.temp || 0) + "°C";
    
    document.getElementById('valFreq').innerText = s.frequency || 485;
    document.getElementById('inputFreq').value = s.frequency || 485;
    document.getElementById('valVolt').innerText = s.voltage || 1200;
    document.getElementById('inputVolt').value = s.voltage || 1200;
    
    // New Split Logic
    const main = parseStratumUrl(s.stratumURL || "");
    document.getElementById('poolHost').value = main.host;
    document.getElementById('poolPort').value = main.port;
    document.getElementById('poolUser').value = s.stratumUser || "";
    
    // Fallback is usually not returned by basic stats API, so we leave blank or use if available in DB later
    
    document.getElementById('detailModal').classList.remove('hidden');
    document.getElementById('detailModal').classList.add('flex');
}

function closeDetail() { 
    isModalOpen = false;
    document.getElementById('detailModal').classList.add('hidden'); 
    document.getElementById('detailModal').classList.remove('flex'); 
}

function openRenameModal() { document.getElementById('renameModal').classList.remove('hidden'); document.getElementById('renameModal').classList.add('flex'); }

function openBulkPoolModal() {
    document.getElementById('bulkPoolModal').classList.remove('hidden');
    document.getElementById('bulkPoolModal').classList.add('flex');
}

async function saveBulkPoolSettings() {
    const host = document.getElementById('bulkPoolHost').value;
    const port = document.getElementById('bulkPoolPort').value;
    const user = document.getElementById('bulkPoolUser').value;
    const pass = document.getElementById('bulkPoolPass').value;
    
    const fbHost = document.getElementById('bulkPoolFallbackHost').value;
    const fbPort = document.getElementById('bulkPoolFallbackPort').value;
    const fbUser = document.getElementById('bulkPoolFallbackUser').value;
    const fbPass = document.getElementById('bulkPoolFallbackPass').value;

    if(!confirm("This will restart ALL active miners. Continue?")) return;
    
    // Reconstruct URLs
    const url = port ? `${host}:${port}` : host;
    const fbUrl = (fbHost && fbPort) ? `${fbHost}:${fbPort}` : fbHost;

    await fetch('/api/miners/pool/all', { 
        method: 'POST', 
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({ 
            url: url, user: user, pass: pass,
            fallbackUrl: fbUrl, fallbackUser: fbUser, fallbackPass: fbPass
        }) 
    });
    alert("Bulk update command sent.");
    document.getElementById('bulkPoolModal').classList.add('hidden');
}

async function saveName() {
    const ip = document.getElementById('detailModal').getAttribute('data-ip'), name = document.getElementById('newNameInput').value;
    await fetch('/api/miners/rename', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ip: ip, name: name}) });
    document.getElementById('renameModal').classList.add('hidden');
    isModalOpen = false;
}

async function savePoolSettings() {
    const ip = document.getElementById('detailModal').getAttribute('data-ip');
    
    const host = document.getElementById('poolHost').value;
    const port = document.getElementById('poolPort').value;
    const user = document.getElementById('poolUser').value;
    const pass = document.getElementById('poolPass').value;
    
    const fbHost = document.getElementById('poolFallbackHost').value;
    const fbPort = document.getElementById('poolFallbackPort').value;
    const fbUser = document.getElementById('poolFallbackUser').value;
    const fbPass = document.getElementById('poolFallbackPass').value;

    const url = port ? `${host}:${port}` : host;
    const fbUrl = (fbHost && fbPort) ? `${fbHost}:${fbPort}` : fbHost;

    await fetch('/api/miners/pool', { 
        method: 'POST', 
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({ 
            ip: ip, url: url, user: user, pass: pass,
            fallbackUrl: fbUrl, fallbackUser: fbUser, fallbackPass: fbPass
        }) 
    });
    alert("Pool update sent!");
}

async function applyOverclock() {
    const ip = document.getElementById('detailModal').getAttribute('data-ip'), freq = document.getElementById('inputFreq').value, volt = document.getElementById('inputVolt').value;
    await fetch('/api/overclock', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ip: ip, freq: freq, volt: volt }) });
    alert("Tuning applied!");
}

async function rebootMiner() {
    const ip = document.getElementById('detailModal').getAttribute('data-ip');
    if(confirm("Reboot miner?")) await fetch('/api/reboot', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ ip: ip }) });
}

function formatBigNum(num, unit='') {
    if (num === undefined || num === null) return "0 " + unit;
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

async function saveNotificationSettings() {
    const config = {
        ntfy_server: document.getElementById('ntfyServer').value,
        ntfy_topic: document.getElementById('ntfyTopic').value,
        nostr_privkey: document.getElementById('nostrPrivKey').value,
        nostr_recipient_pubkey: document.getElementById('nostrPubKey').value,
        kwh_price: parseFloat(document.getElementById('kwhPrice').value) || 0.12,
        notify_offline: document.getElementById('notifyOffline').checked,
        notify_blocks: document.getElementById('notifyBlocks').checked,
        notify_tuning: document.getElementById('notifyTuning').checked
    };
    await fetch('/api/settings', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(config) });
    alert("Settings saved!");
}

async function testNtfy() {
    await fetch('/api/test_ntfy', { method: 'POST' });
    alert("Sent ntfy test!");
}

async function testNostr() {
    await fetch('/api/test_nostr', { method: 'POST' });
    alert("Sent Nostr test!");
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

async function resetSystem() {
    if(confirm("Factory reset?")) { await fetch('/api/system/reset', { method: 'POST' }); location.reload(); }
}

async function runScan() {
    const subnet = document.getElementById('subnetInput').value;
    await fetch('/api/scan', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ subnet: subnet }) });
    alert("Scanning...");
}

async function pollData() {
    try {
        const res = await fetch('/api/miners');
        const data = await res.json();
        renderMiners(data); updateStats(data);
    } catch(e) {}
}

setInterval(pollData, 5000); pollData();
