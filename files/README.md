# 📸 Photo Gallery — Setup Guide

## Architecture

```
Browser → Raspberry Pi (Nginx) → Laptop (Flask API) via Tailscale
```

The laptop does all the work (thumbnails, serving photos).
The Pi is just a lightweight always-on reverse proxy.

---

## 1. Laptop Setup (your "NAS")

### Install dependencies
```bash
pip3 install flask flask-cors Pillow
```

### Set your photos directory and run
```bash
PHOTOS_DIR=/path/to/your/photos python3 app.py
```

The server starts on port 5000. Thumbnails are cached in `.thumb_cache/`
so they're only generated once per photo.

### Run as a background service (auto-start on boot)

Create `/etc/systemd/system/gallery.service`:

```ini
[Unit]
Description=Photo Gallery
After=network.target

[Service]
User=YOUR_USERNAME
WorkingDirectory=/path/to/gallery-backend
Environment=PHOTOS_DIR=/path/to/your/photos
ExecStart=/usr/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then enable it:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gallery
sudo systemctl start gallery
```

---

## 2. Tailscale Setup (both devices)

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Log in with the same account on both devices.
Find your laptop's Tailscale IP:
```bash
tailscale ip -4
# e.g. 100.64.1.23
```

---

## 3. Frontend Config

Edit `static/index.html` line 4 of the script section:

```js
const API_BASE = 'http://100.64.1.23:5000';  // ← your laptop's Tailscale IP
```

---

## 4. Raspberry Pi Setup

### Install Nginx
```bash
sudo apt update && sudo apt install nginx -y
```

### Copy the frontend to the Pi
From your laptop, over Tailscale:
```bash
rsync -avz ./static/ pi@<PI_TAILSCALE_IP>:/var/www/gallery/
```

### Configure Nginx as reverse proxy
Create `/etc/nginx/sites-available/gallery`:

```nginx
server {
    listen 80;

    # Serve the frontend
    root /var/www/gallery;
    index index.html;

    # Proxy API calls to the laptop
    location /api/ {
        proxy_pass http://100.64.1.23:5000;  # ← laptop Tailscale IP
        proxy_set_header Host $host;
        proxy_read_timeout 60s;
    }
}
```

Enable it:
```bash
sudo ln -s /etc/nginx/sites-available/gallery /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

> **Note:** If you use Nginx to proxy the API, change `API_BASE` in index.html
> to an empty string `''` so API calls go through the Pi.

### Access the gallery
Open a browser and go to: `http://<PI_IP>` or `http://<PI_TAILSCALE_IP>`

---

## Tips

- **Thumbnails are cached** — first load of an album may be slow while thumbnails
  generate. After that it's fast.
- **Add new photos?** Just add them to your folder. The API picks them up automatically.
- **Want HTTPS?** Use Tailscale's built-in HTTPS or add Certbot to Nginx.
- **Access from anywhere?** Enable Tailscale Funnel on the Pi to expose it publicly
  without opening firewall ports.
