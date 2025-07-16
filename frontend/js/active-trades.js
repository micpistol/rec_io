// === ACTIVE TRADES MANAGER ===
// This module handles all active trades table creation, updates, and maintenance

// Global active trades state
window.activeTradesRowsMap = new Map();
const previousClosePrices = {}; // Keyed by trade.id
const lastCloseButtonStates = new Map(); // Keyed by trade.id

// === ACTIVE TRADES INITIALIZATION ===

function initializeActiveTradesTable() {
  const activeTradesTableBody = document.querySelector('#activeTradesTable tbody');
  if (!activeTradesTableBody) {
    console.error('[ACTIVE TRADES MANAGER] Active trades table body not found');
    return;
  }
  
  // Clear existing content
  activeTradesTableBody.innerHTML = '';
  window.activeTradesRowsMap.clear();
  
  console.log('[ACTIVE TRADES MANAGER] Active trades table initialized');
}

// === ACTIVE TRADES UPDATE LOGIC ===

async function fetchAndRenderTrades() {
  try {
    // Fetch all trades (all statuses) from backend
    const tradesRes = await fetch('/trades', { cache: 'no-store' });
    if (!tradesRes.ok) throw new Error("Failed to fetch trades");
    let trades = await tradesRes.json();
    // Only show trades whose status is not "closed" or "expired"
    trades = trades.filter(trade =>
      trade.status !== "closed" && trade.status !== "expired"
    );

    // Fetch core data and markets snapshot concurrently
    const [coreRes, marketsRes] = await Promise.all([
      fetch('/core'),
      fetch('/kalshi_market_snapshot')
    ]);
    if (!coreRes.ok || !marketsRes.ok) throw new Error("Failed to fetch core or markets data");
    const coreData = await coreRes.json();
    const marketsData = await marketsRes.json();
    const latestKalshiMarkets = Array.isArray(marketsData.markets) ? marketsData.markets : [];

    // Small delay to ensure strike table DOM is updated before reading from it
    await new Promise(resolve => setTimeout(resolve, 50));

    const ttcSeconds = coreData.ttc_seconds || 1;
    const ttcMinutes = ttcSeconds / 60;

    // Build a map of trade.id to trade for quick lookup
    const tradeIdSet = new Set(trades.map(trade => trade.id));

    // Remove rows for trades that no longer exist
    const activeTradesTableBody = document.querySelector('#activeTradesTable tbody');
    for (const [tradeId, rowObj] of window.activeTradesRowsMap.entries()) {
      if (!tradeIdSet.has(tradeId)) {
        if (rowObj.tr && rowObj.tr.parentNode === activeTradesTableBody) {
          activeTradesTableBody.removeChild(rowObj.tr);
        }
        window.activeTradesRowsMap.delete(tradeId);
        delete previousClosePrices[tradeId];
      }
    }

    // --- Remove all existing spanner rows before rendering trade rows ---
    activeTradesTableBody.querySelectorAll('.spanner-row').forEach(row => row.remove());

    // --- Sort trades by strike (ascending) for correct row order ---
    trades.sort((a, b) => {
      const strikeA = parseFloat(String(a.strike).replace(/[^\d.-]/g, '')) || 0;
      const strikeB = parseFloat(String(b.strike).replace(/[^\d.-]/g, '')) || 0;
      return strikeA - strikeB;
    });

    // === Prepare to build all rows in an array ===
    const tradeRows = [];
    const currentPrice = coreData.btc_price;
    let spannerIndex = trades.length; // default to end

    // Find the correct index to insert the spanner row
    // The spanner row should be inserted AFTER the last trade whose strike is <= currentPrice
    for (let i = 0; i < trades.length; i++) {
      const strike = parseFloat(String(trades[i].strike).replace(/[^\d.-]/g, '')) || 0;
      if (currentPrice < strike) {
        spannerIndex = i;
        break;
      }
    }

    // Build trade rows (do not append yet)
    trades.forEach((trade, idx) => {
      // --- Remove spanner row logic from here ---
      // Re-render the row if status has changed
      const existing = window.activeTradesRowsMap.get(trade.id);
      if (existing && existing.status !== trade.status) {
        activeTradesTableBody.removeChild(existing.tr);
        window.activeTradesRowsMap.delete(trade.id);
      }
      // === PENDING/ERROR/CLOSING TRADE ROW LOGIC: merge Buffer and B/M into one cell ===
      if (["pending", "error", "closing"].includes(trade.status)) {
        let rowObj = window.activeTradesRowsMap.get(trade.id);
        // Choose color and label
        let bgColor, label, textColor;
        if (trade.status === "pending" || trade.status === "closing") {
          bgColor = "#3b82f6";
          label = trade.status === "pending" ? "PENDING" : "CLOSING";
          textColor = "white";
        } else if (trade.status === "error") {
          bgColor = "#ef4444";
          label = "ERROR";
          textColor = "white";
        }
        if (!rowObj) {
          const row = document.createElement("tr");
          row.style.backgroundColor = bgColor;
          row.style.color = textColor;
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
          posCell.textContent = trade.position ?? trade.quantity ?? "";
          row.appendChild(posCell);
          // Buffer and B/M merged cell
          const statusCell = document.createElement("td");
          statusCell.colSpan = 2;
          statusCell.style.textAlign = "center";
          statusCell.style.fontStyle = "italic";
          statusCell.textContent = label;
          row.appendChild(statusCell);
          // === Replacement: Close column (Cancel button for pending/error/closing trades) ===
          const closeCell = document.createElement("td");
          closeCell.style.textAlign = "center";
          // Create a fresh Cancel button styled as price-box
          const cancelSpan = document.createElement("span");
          cancelSpan.className = "price-box";
          cancelSpan.dataset.tradeId = trade.id;
          cancelSpan.dataset.action = "close";
          cancelSpan.style.cursor = "pointer";
          cancelSpan.onclick = () => cancelTrade(trade.id, trade.ticket_id);
          const innerDiv = document.createElement("div");
          innerDiv.textContent = "Cancel";
          cancelSpan.appendChild(innerDiv);
          closeCell.appendChild(cancelSpan);
          row.appendChild(closeCell);
          rowObj = { tr: row, statusCell, status: trade.status };
          window.activeTradesRowsMap.set(trade.id, rowObj);
        } else {
          rowObj.tr.style.backgroundColor = bgColor;
          rowObj.tr.style.color = textColor;
          rowObj.status = trade.status;
        }
        // --- Add error tooltip logic for "error" status ---
        if (trade.status === "error" && rowObj.statusCell) {
          const statusTd = rowObj.statusCell;
          statusTd.style.cursor = 'help';
          statusTd.classList.add('error-cell');
          const newStatusTd = statusTd.cloneNode(true);
          newStatusTd.textContent = statusTd.textContent;
          newStatusTd.style.cursor = 'help';
          newStatusTd.classList.add('error-cell');
          newStatusTd.addEventListener('mouseenter', async (evt) => {
            try {
              const resp = await fetch(`/api/trade_log/${trade.ticket_id}`);
              const data = await resp.json();
              if (data.status === "ok") {
                showErrorTooltip(data.log, evt.clientX, evt.clientY);
              } else {
                showErrorTooltip("Log not found", evt.clientX, evt.clientY);
              }
            } catch (e) {
              showErrorTooltip('Failed to load trade log.', evt.clientX, evt.clientY);
            }
          });
          newStatusTd.addEventListener('mousemove', (evt) => {
            positionErrorTooltip(evt.clientX, evt.clientY);
          });
          newStatusTd.addEventListener('mouseleave', hideErrorTooltip);
          rowObj.tr.replaceChild(newStatusTd, statusTd);
          rowObj.statusCell = newStatusTd;
        }
        tradeRows.push(rowObj.tr);
        return;
      }

      // === OPEN TRADE ROW LOGIC ===
      const strikeNum = parseFloat(String(trade.strike).replace(/\$|,/g, '')) || 0;
      const isYes = (trade.side || "").toUpperCase() === "Y";
      const priceVal = coreData.btc_price;
      let inTheMoney = false;
      if (isYes) {
        inTheMoney = priceVal >= strikeNum;
      } else {
        inTheMoney = priceVal <= strikeNum;
      }
      const rawBuffer = priceVal - strikeNum;
      let buffer, bm;
      if (inTheMoney) {
        buffer = Math.abs(rawBuffer);
        bm = Math.abs(rawBuffer) / ttcMinutes;
      } else {
        buffer = -Math.abs(rawBuffer);
        bm = -Math.abs(rawBuffer) / ttcMinutes;
      }
      const bufferDisplay = buffer.toLocaleString(undefined, {maximumFractionDigits: 0});
      const bmDisplay = Math.round(bm).toLocaleString();
      let rowClass = '';
      if (Math.abs(buffer) >= 300) rowClass = 'ultra-safe';
      else if (Math.abs(buffer) >= 200) rowClass = 'safe';
      else if (Math.abs(buffer) >= 100) rowClass = 'caution';
      else if (Math.abs(buffer) >= 50) rowClass = 'high-risk';
      else rowClass = 'danger-stop';
      const oppositeSide = (trade.side && trade.side.toUpperCase() === 'Y') ? 'NO' : 'YES';
      const strikeFormatted = '$' + strikeNum.toLocaleString();
      let closeButtonSpan = null;
      const strikeTableRows = document.querySelectorAll('#strike-table tbody tr');
      for (const row of strikeTableRows) {
        const firstTd = row.querySelector('td');
        if (!firstTd) continue;
        const firstTdText = firstTd.textContent.trim();
        if (firstTdText === strikeFormatted) {
          let cellIdx = oppositeSide === 'YES' ? 5 : 6;
          const tds = row.querySelectorAll('td');
          if (tds.length > cellIdx) {
            const span = tds[cellIdx].querySelector('span.price-box, span.price-box.disabled');
            if (span) closeButtonSpan = span;
          }
          break;
        }
      }
      let askPrice = parseFloat(closeButtonSpan?.textContent || 'NaN');
      let isActive = closeButtonSpan && !closeButtonSpan.classList.contains('disabled');
      let rowObj = window.activeTradesRowsMap.get(trade.id);
      if (!rowObj) {
        const tr = document.createElement('tr');
        tr.className = rowClass;
        const strikeTd = document.createElement('td');
        strikeTd.textContent = trade.strike;
        const sideTd = document.createElement('td');
        sideTd.textContent = trade.side;
        const priceTd = document.createElement('td');
        priceTd.textContent = trade.buy_price.toFixed(2);
        const posTd = document.createElement('td');
        posTd.textContent = trade.position;
        const bufferTd = document.createElement('td');
        bufferTd.textContent = bufferDisplay;
        // Get the Prob value from the strike table (column index 3, D)
        let probDisplay = '—';
        let closeAskPrice = null;
        const strikeTableRows = document.querySelectorAll('#strike-table tbody tr');
        for (const row of strikeTableRows) {
          const firstTd = row.querySelector('td');
          if (!firstTd) continue;
          const firstTdText = firstTd.textContent.trim();
          if (firstTdText === strikeFormatted) {
            const tds = row.querySelectorAll('td');
            if (tds.length > 5) {
              probDisplay = tds[3].textContent.trim() || '—';
              // Determine which ask price to use for CLOSE column based on trade.side
              if ((trade.side || '').toUpperCase() === 'Y') {
                closeAskPrice = tds[5].querySelector('span')?.textContent.trim() || 'N/A'; // NO ask
              } else {
                closeAskPrice = tds[4].querySelector('span')?.textContent.trim() || 'N/A'; // YES ask
              }
            }
            break;
          }
        }
        const bmTd = document.createElement('td');
        bmTd.textContent = probDisplay;
        const closeTd = document.createElement('td');
        closeTd.className = 'center';
        if (closeButtonSpan) {
          const clonedSpan = closeButtonSpan.cloneNode(true);
          clonedSpan.classList.remove('disabled');
          clonedSpan.style.opacity = '';
          clonedSpan.style.pointerEvents = '';
          clonedSpan.style.cursor = 'pointer';
          clonedSpan.dataset.tradeId = trade.id;
          clonedSpan.dataset.action = 'close';
          closeTd.appendChild(clonedSpan);
        } else {
          closeTd.textContent = 'N/A';
        }
        tr.appendChild(strikeTd);
        tr.appendChild(sideTd);
        tr.appendChild(priceTd);
        tr.appendChild(posTd);
        tr.appendChild(bufferTd);
        tr.appendChild(bmTd);
        tr.appendChild(closeTd);
        tr.dataset.tradeId = trade.id; // Add trade ID to row for tracking
        rowObj = {
          tr, strikeTd, sideTd, priceTd, posTd, bufferTd, bmTd, closeTd,
          status: trade.status
        };
        window.activeTradesRowsMap.set(trade.id, rowObj);
      } else {
        if (rowObj.tr.className !== rowClass) rowObj.tr.className = rowClass;
        rowObj.tr.style.backgroundColor = "";
        rowObj.status = trade.status;
        // Update buffer
        if (rowObj.bufferTd.textContent !== bufferDisplay) rowObj.bufferTd.textContent = bufferDisplay;
        // Update PROB and CLOSE columns using the correct indices
        let probDisplay = '—';
        let closeButtonSpan = null;
        const strikeTableRows = document.querySelectorAll('#strike-table tbody tr');
        for (const row of strikeTableRows) {
          const firstTd = row.querySelector('td');
          if (!firstTd) continue;
          const firstTdText = firstTd.textContent.trim();
          if (firstTdText === strikeFormatted) {
            const tds = row.querySelectorAll('td');
            if (tds.length > 5) {
              probDisplay = tds[3].textContent.trim() || '—';
              if ((trade.side || '').toUpperCase() === 'Y') {
                closeButtonSpan = tds[5].querySelector('span.price-box, span.price-box.disabled'); // NO ask
              } else {
                closeButtonSpan = tds[4].querySelector('span.price-box, span.price-box.disabled'); // YES ask
              }
            }
            break;
          }
        }
        if (rowObj.bmTd.textContent !== probDisplay) rowObj.bmTd.textContent = probDisplay;
        // Update CLOSE column only if the button's display number changed
        const currentButtonText = closeButtonSpan?.textContent || 'N/A';
        const lastButtonText = lastCloseButtonStates.get(trade.id);
        if (lastButtonText !== currentButtonText) {
          rowObj.closeTd.innerHTML = '';
          if (closeButtonSpan) {
            const clonedSpan = closeButtonSpan.cloneNode(true);
            clonedSpan.classList.remove('disabled');
            clonedSpan.style.opacity = '';
            clonedSpan.style.pointerEvents = '';
            clonedSpan.style.cursor = 'pointer';
            clonedSpan.dataset.tradeId = trade.id;
            clonedSpan.dataset.action = 'close';
            rowObj.closeTd.appendChild(clonedSpan);
          } else {
            rowObj.closeTd.textContent = 'N/A';
          }
          lastCloseButtonStates.set(trade.id, currentButtonText);
        }
      }
      if (!rowObj.tr.parentNode) {
        // Not appending here; will append in batch below
      }
      tradeRows.push(rowObj.tr);
    });

    // Only insert the spanner row if there are open trades
    if (tradeRows.length > 0) {
      // Build the spanner row
      const spannerRow = document.createElement("tr");
      spannerRow.className = "spanner-row";
      const spannerTd = document.createElement("td");
      spannerTd.colSpan = 7;

      // --- Add arrow icons based on momentum score ---
      // Helper to get current momentum score from DOM
      function getCurrentMomentumScoreForArrow() {
        const el = document.getElementById('momentum-score-value');
        if (el && el.textContent) {
          const val = parseFloat(el.textContent.replace(/[^\d\.\-]/g, ''));
          return isNaN(val) ? 0 : val;
        }
        return 0;
      }
      let momentumScore = getCurrentMomentumScoreForArrow();
      // SVGs for straight arrows (no margin)
      const svgDown = `<svg width="16" height="16" style="vertical-align:middle;" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8 2v12M8 14l4-4M8 14l-4-4" stroke="#45d34a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
      const svgUp = `<svg width="16" height="16" style="vertical-align:middle;" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8 14V2M8 2l4 4M8 2l-4 4" stroke="#dc3545" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
      let arrowBlock = '';
      const absMomentum = Math.abs(momentumScore);
      if (absMomentum < 5) {
        arrowBlock = '-';
      } else if (absMomentum < 10) {
        arrowBlock = momentumScore > 0 ? svgDown : svgUp;
      } else if (absMomentum < 20) {
        arrowBlock = (momentumScore > 0 ? svgDown : svgUp).repeat(2);
      } else {
        arrowBlock = (momentumScore > 0 ? svgDown : svgUp).repeat(3);
      }
      spannerTd.innerHTML = `<span style=\"margin:0 12px;display:inline-block;\">${arrowBlock}</span>Current Price: $${Math.round(currentPrice).toLocaleString()}<span style=\"margin:0 12px;display:inline-block;\">${arrowBlock}</span>`;
      spannerRow.appendChild(spannerTd);

      // Insert the spanner row at the correct index
      tradeRows.splice(spannerIndex, 0, spannerRow);
    }

    // Update table efficiently by only changing what's needed
    const existingRows = Array.from(activeTradesTableBody.children);
    
    // Remove spanner rows first
    existingRows.filter(row => row.classList.contains('spanner-row')).forEach(row => row.remove());
    
    // Update or add trade rows
    tradeRows.forEach((newRow, index) => {
      if (newRow.classList.contains('spanner-row')) {
        // Insert spanner row at correct position
        if (index < activeTradesTableBody.children.length) {
          activeTradesTableBody.insertBefore(newRow, activeTradesTableBody.children[index]);
        } else {
          activeTradesTableBody.appendChild(newRow);
        }
      } else {
        // For trade rows, find existing row by trade ID
        const tradeId = newRow.querySelector('[data-trade-id]')?.dataset.tradeId;
        const existingRow = existingRows.find(row => 
          row.querySelector(`[data-trade-id="${tradeId}"]`)
        );
        
        if (existingRow) {
          // Update existing row content without recreating the row
          const newCells = Array.from(newRow.children);
          const existingCells = Array.from(existingRow.children);
          
          for (let i = 0; i < Math.min(newCells.length, existingCells.length); i++) {
            if (existingCells[i].textContent !== newCells[i].textContent) {
              existingCells[i].textContent = newCells[i].textContent;
            }
          }
          
          // Update row class if needed
          if (existingRow.className !== newRow.className) {
            existingRow.className = newRow.className;
          }
        } else {
          // New row, insert it at the correct sorted position
          // Find the correct position to insert based on strike value
          const newStrike = parseFloat(String(newRow.children[0].textContent).replace(/[^\d.-]/g, '')) || 0;
          let insertIndex = activeTradesTableBody.children.length;
          
          for (let i = 0; i < activeTradesTableBody.children.length; i++) {
            const row = activeTradesTableBody.children[i];
            if (row.classList.contains('spanner-row')) continue;
            
            const existingStrike = parseFloat(String(row.children[0].textContent).replace(/[^\d.-]/g, '')) || 0;
            if (newStrike < existingStrike) {
              insertIndex = i;
              break;
            }
          }
          
          if (insertIndex < activeTradesTableBody.children.length) {
            activeTradesTableBody.insertBefore(newRow, activeTradesTableBody.children[insertIndex]);
          } else {
            activeTradesTableBody.appendChild(newRow);
          }
        }
      }
    });
    
    // Remove any old rows that are no longer needed
    const currentTradeIds = tradeRows
      .filter(row => !row.classList.contains('spanner-row'))
      .map(row => row.querySelector('[data-trade-id]')?.dataset.tradeId)
      .filter(Boolean);
    
    existingRows.forEach(row => {
      if (!row.classList.contains('spanner-row')) {
        const rowTradeId = row.querySelector('[data-trade-id]')?.dataset.tradeId;
        if (rowTradeId && !currentTradeIds.includes(rowTradeId)) {
          row.remove();
        }
      }
    });
  } catch (err) {
    console.error('Error fetching trades:', err);
  }
  
}

