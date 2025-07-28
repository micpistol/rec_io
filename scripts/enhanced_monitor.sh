#!/bin/bash

echo "📊 ENHANCED SYSTEM MONITOR"
echo "=========================="

# CPU and Memory by service
echo "🔧 SERVICE-SPECIFIC METRICS:"
supervisorctl -c backend/supervisord.conf status | while read line; do
    service=$(echo $line | awk '{print $1}')
    if [[ $service != "active_trade_supervisor" && $service != "" ]]; then
        echo "  $service:"
        ps aux | grep $service | grep -v grep | awk '{print "    CPU: " $3 "%  MEM: " $4 "%"}'
    fi
done

echo ""
echo "💾 DATABASE PERFORMANCE:"
for db in $(find backend/data -name "*.db"); do
    size=$(ls -lh $db | awk '{print $5}')
    echo "  $(basename $db): $size"
done

echo ""
echo "🌐 NETWORK CONNECTIONS:"
if command -v netstat &> /dev/null; then
    netstat -an | grep -E "(3000|4000|8001)" | wc -l | awk '{print "  Active connections: " $1}'
else
    echo "  netstat not available"
fi

echo ""
echo "📁 STORAGE ANALYSIS:"
echo "  Logs directory: $(du -sh logs/ | awk '{print $1}')"
echo "  Data directory: $(du -sh backend/data/ | awk '{print $1}')"

echo ""
echo "🔍 CRITICAL FILES STATUS:"
critical_files=(
    "backend/core/config/config.json"
    "backend/core/config/MASTER_PORT_MANIFEST.json"
    "backend/data/trade_history/trades.db"
    "backend/data/active_trades/active_trades.db"
)

for file in "${critical_files[@]}"; do
    if [ -f "$file" ]; then
        size=$(ls -lh "$file" | awk '{print $5}')
        echo "  ✅ $(basename $file): $size"
    else
        echo "  ❌ $(basename $file): Missing"
    fi
done

echo ""
echo "⚡ PERFORMANCE SUMMARY:"
echo "  - Total Python processes: $(ps aux | grep python | grep -v grep | wc -l)"
echo "  - Supervisor services: $(supervisorctl -c backend/supervisord.conf status | wc -l)"
echo "  - Database files: $(find backend/data -name "*.db" | wc -l)"

echo ""
echo "✅ Enhanced monitoring complete" 