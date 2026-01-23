#!/bin/bash

echo "=== WEB SERVER DETECTION ==="
echo ""

# Check ports
echo "1. Ports in use:"
sudo ss -tlnp | grep -E ':(80|443|5050|8080|10000)' | awk '{print $4, $5, $7}'
echo ""

# Check Apache
echo "2. Apache:"
if command -v apache2 &> /dev/null; then
    echo "   Installed: $(apache2 -v | head -1)"
    systemctl is-active apache2 && echo "   Status: RUNNING" || echo "   Status: STOPPED"
else
    echo "   Not installed"
fi
echo ""

# Check Nginx
echo "3. Nginx:"
if command -v nginx &> /dev/null; then
    echo "   Installed: $(nginx -v 2>&1)"
    systemctl is-active nginx && echo "   Status: RUNNING" || echo "   Status: STOPPED"
else
    echo "   Not installed"
fi
echo ""

# Check Webmin
echo "4. Webmin:"
if systemctl list-units --full --all | grep -q webmin; then
    systemctl is-active webmin && echo "   Status: RUNNING on port 10000" || echo "   Status: STOPPED"
    echo "   Access: https://$(hostname -I | awk '{print $1}'):10000"
else
    echo "   Not found as systemd service"
fi
echo ""

# Check pgAdmin
echo "5. pgAdmin:"
if systemctl list-units --full --all | grep -q pgadmin; then
    systemctl is-active pgadmin4 && echo "   Status: RUNNING" || echo "   Status: STOPPED"
elif pgrep -f pgadmin > /dev/null; then
    echo "   Process found (not systemd service)"
else
    echo "   Not running"
fi
echo ""

# Check what's actually listening
echo "6. Active web listeners:"
sudo lsof -i -P -n | grep LISTEN | grep -E ':(80|443|5050|8080|10000)' | awk '{print $1, $9}'