// === HELPER FUNCTIONS ===

// New async function to close trade by id with current time and BTC price, using sellPrice
async function closeTradeById(tradeId, sellPrice) {
  // Play close trade sound using overlapping playback
  if (typeof playSound === 'function') {
    playSound('close');
  }
  
  // --- All other logic temporarily disabled ---
  /*
  // === Backend: Send trade close request ===
  // const payload = {
  //   status: "closed",
  //   closed_at: new Date().toLocaleTimeString('en-US', {
  //     timeZone: 'America/New_York',
  //     hour12: false,
  //     hour: '2-digit',
  //     minute: '2-digit',
  //     second: '2-digit'
  //   }),
  //   symbol_close: getCurrentBTCTickerPrice(),
  //   sell_price: sellPrice
  // };
  // const res = await fetch(`/trades/${tradeId}`, {
  //   method: 'PUT',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify(payload)
  // });
  // if (!res.ok) throw new Error('Failed to close trade');

  // === DB/UI: Refresh tables ===
  // await fetchAndRenderTrades();
  // await fetchAndRenderRecentTrades();
  // showTradeClosedPopup();
  */
}

// === New function: Close all expired trades (set status to closed and closed_at to current time in NY) ===
async function closeExpiredTrades() {
  try {
    // Fetch all open trades
    const res = await fetch('/trades?status=open', { cache: 'no-store' });
    if (!res.ok) throw new Error("Failed to fetch open trades");
    const openTrades = await res.json();

    // Get current BTC ticker price from DOM element
    const currentPriceEl = document.getElementById('btc-price-value');
    const currentSymbolPrice = currentPriceEl ? parseFloat(currentPriceEl.textContent.replace(/\$|,/g, '')) : null;

    // Loop over each trade and send a close request
    for (const trade of openTrades) {
      const strike = parseFloat(String(trade.strike).replace(/\$|,/g, '')) || 0;
      const isYes = (trade.side || "").toUpperCase() === "Y";
      // Use inclusive logic for win condition at expiration
      const didWin = isYes ? currentSymbolPrice >= strike : currentSymbolPrice <= strike;

      const payload = {
        status: "closed",
        closed_at: new Date().toLocaleTimeString('en-US', {
          timeZone: 'America/New_York',
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        }),
        symbol_close: currentSymbolPrice,
        sell_price: didWin ? 1.00 : 0.00
      };

      const updateRes = await fetch(`/trades/${trade.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!updateRes.ok) {
        console.error(`Failed to close trade ${trade.id}`);
      }
    }

    await fetchAndRenderTrades();
    // Note: fetchAndRenderRecentTrades is handled by the main trade monitor
  } catch (err) {
    console.error("Error in closeExpiredTrades:", err);
  }
}

// === EVENT HANDLERS ===

// --- Debounce mechanism for close trade clicks ---
const lastCloseClickTimes = {};
const DEBOUNCE_DELAY_MS = 300;

// --- Delegated event handler for closing trades ---
function setupActiveTradesEventHandlers() {
  const activeTradesTableBody = document.querySelector('#activeTradesTable tbody');
  if (!activeTradesTableBody) {
    console.error('[ACTIVE TRADES MANAGER] Active trades table body not found for event handlers');
    return;
  }

  activeTradesTableBody.addEventListener('click', (event) => {
    const target = event.target;
    if (target.classList.contains('price-box') && target.dataset.action === 'close') {
      const tradeId = target.dataset.tradeId;
      if (!tradeId) return;

      const now = Date.now();
      if (lastCloseClickTimes[tradeId] && now - lastCloseClickTimes[tradeId] < DEBOUNCE_DELAY_MS) {
        return;
      }
      lastCloseClickTimes[tradeId] = now;

      // Manual close: use ask value shown on the Close button
      const closeButton = target;
      const askText = closeButton.textContent.trim();
      const askNum = parseFloat(askText);
      let calculatedSellPrice = null;
      if (!isNaN(askNum)) {
        calculatedSellPrice = 1.0 - (askNum / 100);
      }
      if (calculatedSellPrice === null) {
        alert('Invalid ASK price for closing trade');
        return;
      }
      // Use centralized closeTrade function from controller
      if (typeof window.closeTrade === 'function') {
        window.closeTrade(tradeId, calculatedSellPrice, event);
      } else {
        console.error('Centralized closeTrade function not available');
      }
    }
  });
}

// === EXPORT FUNCTIONS ===

// Function to refresh the Active Trades panel using up-to-date API data
async function updateActiveTrades() {
  await fetchAndRenderTrades();
}

// Function to refresh active trades (alias for compatibility)
function fetchAndRenderActiveTrades() {
  fetchAndRenderTrades();
}

// === INITIALIZATION ===

document.addEventListener('DOMContentLoaded', () => {
  // Initialize the active trades table
  initializeActiveTradesTable();
  
  // Setup event handlers
  setupActiveTradesEventHandlers();
  
  // Initial fetch
  fetchAndRenderTrades();
  
  // Check trade supervisor popup on load
  setTimeout(() => {
    if (typeof checkAndShowTradeSupervisorPopup === 'function') {
      checkAndShowTradeSupervisorPopup();
    }
  }, 1000); // Wait 1 second for initial data to load
});

// Export functions for use by other modules
window.updateActiveTrades = updateActiveTrades;
window.fetchAndRenderActiveTrades = fetchAndRenderActiveTrades;
window.fetchAndRenderTrades = fetchAndRenderTrades;
window.closeExpiredTrades = closeExpiredTrades;
window.closeTradeById = closeTradeById; 