
// Add no-op definitions for missing functions to prevent ReferenceError
if (typeof window.updateClickHandlersForReco !== 'function') {
  window.updateClickHandlersForReco = function() {};
}

// === STRIKE TABLE MODULE ===
// This module handles all strike table creation, updates, and maintenance

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

async function fetchProbabilities(symbol, currentPrice, ttcMinutes, strikes, year = null) {
  try {
    // Try new live probabilities endpoint first
    const res = await fetch(window.location.origin + '/api/live_probabilities');
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.probabilities)) {
        const probMap = new Map();
        data.probabilities.forEach(row => {
          probMap.set(Math.round(row.strike), row.prob_within);
        });
        return probMap;
      }
    }
    // Fallback to old API if live endpoint fails
    const momentumScore = getCurrentMomentumScore();
    const fallbackRes = await fetch(window.location.origin + '/api/strike_probabilities', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_price: currentPrice,
        strikes: strikes,
        momentum_score: momentumScore
      })
    });
    const fallbackData = await fallbackRes.json();
    if (fallbackData.status === 'ok' && Array.isArray(fallbackData.probabilities)) {
      const probMap = new Map();
      fallbackData.probabilities.forEach(row => {
        probMap.set(Math.round(row.strike), row.prob_within);
      });
      return probMap;
    }
    return null;
  } catch (e) {
    return null;
  }
}

