#!/bin/bash
# Container Escape Trainer - Redaction Checker Daemon
# Monitors for flag10_report.json and verifies credit card redaction

# Function to calculate elapsed time
get_elapsed_time() {
    if [ -f /tmp/start.time ]; then
        start_time=$(cat /tmp/start.time)
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))
        
        minutes=$((elapsed / 60))
        seconds=$((elapsed % 60))
        
        printf "%dm%02ds" $minutes $seconds
    else
        echo "unknown"
    fi
}

# Main monitoring loop
echo "[checkredact] Daemon started - monitoring for flag10_report.json..."

while true; do
    # Check if the report file exists in multiple possible locations
    report_found=false
    report_path=""
    
    # Check possible locations
    for path in "/host/flag10_report.json" "/flag10_report.json" "/tmp/flag10_report.json" "/home/escape/flag10_report.json"; do
        if [ -f "$path" ]; then
            report_found=true
            report_path="$path"
            break
        fi
    done
    
    if [ "$report_found" = true ]; then
        echo "[checkredact] Found report at: $report_path"
        
        # Check if the credit card number is still visible (NOT redacted)
        if grep -q "4444-4444-4444-4444" "$report_path"; then
            echo "❌ Credit card still visible in report - redaction FAILED"
            echo "[checkredact] The card number 4444-4444-4444-4444 must be masked/redacted"
            echo "[checkredact] Please run redact.exe again to properly mask the sensitive data"
        else
            # SUCCESS! Credit card has been redacted
            elapsed=$(get_elapsed_time)
            
            echo ""
            echo "╔══════════════════════════════════════════════════════════════════╗"
            echo "║                                                                  ║"
            echo "║  🎯  FLAG REDACTED - CTF PASS 10/10  🎯                         ║"
            echo "║                                                                  ║"
            echo "╚══════════════════════════════════════════════════════════════════╝"
            echo ""
            echo "  ✅ Credit card successfully masked!"
            echo "  ⏱️  Time: $elapsed"
            echo "  🏆 Challenge completed!"
            echo ""
            echo "═══════════════════════════════════════════════════════════════════"
            echo ""
            echo "🎓 Congratulations! You have successfully:"
            echo "   1. ✓ Escaped the container using one or more of 10 techniques"
            echo "   2. ✓ Located the sensitive flag file"
            echo "   3. ✓ Used Privacy-OCR to redact the credit card"
            echo "   4. ✓ Passed the automatic validation"
            echo ""
            echo "💼 Skills demonstrated:"
            echo "   • Container security assessment"
            echo "   • Privilege escalation techniques"
            echo "   • Data privacy and redaction"
            echo "   • Security best practices"
            echo ""
            echo "═══════════════════════════════════════════════════════════════════"
            echo ""
            
            exit 0
        fi
    fi
    
    # Wait before checking again
    sleep 3
done
