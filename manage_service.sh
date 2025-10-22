#!/bin/bash

SERVICE_NAME="noggin-processor"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

case "$1" in
    start)
        echo "Starting $SERVICE_NAME service..."
        sudo systemctl start $SERVICE_NAME
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    stop)
        echo "Stopping $SERVICE_NAME service..."
        sudo systemctl stop $SERVICE_NAME
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    restart)
        echo "Restarting $SERVICE_NAME service..."
        sudo systemctl restart $SERVICE_NAME
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    status)
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    enable)
        echo "Enabling $SERVICE_NAME to start on boot..."
        sudo systemctl enable $SERVICE_NAME
        sudo systemctl status $SERVICE_NAME --no-pager
        ;;
    disable)
        echo "Disabling $SERVICE_NAME from starting on boot..."
        sudo systemctl disable $SERVICE_NAME
        ;;
    logs)
        echo "Showing recent logs for $SERVICE_NAME..."
        sudo journalctl -u $SERVICE_NAME -n 50 --no-pager
        ;;
    follow)
        echo "Following logs for $SERVICE_NAME (Ctrl+C to exit)..."
        sudo journalctl -u $SERVICE_NAME -f
        ;;
    reload)
        echo "Reloading systemd daemon..."
        sudo systemctl daemon-reload
        echo "Daemon reloaded"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|enable|disable|logs|follow|reload}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the service"
        echo "  stop    - Stop the service"
        echo "  restart - Restart the service"
        echo "  status  - Show service status"
        echo "  enable  - Enable service to start on boot"
        echo "  disable - Disable service from starting on boot"
        echo "  logs    - Show recent logs"
        echo "  follow  - Follow logs in real-time"
        echo "  reload  - Reload systemd daemon (after editing service file)"
        exit 1
        ;;
esac

exit 0