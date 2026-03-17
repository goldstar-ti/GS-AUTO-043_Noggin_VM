#!/bin/bash

# Unified Noggin Service Management Script
# Manages noggin-web and noggin-processor services

set -euo pipefail

# Service definitions
declare -A SERVICES=(
    [noggin-web]="noggin-web"
    [noggin-processor]="noggin-processor"
)

declare -A SERVICE_PORTS=(
    [noggin-web]="5000"
)

# Colour codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Colour

# Helper functions

check_service_exists() {
    local service=$1
    if ! systemctl list-unit-files | grep -q "^${service}.service"; then
        echo -e "${RED}Error: Service ${service} not found${NC}"
        exit 1
    fi
}

check_port() {
    local port=$1
    timeout 2 bash -c "cat < /dev/null > /dev/tcp/localhost/${port}" 2>/dev/null
    return $?
}

get_service_info() {
    local service=$1
    local status=$(systemctl show ${service} --property=ActiveState --value)
    local sub_state=$(systemctl show ${service} --property=SubState --value)
    local uptime=$(systemctl show ${service} --property=ActiveEnterTimestamp --value)
    local memory=$(systemctl show ${service} --property=MemoryCurrent --value)
    local pid=$(systemctl show ${service} --property=MainPID --value)
    
    # Calculate uptime
    local uptime_seconds=0
    if [[ -n "$uptime" && "$uptime" != "n/a" ]]; then
        local enter_timestamp=$(date -d "$uptime" +%s 2>/dev/null || echo 0)
        local current_timestamp=$(date +%s)
        uptime_seconds=$((current_timestamp - enter_timestamp))
    fi
    
    local uptime_formatted="0s"
    if [[ $uptime_seconds -gt 0 ]]; then
        local days=$((uptime_seconds / 86400))
        local hours=$(((uptime_seconds % 86400) / 3600))
        local minutes=$(((uptime_seconds % 3600) / 60))
        
        if [[ $days -gt 0 ]]; then
            uptime_formatted="${days}d ${hours}h ${minutes}m"
        elif [[ $hours -gt 0 ]]; then
            uptime_formatted="${hours}h ${minutes}m"
        else
            uptime_formatted="${minutes}m"
        fi
    fi
    
    # Format memory
    local memory_formatted="0M"
    if [[ "$memory" != "[not set]" && "$memory" -gt 0 ]]; then
        memory_formatted="$(awk "BEGIN {printf \"%.1fM\", ${memory}/1024/1024}")"
    fi
    
    echo "${status}|${sub_state}|${uptime_formatted}|${memory_formatted}|${pid}"
}

get_recent_errors() {
    local service=$1
    local count=${2:-5}
    sudo journalctl -u ${service} -p err -n ${count} --no-pager --output=short-iso 2>/dev/null | grep -v "^--" || echo "No recent errors"
}

# Command implementations

cmd_start() {
    local service=$1
    echo "Starting ${service}..."
    sudo systemctl start ${service}
    sudo systemctl status ${service} --no-pager -l
}

cmd_stop() {
    local service=$1
    echo "Stopping ${service}..."
    sudo systemctl stop ${service}
    sudo systemctl status ${service} --no-pager -l
}

cmd_restart() {
    local service=$1
    echo "Restarting ${service}..."
    sudo systemctl restart ${service}
    sudo systemctl status ${service} --no-pager -l
}

cmd_status() {
    local service=$1
    sudo systemctl status ${service} --no-pager -l
}

cmd_enable() {
    local service=$1
    echo "Enabling ${service} to start on boot..."
    sudo systemctl enable ${service}
    sudo systemctl status ${service} --no-pager -l
}

cmd_disable() {
    local service=$1
    echo "Disabling ${service} from starting on boot..."
    sudo systemctl disable ${service}
}

cmd_logs() {
    local service=$1
    local lines=${2:-50}
    echo "Showing last ${lines} log entries for ${service}..."
    sudo journalctl -u ${service} -n ${lines} --no-pager
}

cmd_follow() {
    local service=$1
    echo "Following logs for ${service} (Ctrl+C to exit)..."
    sudo journalctl -u ${service} -f
}

cmd_reload() {
    echo "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    echo "Daemon reloaded"
}

cmd_errors() {
    local service=$1
    local lines=${2:-50}
    echo "Showing last ${lines} error/critical log entries for ${service}..."
    sudo journalctl -u ${service} -p err -n ${lines} --no-pager
}

