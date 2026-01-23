#!/bin/bash
# Noggin Web Dashboard Service Management Script

SERVICE_NAME="noggin-web"

case "$1" in
    install)
        echo "Installing ${SERVICE_NAME} service..."
        sudo cp ./sys/noggin-web.service /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable ${SERVICE_NAME}
        echo "Service installed and enabled"
        ;;
    start)
        echo "Starting ${SERVICE_NAME}..."
        sudo systemctl start ${SERVICE_NAME}
        sudo systemctl status ${SERVICE_NAME} --no-pager
        ;;
    stop)
        echo "Stopping ${SERVICE_NAME}..."
        sudo systemctl stop ${SERVICE_NAME}
        ;;
    restart)
        echo "Restarting ${SERVICE_NAME}..."
        sudo systemctl restart ${SERVICE_NAME}
        sudo systemctl status ${SERVICE_NAME} --no-pager
        ;;
    status)
        sudo systemctl status ${SERVICE_NAME} --no-pager
        ;;
    logs)
        sudo journalctl -u ${SERVICE_NAME} -n 100 --no-pager
        ;;
    logs-follow)
        sudo journalctl -u ${SERVICE_NAME} -f
        ;;
    uninstall)
        echo "Uninstalling ${SERVICE_NAME} service..."
        sudo systemctl stop ${SERVICE_NAME}
        sudo systemctl disable ${SERVICE_NAME}
        sudo rm /etc/systemd/system/noggin-web.service
        sudo systemctl daemon-reload
        echo "Service uninstalled"
        ;;
    *)
        echo "Usage: $0 {install|start|stop|restart|status|logs|logs-follow|uninstall}"
        exit 1
        ;;
esac
