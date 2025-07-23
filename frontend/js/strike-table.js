
// Add no-op definitions for missing functions to prevent ReferenceError
if (typeof window.updateClickHandlersForReco !== 'function') {
  window.updateClickHandlersForReco = function() {};
}

// === STRIKE TABLE MODULE ===
// This module handles middle column data: strike table, TTC, market title
// All data now comes from unified backend endpoints

// --- Row Flash CSS ---
if (!window._rowFlashStyleInjected) {
  const rowFlashStyle = document.createElement('style');
  rowFlashStyle.innerHTML = `
.strike-row-flash {
  animation: strike-row-flash-anim 0.55s linear;
}
@keyframes strike-row-flash {
  0% { background-color: #fff700; color: #222 !important; }
  80% { background-color: #fff700; color: #222 !important; }
  100% { background-color: inherit; color: inherit; }
}
`;
  document.head.appendChild(rowFlashStyle);
  window._rowFlashStyleInjected = true;
}

// Global strike table state
window.strikeRowsMap = new Map();

// === UNIFIED DATA FETCHING ===

// Fetch unified TTC data
async function fetchUnifiedTTC() {
  try {
    const response = await fetch('/api/unified_ttc/btc');
    const data = await response.json();
    return data.ttc_seconds || 0;
  } catch (error) {
    console.error('Error fetching unified TTC:', error);
    return 0;
  }
}

// Fetch strike table data from unified endpoint
async function fetchStrikeTableData() {
  try {
    const response = await fetch('/api/strike_tables/btc');
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching strike table data:', error);
    return null;
  }
}

