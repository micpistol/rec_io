
// === ACTIVE TRADE SUPERVISOR MANAGER ===
// This module handles the Active Trade Supervisor table creation, updates, and maintenance
// Pulls data directly from active_trades.db via the active_trade_supervisor service

// Global active trade supervisor state
window.activeTradeSupervisorRowsMap = new Map();

// Wait for port configuration to load before initializing
async function waitForPortConfig() {
    let attempts = 0;
    const maxAttempts = 50; // 5 seconds with 100ms intervals
    
    while (attempts < maxAttempts) {
        try {
            // Check if port configuration is loaded
            if (typeof getActiveTradeSupervisorUrl === 'function') {
                // Test if the function works
                getActiveTradeSupervisorUrl('/test');
                return true;
            }
        } catch (error) {
            // Port config not ready yet
        }
        
        await new Promise(resolve => setTimeout(resolve, 100));
        attempts++;
    }
    
    console.warn('[ACTIVE TRADE SUPERVISOR] Port configuration not loaded after 5 seconds, using fallback');
    return false;
}

// === ACTIVE TRADE SUPERVISOR INITIALIZATION ===

function initializeActiveTradeSupervisorTable() {
  const activeTradeSupervisorTableBody = document.querySelector('#activeTradeSupervisorTable tbody');
  if (!activeTradeSupervisorTableBody) {
    console.error('[ACTIVE TRADE SUPERVISOR] Active trade supervisor table body not found');
    return;
  }
  
  // Clear existing content
  activeTradeSupervisorTableBody.innerHTML = '';
  window.activeTradeSupervisorRowsMap.clear();
  
}

// === ACTIVE TRADE SUPERVISOR UPDATE LOGIC ===

async function fetchAndRenderActiveTradeSupervisorTrades() {
  try {
    
    // Get the active trade supervisor service URL
    let activeTradeSupervisorUrl;
    try {
      activeTradeSupervisorUrl = getActiveTradeSupervisorUrl('/api/active_trades');
    } catch (error) {
      console.error('[ACTIVE TRADE SUPERVISOR] Port configuration error:', error);
      // Fallback to hardcoded URL
      activeTradeSupervisorUrl = 'http://localhost:8007/api/active_trades';
    }
    
    // Fetch active trades from the supervisor service
    const response = await fetch(activeTradeSupervisorUrl, { cache: 'no-store' });
    
    if (!response.ok) {
      console.error('[ACTIVE TRADE SUPERVISOR] Failed to fetch active trades:', response.status);
      return;
    }
    
    const data = await response.json();
    
    if (!data.active_trades || !Array.isArray(data.active_trades)) {
      console.error('[ACTIVE TRADE SUPERVISOR] Invalid data format:', data);
      return;
    }
    
    // Render the trades
    renderActiveTradeSupervisorTrades(data.active_trades);
    
  } catch (error) {
    console.error('[ACTIVE TRADE SUPERVISOR] Error fetching trades:', error);
  }
}

// === RENDER FUNCTION ===

