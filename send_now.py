import env_loader
import os, urllib.request, json, urllib.error

def get_env_tags(env_name):
    val = os.environ.get(env_name)
    if val:
        return [t.strip() for t in val.split(",") if t.strip()]
    return []

payload = {
    'monthName': 'May',
    'groupId': os.environ.get('WA_GROUP_ID'),
    'screenshotDir': 'output',
    'reports': [
        { 'file': 'MLL_Vendor_combined.png', 'entity': 'MLL', 'tags': get_env_tags("WA_TAGS_MLL_VENDOR") },
        { 'file': 'WZ_Vendor_combined.png', 'entity': 'WZ', 'tags': get_env_tags("WA_TAGS_WZ_VENDOR") },
        { 'file': 'MLL_Expense_combined.png', 'entity': 'MLL (Expense)', 'tags': get_env_tags("WA_TAGS_MLL_EXPENSE") },
        { 'file': 'WZ_Expense_combined.png', 'entity': 'WZ (Expense)', 'tags': get_env_tags("WA_TAGS_WZ_EXPENSE") }
    ]
}

req = urllib.request.Request('http://localhost:3000/send-flash', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')

try:
    print("Sending request to WhatsApp service...")
    with urllib.request.urlopen(req) as response:
        print("✅ Success:", response.read().decode())
except urllib.error.HTTPError as e:
    print("❌ HTTP Error:", e.read().decode())
except Exception as e:
    print("❌ Exception:", e)