// PATCHED updateStrikeTable to use model-based probabilities for RISK
async function updateStrikeTable(coreData, latestKalshiMarkets) {
  // Use local diffMode state if available, otherwise fetch from preferences
  let diffMode = false;
  if (window.diffMode !== undefined) {
    // Use local state for instant response
    diffMode = window.diffMode;
  } else {
    // Fallback to backend preferences
    try {
      const response = await fetch('/api/get_preferences');
      const data = await response.json();
      diffMode = data.diff_mode || false;
    } catch (e) {
      diffMode = false;
    }
  }

  const strikeTableBody = document.querySelector('#strike-table tbody');
  if (!coreData || typeof coreData.btc_price !== 'number') return;

  const base = Math.round(coreData.btc_price / 250) * 250;
  const ttcSeconds = coreData.ttc_seconds || 1;
  const ttcMinutes = ttcSeconds / 60;
  const centerPrice = coreData.btc_price;
  const symbol = getSelectedSymbol ? getSelectedSymbol() : 'BTC';
  const year = '2021'; // TODO: make dynamic if needed



  // Build array of strike rows for proper ordering
  const strikeRows = [];
  const strikes = Array.from(window.strikeRowsMap.keys()).sort((a, b) => a - b);
  strikes.forEach(strike => {
    const cells = window.strikeRowsMap.get(strike);
    if (cells && cells.row) {
      strikeRows.push(cells.row);
    }
  });

  // Fetch model-based probabilities for all strikes
  const probMap = await fetchProbabilities(symbol, centerPrice, ttcMinutes, strikes, year);

  // Update fingerprint display after fetching probabilities with momentum score
  if (typeof updateFingerprintDisplay === 'function') {
    updateFingerprintDisplay();
  }



  window.strikeRowsMap.forEach((cells, strike) => {
    const { row, bufferTd, bmTd, probTd, yesSpan, noSpan } = cells;

    // Buffer
    const buffer = centerPrice - strike;
    bufferTd.textContent = Math.abs(buffer).toLocaleString(undefined, {maximumFractionDigits: 0});

    // % (Buffer as percentage of one strike level)
    const strikeLevel = 250; // One strike level is $250
    const bufferPercent = Math.abs(buffer) / strikeLevel;
    bmTd.textContent = bufferPercent.toFixed(2);

    // --- PATCH: Use model-based probability for Prob Touch (%) ---
    let prob = probMap && probMap.has(strike) ? probMap.get(strike) : null;
    if (prob !== null && prob !== undefined) {
      // Use the probability directly (already prob_within from API)
      let displayProb = prob;
      probTd.textContent = displayProb.toFixed(1);
      row.className = '';
      // --- RISK COLOR PATCH (UPDATED BANDS) ---
      row.classList.remove('ultra-safe', 'safe', 'caution', 'high-risk', 'danger-stop');
      let riskClass = '';
      if (displayProb >= 98) riskClass = 'ultra-safe'; // bright green
      else if (displayProb >= 95) riskClass = 'safe'; // light green
      else if (displayProb >= 80) riskClass = 'caution'; // yellow
      else riskClass = 'high-risk'; // red
      row.classList.add(riskClass);
      // --- END PATCH ---
    } else {
      probTd.textContent = '—';
      row.className = '';
      row.classList.remove('ultra-safe', 'safe', 'caution', 'high-risk', 'danger-stop');
    }

    // Find markets for yes/no asks - use more flexible matching
    const matchingMarket = latestKalshiMarkets.find(m => {
      const marketStrike = Math.round(m.floor_strike);
      return marketStrike === strike || Math.abs(marketStrike - strike) <= 1;
    });
    const ticker = matchingMarket ? matchingMarket.ticker : null;
    const yesAsk = matchingMarket && typeof matchingMarket.yes_ask === "number" ? Math.round(matchingMarket.yes_ask) : 0;
    const noAsk = matchingMarket && typeof matchingMarket.no_ask === "number" ? Math.round(matchingMarket.no_ask) : 0;
    const volume = matchingMarket && typeof matchingMarket.volume === "number" ? matchingMarket.volume : 0;

    // --- VOLUME-BASED DISABLING LOGIC ---
    
    // If volume < 1000, both buttons are disabled regardless of mode
    if (volume < 1000) {
      updateYesNoButton(yesSpan, strike, "yes", yesAsk, false, ticker);
      updateYesNoButton(noSpan, strike, "no", noAsk, false, ticker);
    } else {
      // Volume >= 1000, determine which button is active
      const isYesActive = (volume >= 1000) && yesAsk > noAsk && yesAsk < 99 && yesAsk >= 40;
      const isNoActive = (volume >= 1000) && noAsk > yesAsk && noAsk < 99 && noAsk >= 40;
      
      // Always pass actual ask prices to updateYesNoButton for trade execution
      // Display values will be set inside updateYesNoButton based on mode
      updateYesNoButton(yesSpan, strike, "yes", yesAsk, isYesActive, ticker, false, diffMode, probMap?.get(strike));
      updateYesNoButton(noSpan, strike, "no", noAsk, isNoActive, ticker, false, diffMode, probMap?.get(strike));
    }
    updatePositionIndicator(cells.row.children[0], strike);
  });

  // --- GUARANTEED SPANNER ROW LOGIC ---
  if (strikeRows.length > 0) {
    // Always check for spanner row after all strike rows are rendered
    let spannerRow = strikeTableBody.querySelector('.spanner-row');
    const allRows = Array.from(strikeTableBody.children);
    let insertIndex = allRows.length; // default to end
    for (let i = 0; i < allRows.length; i++) {
      const row = allRows[i];
      if (row.classList.contains('spanner-row')) continue;
      const strikeCell = row.querySelector('td');
      if (strikeCell) {
        const strike = parseFloat(strikeCell.textContent.replace(/[\$,]/g, ''));
        if (centerPrice < strike) {
          insertIndex = i;
          break;
        }
      }
    }
    if (!spannerRow) {
      spannerRow = createSpannerRow(centerPrice);
      if (insertIndex < allRows.length) {
        strikeTableBody.insertBefore(spannerRow, allRows[insertIndex]);
      } else {
        strikeTableBody.appendChild(spannerRow);
      }
    } else {
      // Update content
      const spannerTd = spannerRow.querySelector('td');
      if (spannerTd) {
        const priceMatch = spannerTd.innerHTML.match(/Current Price: \$[\d,]+/);
        if (priceMatch) {
          const newPriceText = `Current Price: $${Math.round(centerPrice).toLocaleString()}`;
          spannerTd.innerHTML = spannerTd.innerHTML.replace(priceMatch[0], newPriceText);
        }
      }
      // Move if not at correct position
      const currentSpannerIndex = allRows.indexOf(spannerRow);
      if (currentSpannerIndex !== insertIndex) {
        if (insertIndex < allRows.length) {
          strikeTableBody.insertBefore(spannerRow, allRows[insertIndex]);
        } else {
          strikeTableBody.appendChild(spannerRow);
        }
      }
    }
  }


  
  if (typeof window.addStrikeTableClickHandlers === 'function') window.addStrikeTableClickHandlers();

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
function updateYesNoButton(spanEl, strike, side, askPrice, isActive, ticker = null, forceRefresh = false, diffMode = false, probability = null) {
  const key = `${strike}-${side}`;
  const prev = lastButtonStates.get(key);
  
  if (!forceRefresh && !window.forceButtonRefresh && prev && prev.askPrice === askPrice && prev.isActive === isActive) {
    // No change; skip update
    return;
  }

  // Determine display value based on mode
  let displayValue = '—';
  if (askPrice && askPrice !== '—' && askPrice !== 0) {
    if (diffMode && probability !== null && isActive) {
      // DIFF MODE: Show probability - ask price difference for active button
      const diff = Math.round(probability - askPrice);
      displayValue = diff > 0 ? `+${diff}` : `${diff}`;
    } else {
      // PRICE MODE or inactive button: Show actual ask price
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
      // Call master openTrade function
      if (typeof openTrade === 'function') {
        openTrade(spanEl);
      } else {
        console.error('openTrade function not available');
      }
    }, 300);
  } else {
    spanEl.onclick = null;
  }

  lastButtonStates.set(key, { askPrice, isActive });
}

