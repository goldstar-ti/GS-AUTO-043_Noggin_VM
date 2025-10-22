#!/bin/bash

echo "Testing Noggin Processor Systemd Service"
echo "========================================="
echo ""

echo "1. Checking if service file exists..."
if [ -f /etc/systemd/system/noggin-processor.service ]; then
    echo "   ✓ Service file found"
else
    echo "   ✗ Service file not found at /etc/systemd/system/noggin-processor.service"
    exit 1
fi

echo ""
echo "2. Reloading systemd daemon..."
sudo systemctl daemon-reload
echo "   ✓ Daemon reloaded"

echo ""
echo "3. Checking service status..."
sudo systemctl status noggin-processor --no-pager

echo ""
echo "4. Starting service..."
sudo systemctl start noggin-processor
sleep 3

echo ""
echo "5. Checking if service is active..."
if sudo systemctl is-active --quiet noggin-processor; then
    echo "   ✓ Service is active"
else
    echo "   ✗ Service failed to start"
    echo ""
    echo "   Recent logs:"
    sudo journalctl -u noggin-processor -n 20 --no-pager
    exit 1
fi

echo ""
echo "6. Showing recent logs (last 20 lines)..."
sudo journalctl -u noggin-processor -n 20 --no-pager

echo ""
echo "7. Service test complete!"
echo ""
echo "Useful commands:"
echo "  ./manage_service.sh status  - Check service status"
echo "  ./manage_service.sh logs    - View recent logs"
echo "  ./manage_service.sh follow  - Follow logs in real-time"
echo "  ./manage_service.sh stop    - Stop the service"
echo "  python service_dashboard.py - View processing dashboard"