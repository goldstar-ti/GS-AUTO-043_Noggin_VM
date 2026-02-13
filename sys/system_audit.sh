#!/bin/bash

OUTPUT_FILE="system_context.txt"

# Clear the file first
> "$OUTPUT_FILE"

echo "Generating system audit for NotebookLM..."

{
    echo "=========================================="
    echo " SYSTEM CONTEXT REPORT"
    echo "=========================================="
    echo "Generated on: $(date)"
    echo ""

    echo "### 1. OPERATING SYSTEM DETAILS"
    echo "--------------------------------"
    # Get standard OS release info
    if [ -f /etc/os-release ]; then
        cat /etc/os-release | grep -E 'PRETTY_NAME|VERSION_ID'
    fi
    echo "Kernel: $(uname -sr)"
    echo "Architecture: $(uname -m)"
    echo ""

    echo "### 2. PYTHON ENVIRONMENT"
    echo "--------------------------------"
    # Check for python3 specifically
    if command -v python3 &> /dev/null; then
        echo "Python Executable: $(which python3)"
        echo "Python Version: $(python3 --version)"
    else
        echo "WARNING: python3 not found in PATH."
    fi
    echo ""

    echo "### 3. INSTALLED PACKAGES (pip freeze)"
    echo "--------------------------------"
    # Only run if pip is available
    if command -v pip3 &> /dev/null; then
        pip3 freeze
    else
        echo "pip3 command not found."
    fi
    echo ""

    echo "### 4. RELEVANT ENVIRONMENT VARIABLES"
    echo "--------------------------------"
    # We filter for relevant vars to avoid noise (like LS_COLORS)
    printenv | grep -E 'PYTHON|PATH|LANG|VIRTUAL_ENV|SHELL' | sort
    echo ""

    echo "### 5. HARDWARE RESOURCE OVERVIEW"
    echo "--------------------------------"
    # Quick check of memory and disk space
    free -h | grep "Mem:" | awk '{print "Total Memory: " $2}'
    df -h / | tail -1 | awk '{print "Disk Space (/): " $2 " Total, " $4 " Free"}'

} >> "$OUTPUT_FILE"

echo "Done! created $OUTPUT_FILE"
echo "You can now upload $OUTPUT_FILE along with your Repomix output."