// === TRADE EXECUTION ===
// Remove legacy openTrade and ticket logic. All trade tickets must go through the centralized controller.
// Remove function openTrade and any code that builds or sends tickets directly.
// Only keep UI logic and event handlers that call window.executeTrade and window.prepareTradeData from trade-execution-controller.js.

// === IMMEDIATE DIF MODE REDRAW ===

// Global flag to force refresh on mode changes
window.forceButtonRefresh = false;

// === UTILITY FUNCTIONS ===

// Utility function to get selected symbol from ticker panel
function getSelectedSymbol() {
  const tickerSelect = document.getElementById('ticker-picker');
  if (tickerSelect) {
    return tickerSelect.value;
  }
  return "";
}

// Utility function to get truncated market title, e.g., "BTC 11am"
function getTruncatedMarketTitle() {
  if (window.CurrentMarketTitleRaw && typeof window.CurrentMarketTitleRaw === "string") {
    const contractMatch = window.CurrentMarketTitleRaw.match(/at\s(.+?)\s*(?:EDT|EST)?\?/i);
    if (contractMatch) {
      return `BTC ${contractMatch[1].trim()}`;
    } else {
      return window.CurrentMarketTitleRaw;
    }
  }
  return 'BTC Unknown';
}

// Utility function to get current BTC ticker price from the UI
function getCurrentBTCTickerPrice() {
  const el = document.getElementById('btc-price-value');
  if (el && el.textContent) {
    // Remove $ and commas, parse as float
    const val = parseFloat(el.textContent.replace(/\$|,/g, ''));
    return isNaN(val) ? "" : val;
  }
  return "";
}

// Utility function to get current momentum score from the panel
function getCurrentMomentumScore() {
  const el = document.getElementById('momentum-score-value');
  if (el && el.textContent) {
    const val = parseFloat(el.textContent.replace(/[^\d\.\-]/g, ''));
    return isNaN(val) ? "" : val;
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
// window.openTrade = openTrade; // Removed
window.updateYesNoButton = updateYesNoButton;
window.updatePositionIndicator = updatePositionIndicator;
// window.redrawYesNoButtonsForDIFMode = redrawYesNoButtonsForDIFMode; // REMOVED
window.addStrikeTableRowClickHandlers = addStrikeTableRowClickHandlers;

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
    // Now safe to initialize or update the strike table
    if (typeof window.fetchAndUpdate === 'function') {
      window.fetchAndUpdate();
    }
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

// === Spanner Row Helper ===
function createSpannerRow(currentPrice) {
  const spannerRow = document.createElement("tr");
  spannerRow.className = "spanner-row";
  const spannerTd = document.createElement("td");
  spannerTd.colSpan = 6; // PATCHED: match actual number of columns
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

 
