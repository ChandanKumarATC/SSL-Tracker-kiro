# Free Wildcard SSL Certificate Guide (Certbot + DNS Challenge)

## Overview

Wildcard SSL certificates (`*.example.com`) cover all subdomains under a domain.
Let's Encrypt issues free wildcard certs, but they **require DNS-01 challenge** —
meaning you must prove domain ownership by adding a TXT record to your DNS.

---

## Manual Method (Any DNS Provider)

```bash
# Install Certbot
sudo apt install certbot

# Request wildcard cert — you'll be prompted to add a DNS TXT record
sudo certbot certonly \
  --manual \
  --preferred-challenges dns \
  -d "*.example.com" \
  -d "example.com"
```

Certbot will output something like:

```
Please deploy a DNS TXT record under the name:
_acme-challenge.example.com
with the following value:
AbCdEfGhIjKlMnOpQrStUvWxYz123456789

Press Enter to Continue
```

1. Log in to your DNS provider
2. Add a TXT record: `_acme-challenge.example.com` → `<value>`
3. Wait 1–2 minutes for DNS propagation
4. Press Enter in the terminal

Cert files will be saved to `/etc/letsencrypt/live/example.com/`.

---

## Automated Method (Requires DNS API)

Full automation requires a DNS provider with an API. Certbot plugins exist for:

| Provider   | Plugin                          |
|------------|---------------------------------|
| Cloudflare | `certbot-dns-cloudflare`        |
| Route53    | `certbot-dns-route53`           |
| DigitalOcean | `certbot-dns-digitalocean`    |
| GoDaddy    | `certbot-dns-godaddy`           |

### Example: Cloudflare

```bash
pip install certbot-dns-cloudflare

# Create credentials file
cat > /etc/letsencrypt/cloudflare.ini << EOF
dns_cloudflare_api_token = YOUR_CLOUDFLARE_API_TOKEN
EOF
chmod 600 /etc/letsencrypt/cloudflare.ini

# Issue cert
sudo certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
  -d "*.example.com" \
  -d "example.com"
```

### Example: AWS Route53

```bash
pip install certbot-dns-route53

# Ensure AWS credentials are configured (~/.aws/credentials or IAM role)
sudo certbot certonly \
  --dns-route53 \
  -d "*.example.com" \
  -d "example.com"
```

---

## Auto-Renewal

Let's Encrypt certs expire every 90 days. Set up auto-renewal:

```bash
# Test renewal
sudo certbot renew --dry-run

# Certbot installs a systemd timer automatically; verify it:
sudo systemctl status certbot.timer

# Or add a cron job manually:
echo "0 3 * * * root certbot renew --quiet" | sudo tee /etc/cron.d/certbot
```

---

## Using the Cert with Nginx

```nginx
server {
    listen 443 ssl;
    server_name *.example.com example.com;

    ssl_certificate     /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Notes

- Wildcard certs only cover **one level** of subdomains (`*.example.com` covers
  `app.example.com` but NOT `api.app.example.com`).
- You need a separate cert or SAN entry for the apex domain (`example.com`).
- This tracker's SSL checker will detect wildcard certs automatically via the
  Subject Alternative Name (SAN) field in the certificate.
