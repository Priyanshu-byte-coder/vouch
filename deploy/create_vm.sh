#!/bin/sh
# Creates the billable Vouch VM on Vultr (vc2-2c-4gb, Bangalore, Ubuntu 24.04, ~$20/month). Run it yourself:
#   bash deploy/create_vm.sh <VULTR_ACCOUNT_API_KEY>
# Writes the instance id and IP to deploy/vm.env (gitignored). Delete the VM after the finals.
set -e
K="$1"; [ -n "$K" ] || { echo "usage: bash deploy/create_vm.sh <VULTR_API_KEY>"; exit 1; }
cd "$(dirname "$0")"
[ -f ~/.ssh/vouch_vultr ] || ssh-keygen -t ed25519 -N "" -C vouch-deploy -f ~/.ssh/vouch_vultr -q
PUB=$(cat ~/.ssh/vouch_vultr.pub)
SK=$(curl -s -X POST -H "Authorization: Bearer $K" -H "Content-Type: application/json" https://api.vultr.com/v2/ssh-keys \
  -d "{\"name\":\"vouch-deploy\",\"ssh_key\":\"$PUB\"}" | python -c "import sys,json;print(json.load(sys.stdin)['ssh_key']['id'])")
UD=$(base64 -w0 cloud-init.sh)
ID=$(curl -s -X POST -H "Authorization: Bearer $K" -H "Content-Type: application/json" https://api.vultr.com/v2/instances \
  -d "{\"region\":\"blr\",\"plan\":\"vc2-2c-4gb\",\"os_id\":2284,\"label\":\"vouch\",\"hostname\":\"vouch\",\"sshkey_id\":[\"$SK\"],\"user_data\":\"$UD\",\"backups\":\"disabled\"}" \
  | python -c "import sys,json;d=json.load(sys.stdin);print(d['instance']['id']) if 'instance' in d else sys.exit('Vultr error: '+json.dumps(d))")
echo "created instance $ID, waiting for an IP..."
for i in $(seq 1 60); do
  IP=$(curl -s -H "Authorization: Bearer $K" https://api.vultr.com/v2/instances/$ID | python -c "import sys,json;print(json.load(sys.stdin)['instance']['main_ip'])")
  [ "$IP" != "0.0.0.0" ] && [ -n "$IP" ] && break
  sleep 5
done
printf 'VM_ID=%s\nVM_IP=%s\n' "$ID" "$IP" > vm.env
echo "VM ready: id=$ID ip=$IP (saved to deploy/vm.env)"