// Update TTC display from unified endpoint
async function updateTTCDisplay() {
  try {
    const ttcSeconds = await fetchUnifiedTTC();
    const ttcEl = document.getElementById('strikePanelTTC');
    if (!ttcEl) return;

    // Format TTC for display
    const formatTTC = (seconds) => {
      if (seconds === null || seconds === undefined || isNaN(seconds)) {
        return '--:--';
      }
      
      const totalMinutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      
      if (totalMinutes >= 60) {
        const hours = Math.floor(totalMinutes / 60);
        const minutes = totalMinutes % 60;
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
      } else {
        return `${totalMinutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
      }
    };

    ttcEl.textContent = formatTTC(ttcSeconds);

    // Apply color coding
    ttcEl.style.backgroundColor = '';
    ttcEl.style.color = '';
    ttcEl.style.borderRadius = '';
    ttcEl.style.padding = '';

    if (ttcSeconds >= 0 && ttcSeconds <= 180) {
      ttcEl.style.backgroundColor = '#d2372b';
      ttcEl.style.color = '#fff';
      ttcEl.style.borderRadius = '6px';
      ttcEl.style.padding = '0 10px';
    } else if (ttcSeconds <= 300) {
      ttcEl.style.backgroundColor = '#ffc107';
      ttcEl.style.color = '#fff';
      ttcEl.style.borderRadius = '6px';
      ttcEl.style.padding = '0 10px';
    } else if (ttcSeconds <= 720) {
      ttcEl.style.backgroundColor = '#45d34a';
      ttcEl.style.color = '#fff';
      ttcEl.style.borderRadius = '6px';
      ttcEl.style.padding = '0 10px';
    } else if (ttcSeconds <= 900) {
      ttcEl.style.backgroundColor = '#45d34a';
      ttcEl.style.color = '#fff';
      ttcEl.style.borderRadius = '6px';
      ttcEl.style.padding = '0 10px';
    }
  } catch (error) {
    console.error('Error updating TTC display:', error);
  }
}

// Update market title from strike table data
function updateMarketTitle(strikeTableData) {
  if (!strikeTableData) return;
  
  const cell = document.getElementById('strikePanelMarketTitleCell');
  if (!cell) return;
  
  // Extract time from market_title (e.g., "Bitcoin price on Jul 22, 2025 at 3pm EDT?" -> "3pm")
  const marketTitle = strikeTableData.market_title || '';
  const timeMatch = marketTitle.match(/at\s+(.+?)\s+(?:EDT|EST)\?/i);
  const timeStr = timeMatch ? timeMatch[1].trim() : '11pm';
  
  // Format as "<symbol> price today at <time>?"
  const symbol = strikeTableData.symbol || 'BTC';
  const formattedTitle = `${symbol} price today at ${timeStr}?`;
  
  cell.textContent = formattedTitle;
  cell.style.color = "white";
}

// Main function to update middle column data
async function updateMiddleColumnData() {
  try {
    // Fetch strike table data (includes market title)
    const strikeTableData = await fetchStrikeTableData();
    
    // Update market title
    updateMarketTitle(strikeTableData);
    
    // Update TTC display
    await updateTTCDisplay();
    
    console.log('[STRIKE-TABLE] Updated middle column data');
  } catch (error) {
    console.error('Error updating middle column data:', error);
  }
}

// === STRIKE TABLE INITIALIZATION ===

function buildStrikeTableRows(basePrice) {
  const step = 250;
  const rows = [];
  // Generate two extra rows: one above, one below
  for (let i = basePrice - 7 * step; i <= basePrice + 7 * step; i += step) {
    rows.push(i);
  }
  return rows;
}

function createSpannerRow(currentPrice) {
  const spannerRow = document.createElement("tr");
  spannerRow.className = "spanner-row";
  const spannerTd = document.createElement("td");
  spannerTd.colSpan = 6; // Match the number of columns in strike table
  // SVGs for straight arrows (no margin)
  const svgDown = `<svg width="16" height="16" style="vertical-align:middle;" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8 2v12M8 14l4-4M8 14l-4-4" stroke="#45d34a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const svgUp = `<svg width="16" height="16" style="vertical-align:middle;" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8 14V2M8 2l4 4M8 2l-4 4" stroke="#dc3545" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
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
  return spannerRow;
}

function initializeStrikeTable(basePrice) {
  const strikeTableBody = document.querySelector('#strike-table tbody');
  const strikes = buildStrikeTableRows(basePrice);
  strikeTableBody.innerHTML = '';
  window.strikeRowsMap.clear();

  strikes.forEach((strike, idx) => {
    const row = document.createElement('tr');

    // Strike cell
    const strikeTd = document.createElement('td');
    strikeTd.textContent = '$' + strike.toLocaleString();
    strikeTd.classList.add('center');
    row.appendChild(strikeTd);

    // Buffer cell
    const bufferTd = document.createElement('td');
    row.appendChild(bufferTd);

    // B/M cell
    const bmTd = document.createElement('td');
    row.appendChild(bmTd);

    // Risk cell (now Prob Touch (%))
    const probTd = document.createElement('td');
    row.appendChild(probTd);

    // Yes button cell and span
    const yesTd = document.createElement('td');
    // Set data-ticker on the cell (will be updated later in updateYesNoButton)
    yesTd.setAttribute('data-ticker', '');
    const yesSpan = document.createElement('span');
    yesTd.appendChild(yesSpan);
    row.appendChild(yesTd);

    // No button cell and span
    const noTd = document.createElement('td');
    noTd.setAttribute('data-ticker', '');
    const noSpan = document.createElement('span');
    noTd.appendChild(noSpan);
    row.appendChild(noTd);

    // Hide the first and last row (buffer rows)
    if (idx === 0 || idx === strikes.length - 1) {
      row.classList.add('strike-row-buffer');
      row.style.display = 'none';
    }
    strikeTableBody.appendChild(row);

    window.strikeRowsMap.set(strike, {
      row,
      bufferTd,
      bmTd,
      probTd,
      yesSpan,
      noSpan
    });
  });
}

// === STRIKE TABLE UPDATE LOGIC ===

// Update strike table with data from unified endpoint
async function updateStrikeTable() {
  try {
    // Fetch strike table data from unified endpoint
    const strikeTableData = await fetchStrikeTableData();
    if (!strikeTableData || !strikeTableData.strikes) {
      console.error('No strike table data available');
      return;
    }

    const strikes = strikeTableData.strikes;
    const currentPrice = strikeTableData.current_price;
    const symbol = strikeTableData.symbol || 'BTC';

    // Initialize strike table if needed
    if (!window.strikeRowsMap || window.strikeRowsMap.size === 0) {
      const base = Math.round(currentPrice / 250) * 250;
      initializeStrikeTable(base);
    }

    // Update each strike row with pre-calculated data
    window.strikeRowsMap.forEach((cells, strike) => {
      const { row, bufferTd, bmTd, probTd, yesSpan, noSpan } = cells;

      // Find matching strike data from JSON
      const strikeData = strikes.find(s => s.strike === strike);
      
      if (strikeData) {
        // Buffer (pre-calculated)
        bufferTd.textContent = strikeData.buffer.toLocaleString(undefined, {maximumFractionDigits: 0});

        // Buffer % (pre-calculated)
        bmTd.textContent = strikeData.buffer_pct.toFixed(2);

        // Probability (pre-calculated)
        const prob = strikeData.probability;
        probTd.textContent = prob.toFixed(1);
        
        // Risk color coding
        row.classList.remove('ultra-safe', 'safe', 'caution', 'high-risk', 'danger-stop');
        let riskClass = '';
        if (prob >= 98) riskClass = 'ultra-safe';
        else if (prob >= 95) riskClass = 'safe';
        else if (prob >= 80) riskClass = 'caution';
        else riskClass = 'high-risk';
        row.classList.add(riskClass);

        // Yes/No ask prices (pre-calculated)
        const yesAsk = strikeData.yes_ask;
        const noAsk = strikeData.no_ask;
        const yesDiff = strikeData.yes_diff;
        const noDiff = strikeData.no_diff;
        const volume = strikeData.volume;

        // Get current diff mode state
        const diffMode = window.diffMode || false;

        // Simplified button enabling logic
        const volumeNum = parseInt(volume) || 0;
        const volumeOk = volumeNum >= 1000;
        const yesPriceOk = yesAsk <= 98;
        const noPriceOk = noAsk <= 98;
        const currentPrice = strikeTableData.current_price;
        const isAboveMoneyLine = strike > currentPrice;
        
        // Determine which button should be enabled
        let yesEnabled = false;
        let noEnabled = false;
        
        if (volumeOk) {
          if (isAboveMoneyLine) {
            // Above money line: Only enable NO button if price is good
            noEnabled = noPriceOk;
            yesEnabled = false; // Never enable YES above money line
          } else {
            // Below money line: Only enable YES button if price is good
            yesEnabled = yesPriceOk;
            noEnabled = false; // Never enable NO below money line
          }
        }
        
        // Update both buttons with their correct enabled state
        updateYesNoButton(yesSpan, strike, "yes", yesAsk, yesEnabled, strikeData.ticker, false, diffMode, yesDiff);
        updateYesNoButton(noSpan, strike, "no", noAsk, noEnabled, strikeData.ticker, false, diffMode, noDiff);
        
        // Update position indicator for this strike
        const strikeCell = row.querySelector('td:first-child'); // First column is strike price
        if (strikeCell) {
          updatePositionIndicator(strikeCell, strike);
        }
      } else {
        // No data for this strike, show placeholders
        bufferTd.textContent = '—';
        bmTd.textContent = '—';
        probTd.textContent = '—';
        updateYesNoButton(yesSpan, strike, "yes", 0, false, null, false, window.diffMode || false, null);
        updateYesNoButton(noSpan, strike, "no", 0, false, null, false, window.diffMode || false, null);
      }
    });

    // --- SPANNER ROW LOGIC ---
    const strikeTableBody = document.querySelector('#strike-table tbody');
    let spannerRow = strikeTableBody.querySelector('.spanner-row');
    
    // Create spanner row if it doesn't exist
    if (!spannerRow) {
      spannerRow = createSpannerRow(currentPrice);
      // Ensure the spanner row is added to the table
      strikeTableBody.appendChild(spannerRow);
    } else {
      // Update existing spanner row with current price and momentum arrows
      const spannerTd = spannerRow.querySelector('td');
      if (spannerTd) {
        // Recreate the spanner row content with updated momentum arrows
        const svgDown = `<svg width="16" height="16" style="vertical-align:middle;" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8 2v12M8 14l4-4M8 14l-4-4" stroke="#45d34a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
        const svgUp = `<svg width="16" height="16" style="vertical-align:middle;" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8 14V2M8 2l4 4M8 2l-4 4" stroke="#dc3545" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
        
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
      }
    }

    // Position spanner row correctly
    const allRows = Array.from(strikeTableBody.children).filter(row => !row.classList.contains('spanner-row'));
    let insertIndex = allRows.length; // default to end
    
    for (let i = 0; i < allRows.length; i++) {
      const row = allRows[i];
      const strikeCell = row.querySelector('td');
      if (strikeCell && strikeCell.textContent) {
        const strikeText = strikeCell.textContent.replace(/[\$,]/g, '');
        const strike = parseFloat(strikeText);
        if (!isNaN(strike) && currentPrice < strike) {
          insertIndex = i;
          break;
        }
      }
    }

    // Remove spanner row from current position and insert at correct position
    if (spannerRow.parentNode) {
      spannerRow.remove();
    }
    
    if (insertIndex < allRows.length) {
      strikeTableBody.insertBefore(spannerRow, allRows[insertIndex]);
    } else {
      strikeTableBody.appendChild(spannerRow);
    }

    // Update fingerprint display if function exists
    if (typeof updateFingerprintDisplay === 'function') {
      updateFingerprintDisplay();
    }

    // Update heat band if function exists
    if (typeof updateMomentumHeatBandSegmented === 'function') {
      setTimeout(() => {
        const strikeTable = document.getElementById('strike-table');
        const heatBand = document.getElementById('momentum-heat-band');
        if (strikeTable && heatBand) {
          heatBand.style.height = strikeTable.offsetHeight + 'px';
        }
        updateMomentumHeatBandSegmented();
      }, 0);
    }

    console.log('[STRIKE-TABLE] Updated strike table with unified data');
    
    // Reset diff mode change flag after update is complete
    window.diffModeChanged = false;
  } catch (error) {
    console.error('Error updating strike table:', error);
  }
}

// === POSITION INDICATOR ===

async function updatePositionIndicator(strikeCell, strike) {
  try {
    // Fetch active trades to check for positions at this strike
    const tradesRes = await fetch('/trades', { cache: 'no-store' });
    if (!tradesRes.ok) return;
    
    const trades = await tradesRes.json();
    const activeTrades = trades.filter(trade => 
      trade.status !== "closed" && 
      trade.status !== "expired"
    );
    
    // Check if any active trade has this strike
    const hasPosition = activeTrades.some(trade => {
      const tradeStrike = parseFloat(trade.strike.replace(/[^\d.-]/g, ''));
      return tradeStrike === strike;
    });
    
    // Update visual indicator
    if (hasPosition) {
      strikeCell.style.backgroundColor = '#1a2a1a'; // Very subtle green tint
      strikeCell.style.borderLeft = '3px solid #45d34a'; // Green left border
    } else {
      strikeCell.style.backgroundColor = '';
      strikeCell.style.borderLeft = '';
    }
  } catch (e) {
    strikeCell.style.backgroundColor = '';
    strikeCell.style.borderLeft = '';
  }
}

// === YES/NO BUTTON UPDATES ===

// Track last Yes/No button states
const lastButtonStates = new Map();

// Debounce helper function
function debounce(func, wait) {
  let timeout;
  return function(...args) {
    if (timeout) return;
    func.apply(this, args);
    timeout = setTimeout(() => {
      timeout = null;
    }, wait);
  };
}

// Helper function to update Yes/No button with conditional redraw
function updateYesNoButton(spanEl, strike, side, askPrice, isActive, ticker = null, forceRefresh = false, diffMode = false, diffValue = null) {
  const key = `${strike}-${side}`;
  const prev = lastButtonStates.get(key);
  
  // Check if diffMode has changed (this forces redraw when switching modes)
  const diffModeChanged = prev && prev.diffMode !== diffMode;
  
  if (!forceRefresh && !window.forceButtonRefresh && !diffModeChanged && !window.diffModeChanged && prev && prev.askPrice === askPrice && prev.isActive === isActive) {
    // No change; skip update
    return;
  }

  // Determine display value based on mode
  let displayValue = '—';
  if (askPrice && askPrice !== '—' && askPrice !== 0) {
    if (diffMode && diffValue !== null) {
      // DIFF MODE: Show pre-calculated diff value (no decimals) for ALL buttons
      displayValue = diffValue > 0 ? `+${Math.round(diffValue)}` : `${Math.round(diffValue)}`;
    } else {
      // PRICE MODE: Show actual ask price for ALL buttons
      displayValue = askPrice;
    }
  }
  
  spanEl.textContent = displayValue;
  spanEl.className = isActive ? 'price-box' : 'price-box disabled';
  spanEl.style.cursor = isActive ? 'pointer' : 'default';
  
  // Force cursor style with higher specificity
  if (isActive) {
    spanEl.style.setProperty('cursor', 'pointer', 'important');
  } else {
    spanEl.style.setProperty('cursor', 'default', 'important');
  }

  // Set data-ticker on the YES/NO cell's parent td (for reference, if needed)
  if (spanEl.parentElement && ticker) {
    spanEl.parentElement.setAttribute('data-ticker', ticker);
  }
  // Also set data-ticker directly on spanEl for easier access in openTrade
            if (ticker) {
            spanEl.setAttribute('data-ticker', ticker);
          }
  // Set data-strike and data-side for easier retrieval in openTrade
  spanEl.setAttribute('data-strike', strike);
  spanEl.setAttribute('data-side', side);
  
  // Store the actual ask price for trade execution (not the display value)
  if (askPrice && askPrice !== '—' && askPrice !== 0) {
    spanEl.setAttribute('data-ask-price', askPrice);
  } else {
    spanEl.removeAttribute('data-ask-price');
  }

  if (isActive) {
    spanEl.onclick = debounce(function(event) {
      // Use centralized trade execution controller
      if (typeof openTrade === 'function') {
        openTrade(spanEl);
      } else {
        console.error('openTrade function not available');
      }
    }, 300);
  } else {
    spanEl.onclick = null;
  }

  lastButtonStates.set(key, { askPrice, isActive, diffMode });
}

// === TRADE EXECUTION ===
// All trade execution goes through the single openTrade function in trade_monitor.html
// This ensures audio alerts and popup displays work correctly

// === IMMEDIATE DIF MODE REDRAW ===

// Global flag to force refresh on mode changes
window.forceButtonRefresh = false;
window.diffModeChanged = false;

// === UTILITY FUNCTIONS ===

// Utility function to get selected symbol from ticker panel
function getSelectedSymbol() {
  const tickerSelect = document.getElementById('ticker-picker');
  if (tickerSelect) {
    return tickerSelect.value;
  }
  return "";
}


function showTradeOpenedPopup() {
  const popup = document.getElementById('tradePopup');
  if (!popup) return;

  popup.style.transition = 'none';
  popup.style.display = 'block';
  popup.style.opacity = '1';

  setTimeout(() => {
    popup.style.transition = 'opacity 0.5s ease';
    popup.style.opacity = '0';
    setTimeout(() => {
      popup.style.display = 'none';
    }, 500);
  }, 2000);
}

// === EXPORT FUNCTIONS TO WINDOW ===
// Make functions available globally for other modules to use
window.initializeStrikeTable = initializeStrikeTable;
window.updateStrikeTable = updateStrikeTable;
window.updateYesNoButton = updateYesNoButton;
window.updatePositionIndicator = updatePositionIndicator;
window.addStrikeTableRowClickHandlers = addStrikeTableRowClickHandlers;
window.updateMiddleColumnData = updateMiddleColumnData;
window.fetchUnifiedTTC = fetchUnifiedTTC;
window.fetchStrikeTableData = fetchStrikeTableData;

// === STRIKE TABLE ROW CLICK HANDLERS ===
function addStrikeTableRowClickHandlers() {
  const strikeTable = document.getElementById('strike-table');
  if (!strikeTable) return;
  const rows = strikeTable.querySelectorAll('tbody tr');
  rows.forEach(row => {
    // Remove any previous click handler
    row.removeEventListener('click', row._strikeTableClickHandler);
    // Attach new click handler (currently no-op, can be extended later)
    const clickHandler = (event) => {
      // Click handler removed - no functionality
    };
    row._strikeTableClickHandler = clickHandler;
    row.addEventListener('click', clickHandler);
  });
}

// Load DIFF mode setting from preferences
async function loadDiffModeFromPreferences() {
  try {
    const response = await fetch('/api/get_preferences');
    const data = await response.json();
    window.diffMode = data.diff_mode || false;
  } catch (error) {
    window.diffMode = false;
  }
}

// Attach handlers after table is rendered
if (typeof window !== 'undefined') {
  document.addEventListener('DOMContentLoaded', async () => {
    await loadDiffModeFromPreferences();
    
    // Initialize middle column data immediately
    await updateMiddleColumnData();
    
    // Set up polling for middle column data
    setInterval(updateMiddleColumnData, 1000); // Poll every 1 second (unchanged frequency)
    
    // Initialize and poll strike table data
    await updateStrikeTable();
    setInterval(updateStrikeTable, 1000); // Poll every 1 second (unchanged frequency)
  });
} 

// === STRIKE TABLE WEBSOCKET UPDATES ===
// WebSocket connection for real-time database change notifications
let dbChangeWebSocket = null;

function connectDbChangeWebSocket() {
  if (dbChangeWebSocket && dbChangeWebSocket.readyState === WebSocket.OPEN) {
    console.log("[WEBSOCKET] Already connected");
    return; // Already connected
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/db_changes`;
  console.log("[WEBSOCKET] Connecting to:", wsUrl);
  
  dbChangeWebSocket = new WebSocket(wsUrl);
  
  dbChangeWebSocket.onopen = function() {
    console.log("[WEBSOCKET] ✅ Connection opened successfully");
  };
  
  dbChangeWebSocket.onmessage = function(event) {
    try {
      console.log("[WEBSOCKET] Received message:", event.data);
      const data = JSON.parse(event.data);
      if (data.type === 'db_change' && data.database === 'trades') {
        console.log("[WEBSOCKET] ✅ Trades DB change detected, updating UI");
        fetchAndRenderStrikeTable();
        // Also update active trades when trades.db changes
        if (typeof window.fetchAndRenderTrades === 'function') {
          window.fetchAndRenderTrades();
        }
      }
    } catch (error) {
      console.error("[WEBSOCKET] Error processing message:", error);
    }
  };
  
  dbChangeWebSocket.onclose = function(event) {
    console.log("[WEBSOCKET] ❌ Connection closed:", event.code, event.reason);
    // Try to reconnect after 5 seconds
    setTimeout(() => {
      console.log("[WEBSOCKET] Attempting to reconnect...");
      connectDbChangeWebSocket();
    }, 5000);
  };
  
  dbChangeWebSocket.onerror = function(error) {
    console.error("[WEBSOCKET] ❌ Connection error:", error);
  };
}

// Function to fetch and render strike table (called by WebSocket)
function fetchAndRenderStrikeTable() {
  if (typeof window.fetchAndUpdate === 'function') {
    window.fetchAndUpdate();
  }
}

// Initialize WebSocket connection
if (typeof window !== 'undefined') {
  connectDbChangeWebSocket();
  
  // Add a test function to manually trigger a database change notification
  window.testWebSocketConnection = function() {
    console.log("[WEBSOCKET] Testing connection...");
    if (dbChangeWebSocket && dbChangeWebSocket.readyState === WebSocket.OPEN) {
      console.log("[WEBSOCKET] ✅ Connection is open");
      // Send a test message to the server
      dbChangeWebSocket.send("ping");
    } else {
      console.log("[WEBSOCKET] ❌ Connection is not open, state:", dbChangeWebSocket ? dbChangeWebSocket.readyState : 'null');
    }
  };
} 

 