function renderActiveTradeSupervisorTrades(activeTrades) {
  
  const activeTradeSupervisorTableBody = document.querySelector('#activeTradeSupervisorTable tbody');
  if (!activeTradeSupervisorTableBody) {
    console.error('[ACTIVE TRADE SUPERVISOR] Table body not found!');
    return;
  }
  
  // Remove rows for trades that no longer exist
  const activeTradeIds = new Set(activeTrades.map(trade => trade.trade_id));
  
  for (const [tradeId, rowObj] of window.activeTradeSupervisorRowsMap.entries()) {
    if (!activeTradeIds.has(tradeId)) {
      if (rowObj.tr && rowObj.tr.parentNode === activeTradeSupervisorTableBody) {
        activeTradeSupervisorTableBody.removeChild(rowObj.tr);
      }
      window.activeTradeSupervisorRowsMap.delete(tradeId);
    }
  }

  // Remove all existing spanner rows before rendering trade rows
  activeTradeSupervisorTableBody.querySelectorAll('.spanner-row').forEach(row => row.remove());

  // Render each active trade
  activeTrades.forEach((trade, idx) => {
    const tradeId = trade.trade_id;
    
    // Check if we already have a row for this trade
    let rowObj = window.activeTradeSupervisorRowsMap.get(tradeId);
    
    if (!rowObj) {
      const row = document.createElement("tr");
      
      // Strike
      const strikeCell = document.createElement("td");
      strikeCell.textContent = trade.strike;
      row.appendChild(strikeCell);
      
      // Side
      const sideCell = document.createElement("td");
      sideCell.textContent = trade.side;
      row.appendChild(sideCell);
      
      // Buy (price)
      const priceCell = document.createElement("td");
      priceCell.textContent = (typeof trade.buy_price === "number")
        ? trade.buy_price.toFixed(2)
        : trade.buy_price;
      row.appendChild(priceCell);
      
      // Position
      const posCell = document.createElement("td");
      posCell.textContent = trade.position ?? "";
      row.appendChild(posCell);
      
      // Buffer (from active_trades.db)
      const bufferCell = document.createElement("td");
      if (trade.buffer_from_entry !== null) {
        const buffer = trade.buffer_from_entry;
        bufferCell.textContent = buffer.toLocaleString(undefined, {maximumFractionDigits: 0});
        
        // Apply risk color classes based on buffer
        if (Math.abs(buffer) >= 300) row.classList.add('ultra-safe');
        else if (Math.abs(buffer) >= 200) row.classList.add('safe');
        else if (Math.abs(buffer) >= 100) row.classList.add('caution');
        else if (Math.abs(buffer) >= 50) row.classList.add('high-risk');
        else row.classList.add('danger-stop');
      } else {
        bufferCell.textContent = "N/A";
      }
      row.appendChild(bufferCell);
      
      // Probability (from active_trades.db)
      const probCell = document.createElement("td");
      if (trade.current_probability !== null) {
        probCell.textContent = `${trade.current_probability.toFixed(1)}%`;
      } else {
        probCell.textContent = "N/A";
      }
      row.appendChild(probCell);
      
      // Close button with PnL display
      const closeCell = document.createElement("td");
      closeCell.style.textAlign = "center";
      const closeSpan = document.createElement("span");
      closeSpan.className = "price-box";
      closeSpan.dataset.tradeId = trade.trade_id;
      closeSpan.dataset.action = "close";
      closeSpan.style.cursor = "pointer";
      closeSpan.onclick = () => closeActiveTrade(trade.trade_id, trade.ticket_id);
      const innerDiv = document.createElement("div");
      
      // Display PnL if available, otherwise show "Close"
      if (trade.current_pnl !== null && trade.current_pnl !== undefined) {
        const pnl = parseFloat(trade.current_pnl);
        if (!isNaN(pnl)) {
          // Format PnL with white text
          const pnlText = pnl >= 0 ? `+${pnl.toFixed(2)}` : pnl.toFixed(2);
          innerDiv.textContent = pnlText;
          innerDiv.style.color = "white";
        } else {
          innerDiv.textContent = "Close";
          innerDiv.style.color = "white";
        }
      } else {
        innerDiv.textContent = "Close";
        innerDiv.style.color = "white";
      }
      
      closeSpan.appendChild(innerDiv);
      closeCell.appendChild(closeSpan);
      row.appendChild(closeCell);
      
      // Store the row object
      rowObj = { tr: row };
      window.activeTradeSupervisorRowsMap.set(tradeId, rowObj);
      
      // Add the row to the table
      activeTradeSupervisorTableBody.appendChild(row);
    } else {
      // Update existing row with new data
      const row = rowObj.tr;
      const cells = row.querySelectorAll('td');
      
      // Update buffer
      if (cells.length > 4 && trade.buffer_from_entry !== null) {
        const buffer = trade.buffer_from_entry;
        cells[4].textContent = buffer.toLocaleString(undefined, {maximumFractionDigits: 0});
        
        // Update risk color classes
        row.classList.remove('ultra-safe', 'safe', 'caution', 'high-risk', 'danger-stop');
        if (Math.abs(buffer) >= 300) row.classList.add('ultra-safe');
        else if (Math.abs(buffer) >= 200) row.classList.add('safe');
        else if (Math.abs(buffer) >= 100) row.classList.add('caution');
        else if (Math.abs(buffer) >= 50) row.classList.add('high-risk');
        else row.classList.add('danger-stop');
      }
      
      // Update probability
      if (cells.length > 5 && trade.current_probability !== null) {
        cells[5].textContent = `${trade.current_probability.toFixed(1)}%`;
      }
      
      // Update PnL on close button
      if (cells.length > 6 && trade.current_pnl !== null && trade.current_pnl !== undefined) {
        const closeButton = cells[6].querySelector('.price-box div');
        if (closeButton) {
          const pnl = parseFloat(trade.current_pnl);
          if (!isNaN(pnl)) {
            const pnlText = pnl >= 0 ? `+${pnl.toFixed(2)}` : pnl.toFixed(2);
            closeButton.textContent = pnlText;
            closeButton.style.color = "white";
          } else {
            closeButton.textContent = "Close";
            closeButton.style.color = "white";
          }
        }
      }
    }
  });

  // Add spanner row if no trades
  if (activeTrades.length === 0) {
    const spannerRow = document.createElement("tr");
    spannerRow.className = "spanner-row";
    const spannerCell = document.createElement("td");
    spannerCell.colSpan = 7;
    spannerCell.textContent = "No active trades";
    spannerRow.appendChild(spannerCell);
    activeTradeSupervisorTableBody.appendChild(spannerRow);
  }

}