cmd_errors_priority() {
    local service=$1
    echo "Select log priority level:"
    echo "  0) Emergency"
    echo "  1) Alert"
    echo "  2) Critical"
    echo "  3) Error"
    echo "  4) Warning"
    echo "  5) Notice"
    echo "  6) Info"
    echo "  7) Debug"
    read -p "Enter priority (0-7): " priority
    
    if [[ ! "$priority" =~ ^[0-7]$ ]]; then
        echo -e "${RED}Invalid priority${NC}"
        exit 1
    fi
    
    echo "Showing logs with priority ${priority} and higher for ${service}..."
    sudo journalctl -u ${service} -p ${priority} -n 50 --no-pager
}

cmd_logs_time() {
    local service=$1
    local days=$2
    echo "Showing logs from the past ${days} day(s) for ${service}..."
    sudo journalctl -u ${service} --since "${days} days ago" --no-pager
}

cmd_dependencies() {
    local service=$1
    echo "Dependencies for ${service}:"
    systemctl list-dependencies ${service} --no-pager
}

cmd_environment() {
    local service=$1
    echo "Environment variables for ${service}:"
    sudo systemctl show ${service} --property=Environment --no-pager
    echo ""
    echo "Environment files:"
    sudo systemctl show ${service} --property=EnvironmentFiles --no-pager
}

cmd_health() {
    local service=$1
    
    # Check service status
    local status=$(systemctl show ${service} --property=ActiveState --value)
    
    if [[ "$status" != "active" ]]; then
        echo -e "${RED}UNHEALTHY: Service is ${status}${NC}"
        return 1
    fi
    
    # Service-specific health checks
    case "$service" in
        noggin-web)
            local port=${SERVICE_PORTS[$service]}
            if check_port $port; then
                echo -e "${GREEN}HEALTHY: Service is active and port ${port} is accepting connections${NC}"
                return 0
            else
                echo -e "${RED}UNHEALTHY: Service is active but port ${port} is not responding${NC}"
                return 1
            fi
            ;;
        noggin-processor)
            echo -e "${YELLOW}Health check not implemented for ${service}${NC}"
            return 0
            ;;
        *)
            echo -e "${YELLOW}No health check defined for ${service}${NC}"
            return 0
            ;;
    esac
}

cmd_dashboard() {
    echo "======================"
    echo "Noggin Services Status"
    echo "======================"
    echo ""
    echo ""
    
    for service in noggin-web noggin-processor; do
        if ! systemctl list-unit-files | grep -q "^${service}.service"; then
            echo "${service}: Not installed"
            continue
        fi
        
        local info=$(get_service_info ${service})
        IFS='|' read -r status sub_state uptime memory pid <<< "$info"
        
        # Determine display status
        local display_status="${status} (${sub_state})"
        local status_colour=$NC
        if [[ "$status" == "active" ]]; then
            status_colour=$GREEN
        elif [[ "$status" == "failed" ]]; then
            status_colour=$RED
        else
            status_colour=$YELLOW
        fi
        
        # Display service info
        echo -e "${BLUE}${service}${NC}"
        printf "  Status:  ${status_colour}%-20s${NC}\n" "${display_status}"
        printf "  Uptime:  %-20s\n" "${uptime}"
        printf "  Memory:  %-20s\n" "${memory}"
        printf "  PID:     %-20s\n" "${pid}"
        
        # Show recent errors
        echo "  Recent errors:"
        local errors=$(get_recent_errors ${service} 3)
        if [[ "$errors" == "No recent errors" ]]; then
            echo "    None"
        else
            echo "$errors" | sed 's/^/    /'
        fi
        
        # Add blank line between services
        if [[ "$service" == "noggin-web" ]]; then
            echo ""
        fi
    done
    
    echo ""
    echo "Last checked: $(date '+%Y-%m-%d %H:%M:%S')"
}

# Menu display

