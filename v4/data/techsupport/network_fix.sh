#!/bin/bash
case "$1" in
    check_dns)
        echo "✅ DNS Resolution: OK"
        ;;
    reset_interface)
        echo "🔄 Resetting interface: eth0... (Simulated)"
        ;;
    *)
        echo "Unknown operation: $1"
        exit 1
        ;;
esac
