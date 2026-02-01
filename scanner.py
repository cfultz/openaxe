
import requests
import ipaddress
from concurrent.futures import ThreadPoolExecutor

def check_ip(ip):
    """
    Probes an IP address for the AxeOS API.
    Returns miner data if found, None otherwise.
    """
    try:
        url = f"http://{ip}/api/system/info"
        r = requests.get(url, timeout=0.8)
        if r.status_code == 200:
            data = r.json()
            if 'hashRate' in data or 'model' in data:
                return {
                    "ip": str(ip), 
                    "name": data.get('hostname', str(ip)), 
                    "model": data.get('model', 'Unknown Device')
                }
    except:
        pass
    return None

def scan_network(subnet_str):
    """
    Scans a /24 subnet for Bitaxe devices.
    """
    try:
        network = ipaddress.ip_network(subnet_str, strict=False)
        hosts = list(network.hosts())[:254]
    except ValueError:
        return []

    found_devices = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(check_ip, hosts)
        
    for res in results:
        if res:
            found_devices.append(res)
            
    return found_devices