show_menu() {
    echo ""
    echo "Tip: You can also run commands directly from the command line:"
    echo "    ./manage_services.sh <service> <command>"
    echo "    Example: ./manage_services.sh noggin-web restart"
    echo ""
    echo "Available commands:"
    echo "   start, stop, restart, status, enable, disable,"
    echo "   logs, follow, errors, errors-priority, logs-1d, logs-3d, logs-7d,"
    echo "   dependencies, environment, health, dashboard, reload"
    echo ""
    echo ""
    echo ""
    echo "███╗   ██╗ ██████╗ ██████╗ ██████╗ ██╗███████╗";
    echo "████╗  ██║██╔═══██╗██╔══██╗██╔══██╗██║██╔════╝";
    echo "██╔██╗ ██║██║   ██║██████╔╝██████╔╝██║█████╗  ";
    echo "██║╚██╗██║██║   ██║██╔══██╗██╔══██╗██║██╔══╝  ";
    echo "██║ ╚████║╚██████╔╝██████╔╝██████╔╝██║███████╗";
    echo "╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═════╝ ╚═╝╚══════╝";
    echo ""
    echo ""
    echo "N o g g i n   O b j e c t   B i n a r y   B a c k u p   &   I n g e s t i o n   E n g i n e"
    echo ""
    echo "=================="
    echo "Service Management"
    echo "=================="
    echo ""
    
    local index=1
    
    # noggin-web commands
    echo "${index}. noggin-web restart"
    ((index++))
    echo "${index}. noggin-web start"
    ((index++))
    echo "${index}. noggin-web stop"
    ((index++))
    echo "${index}. noggin-web status"
    ((index++))
    echo "${index}. noggin-web logs"
    ((index++))
    echo "${index}. noggin-web follow"
    ((index++))
    echo "${index}. noggin-web errors"
    ((index++))
    echo "${index}. noggin-web health"
    ((index++))
    
    echo ""
    
    # noggin-processor commands
    echo "${index}. noggin-processor start"
    ((index++))
    echo "${index}. noggin-processor stop"
    ((index++))
    echo "${index}. noggin-processor restart"
    ((index++))
    echo "${index}. noggin-processor status"
    ((index++))
    echo "${index}. noggin-processor logs"
    ((index++))
    echo "${index}. noggin-processor follow"
    ((index++))
    echo "${index}. noggin-processor errors"
    ((index++))
    
    echo ""
    
    # Common commands
    echo "${index}. dashboard"
    ((index++))
    echo "${index}. reload (daemon)"
    ((index++))
}

execute_menu_choice() {
    local choice=$1
    
    case $choice in
        1) cmd_restart "noggin-web" ;;
        2) cmd_start "noggin-web" ;;
        3) cmd_stop "noggin-web" ;;
        4) cmd_status "noggin-web" ;;
        5) cmd_logs "noggin-web" ;;
        6) cmd_follow "noggin-web" ;;
        7) cmd_errors "noggin-web" ;;
        8) cmd_health "noggin-web" ;;
        9) cmd_start "noggin-processor" ;;
        10) cmd_stop "noggin-processor" ;;
        11) cmd_restart "noggin-processor" ;;
        12) cmd_status "noggin-processor" ;;
        13) cmd_logs "noggin-processor" ;;
        14) cmd_follow "noggin-processor" ;;
        15) cmd_errors "noggin-processor" ;;
        16) cmd_dashboard ;;
        17) cmd_reload ;;
        *) echo -e "${RED}Invalid choice${NC}"; exit 1 ;;
    esac
}

# Main execution

main() {
    # Menu mode - no arguments
    if [[ $# -eq 0 ]]; then
        show_menu
        read -p "Enter choice: " choice
        execute_menu_choice "$choice"
        exit 0
    fi
    
    # CLI mode
    local service=$1
    local command=${2:-status}
    
    # Special commands that don't require a service
    if [[ "$service" == "dashboard" ]]; then
        cmd_dashboard
        exit 0
    elif [[ "$service" == "reload" ]]; then
        cmd_reload
        exit 0
    fi
    
    # Validate service
    if [[ ! -v SERVICES[$service] ]]; then
        echo -e "${RED}Error: Unknown service '${service}'${NC}"
        echo "Available services: ${!SERVICES[@]}"
        exit 1
    fi
    
    local service_name=${SERVICES[$service]}
    check_service_exists "$service_name"
    
    # Execute command
    case "$command" in
        restart) cmd_restart "$service_name" ;;
        start) cmd_start "$service_name" ;;
        stop) cmd_stop "$service_name" ;;
        status) cmd_status "$service_name" ;;
        enable) cmd_enable "$service_name" ;;
        disable) cmd_disable "$service_name" ;;
        logs) cmd_logs "$service_name" ;;
        follow) cmd_follow "$service_name" ;;
        reload) cmd_reload ;;
        errors) cmd_errors "$service_name" ;;
        errors-priority) cmd_errors_priority "$service_name" ;;
        logs-1d) cmd_logs_time "$service_name" 1 ;;
        logs-3d) cmd_logs_time "$service_name" 3 ;;
        logs-7d) cmd_logs_time "$service_name" 7 ;;
        dependencies) cmd_dependencies "$service_name" ;;
        environment) cmd_environment "$service_name" ;;
        health) cmd_health "$service_name" ;;
        dashboard) cmd_dashboard ;;
        *)
            echo -e "${RED}Error: Unknown command '${command}'${NC}"
            echo "Available commands: start, stop, restart, status, enable, disable,logs, follow, errors, errors-priority, logs-1d, logs-3d, logs-7d,dependencies, environment, health, dashboard, reload"
            exit 1
            ;;
    esac
}

main "$@"