// === CLOSE TRADE FUNCTION ===

async function closeActiveTrade(tradeId, ticketId) {
  try {
    console.log('[ACTIVE TRADE SUPERVISOR] Attempting to close trade:', tradeId);
    
    // Use the centralized closeTrade function from the trade execution controller
    if (typeof window.closeTrade === 'function') {
      // Get current BTC price for sell price
      const currentPrice = typeof getCurrentBTCTickerPrice === 'function' ? getCurrentBTCTickerPrice() : 0.5;
      console.log('[ACTIVE TRADE SUPERVISOR] Current price for close:', currentPrice);
      
      // Create a mock event object since we don't have the actual event
      const mockEvent = {
        target: document.createElement('button'),
        preventDefault: () => {},
        stopPropagation: () => {}
      };
      
      // Call the centralized close trade function - let it handle all notifications
      console.log('[ACTIVE TRADE SUPERVISOR] Calling window.closeTrade with:', { tradeId, currentPrice });
      await window.closeTrade(tradeId, currentPrice, mockEvent);
      console.log('[ACTIVE TRADE SUPERVISOR] Close trade call completed');
    } else {
      console.error('[ACTIVE TRADE SUPERVISOR] Centralized closeTrade function not available');
    }
  } catch (error) {
    console.error(`[ACTIVE TRADE SUPERVISOR] Error closing trade ${tradeId}:`, error);
  }
}



// === AUTO REFRESH SETUP ===

function startActiveTradeSupervisorRefresh() {
  // Initial load
  fetchAndRenderActiveTradeSupervisorTrades();
  
  // Set up periodic refresh (every 5 seconds - REDUCED to prevent resource exhaustion)
  setInterval(() => {
    fetchAndRenderActiveTradeSupervisorTrades();
  }, 5000);
}

// === INITIALIZATION ===

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
  
      // Wait for port configuration to load
    const portConfigReady = await waitForPortConfig();
    
    initializeActiveTradeSupervisorTable();
    startActiveTradeSupervisorRefresh();
});

// Also try immediate initialization if DOM is already ready
if (document.readyState === 'loading') {
  // DOM still loading, waiting for DOMContentLoaded...
} else {
  // DOM already ready, initializing immediately...
  
  // Wait for port configuration to load
  waitForPortConfig().then(() => {
    initializeActiveTradeSupervisorTable();
    startActiveTradeSupervisorRefresh();
  });
}

// Export functions for global access
window.fetchAndRenderActiveTradeSupervisorTrades = fetchAndRenderActiveTradeSupervisorTrades;
window.closeActiveTrade = closeActiveTrade; 
