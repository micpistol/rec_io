// === WATCHLIST TABLE MODULE ===
// This module handles the watchlist table - an exact clone of the strike table
// but using data from the watchlist JSON file

// Global watchlist table state
window.watchlistRowsMap = new Map();

// === WATCHLIST DATA FETCHING ===

// Fetch watchlist data from the watchlist JSON file
async function fetchWatchlistData() {
  try {
    const response = await fetch('/api/watchlist/btc');
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching watchlist data:', error);
    return null;
  }
}

// === WATCHLIST TABLE INITIALIZATION ===

function initializeWatchlistTable() {
  const watchlistTableBody = document.querySelector('#watchlist-table tbody');
  if (!watchlistTableBody) {
    console.error('Watchlist table body not found');
    return;
  }
  
  console.log('🔍 Initializing watchlist table...');
  updateWatchlistTable();
  
  // Set up periodic updates (every 1 second like the main strike table)
  setInterval(updateWatchlistTable, 1000);
}

// === WATCHLIST TABLE UPDATES ===

async function updateWatchlistTable() {
  try {
    const data = await fetchWatchlistData();
    if (!data || !data.strikes) {
      console.warn('No watchlist data available');
      return;
    }
    
    const watchlistTableBody = document.querySelector('#watchlist-table tbody');
    if (!watchlistTableBody) return;
    
    // Initialize watchlist table if needed
    if (!window.watchlistRowsMap || window.watchlistRowsMap.size === 0) {
      initializeWatchlistTableRows(data.strikes);
    }
    
    // Update each watchlist row with data
    window.watchlistRowsMap.forEach((cells, strike) => {
      const { row, sideTd, bufferTd, bmTd, probTd, buySpan } = cells;
      
      // Find matching strike data from JSON
      const strikeData = data.strikes.find(s => s.strike === strike);
      
      if (strikeData) {
        // Show the row and update it
        row.style.display = '';
        // Buffer (pre-calculated)
        bufferTd.textContent = strikeData.buffer.toLocaleString(undefined, {maximumFractionDigits: 0});
        
        // Buffer % (pre-calculated)
        bmTd.textContent = strikeData.buffer_pct.toFixed(2);
        
        // Probability (pre-calculated) - EXACT SAME as main strike table
        const prob = strikeData.probability;
        probTd.textContent = prob.toFixed(1);
        
        // Risk color coding (EXACT SAME as main strike table)
        row.classList.remove('ultra-safe', 'safe', 'caution', 'high-risk', 'danger-stop');
        let riskClass = '';
        if (prob >= 98) riskClass = 'ultra-safe';
        else if (prob >= 95) riskClass = 'safe';
        else if (prob >= 80) riskClass = 'caution';
        else riskClass = 'high-risk';
        row.classList.add(riskClass);
        
        // Get market data
        const yesAsk = strikeData.yes_ask;
        const noAsk = strikeData.no_ask;
        const yesDiff = strikeData.yes_diff;
        const noDiff = strikeData.no_diff;
        const volume = strikeData.volume;
        const ticker = strikeData.ticker;
        
        // Get current diff mode state (SAME as main strike table)
        const diffMode = window.diffMode || false;
        
        // Same button enabling logic as main strike table
        const volumeNum = parseInt(volume) || 0;
        const volumeOk = volumeNum >= 1000;
        const yesPriceOk = yesAsk <= 98;
        const noPriceOk = noAsk <= 98;
        const isAboveMoneyLine = strike > data.current_price;
        
        // Determine which side should be active and enabled
        let activeSide = null;
        let activeAsk = null;
        let activeDiff = null;
        let activeEnabled = false;
        
        if (volumeOk) {
          if (isAboveMoneyLine) {
            // Above money line: Only enable NO button if price is good
            if (noPriceOk) {
              activeSide = "no";
              activeAsk = noAsk;
              activeDiff = noDiff;
              activeEnabled = true;
            }
          } else {
            // Below money line: Only enable YES button if price is good
            if (yesPriceOk) {
              activeSide = "yes";
              activeAsk = yesAsk;
              activeDiff = yesDiff;
              activeEnabled = true;
            }
          }
        }
        
        // Update side column
        if (activeSide) {
          sideTd.textContent = activeSide.toUpperCase();
        } else {
          sideTd.textContent = '—';
        }
        
        // Update single buy button
        updateWatchlistBuyButton(buySpan, strike, activeSide, activeAsk, activeEnabled, ticker, false, diffMode, activeDiff);
        
        // Update position indicator for this strike (SAME as main strike table)
        updateWatchlistPositionIndicator(row.querySelector('td'), strike);
      } else {
        // Hide the row - strike is not in the watchlist JSON
        row.style.display = 'none';
      }
    });
    
    console.log(`📊 Updated watchlist table with ${data.strikes.length} strikes`);
    
  } catch (error) {
    console.error('Error updating watchlist table:', error);
  }
}

// === WATCHLIST TABLE ROW INITIALIZATION ===

function initializeWatchlistTableRows(strikes) {
  const watchlistTableBody = document.querySelector('#watchlist-table tbody');
  watchlistTableBody.innerHTML = '';
  window.watchlistRowsMap.clear();
  
  strikes.forEach((strikeData) => {
    const row = document.createElement('tr');
    const strike = strikeData.strike;
    
    // Strike cell (EXACT SAME as main strike table)
    const strikeTd = document.createElement('td');
    strikeTd.textContent = '$' + strike.toLocaleString();
    strikeTd.classList.add('center');
    row.appendChild(strikeTd);
    
    // Buffer cell (EXACT SAME as main strike table)
    const bufferTd = document.createElement('td');
    row.appendChild(bufferTd);
    
    // B/M cell (EXACT SAME as main strike table)
    const bmTd = document.createElement('td');
    row.appendChild(bmTd);
    
    // Risk cell (now Prob Touch (%)) (EXACT SAME as main strike table)
    const probTd = document.createElement('td');
    row.appendChild(probTd);
    
    // Side cell (NEW - shows YES/NO)
    const sideTd = document.createElement('td');
    sideTd.classList.add('center');
    row.appendChild(sideTd);
    
    // Buy button cell and span (NEW - single button)
    const buyTd = document.createElement('td');
    buyTd.setAttribute('data-ticker', '');
    const buySpan = document.createElement('span');
    buyTd.appendChild(buySpan);
    row.appendChild(buyTd);
    
    // Add row to table
    watchlistTableBody.appendChild(row);
    
    // Store row data for updates
    window.watchlistRowsMap.set(strike, {
      row,
      sideTd,
      bufferTd,
      bmTd,
      probTd,
      buySpan
    });
  });
}

// === WATCHLIST BUY BUTTON FUNCTION ===

// Global state for button updates
const lastWatchlistButtonStates = new Map();

function updateWatchlistBuyButton(spanEl, strike, side, askPrice, isActive, ticker = null, forceRefresh = false, diffMode = false, diffValue = null) {
  const key = `${strike}-buy`;
  const prev = lastWatchlistButtonStates.get(key);
  
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
      // DIFF MODE: Show pre-calculated diff value (no decimals)
      displayValue = diffValue > 0 ? `+${Math.round(diffValue)}` : `${Math.round(diffValue)}`;
    } else {
      // PRICE MODE: Show actual ask price
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

  // Set data-ticker on the buy cell's parent td
  if (spanEl.parentElement && ticker) {
    spanEl.parentElement.setAttribute('data-ticker', ticker);
  }
  
  // Also set data-ticker directly on spanEl for easier access in openTrade
  if (ticker) {
    spanEl.setAttribute('data-ticker', ticker);
  }
  
  // Set data-strike and data-side for easier retrieval in openTrade
  spanEl.setAttribute('data-strike', strike);
  spanEl.setAttribute('data-side', side || '');
  
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

  lastWatchlistButtonStates.set(key, { askPrice, isActive, diffMode });
}

// === WATCHLIST POSITION INDICATOR (EXACT SAME AS MAIN STRIKE TABLE) ===

async function updateWatchlistPositionIndicator(strikeCell, strike) {
  try {
    // Fetch active trades to check for positions at this strike (SAME as main strike table)
    const tradesRes = await fetch('/trades', { cache: 'no-store' });
    if (!tradesRes.ok) return;
    
    const trades = await tradesRes.json();
    const activeTrades = trades.filter(trade => 
      trade.status !== "closed" && 
      trade.status !== "expired"
    );
    
    // Check if any active trade has this strike (SAME as main strike table)
    const hasPosition = activeTrades.some(trade => {
      const tradeStrike = parseFloat(trade.strike.replace(/[^\d.-]/g, ''));
      return tradeStrike === strike;
    });
    
    // Update visual indicator (SAME as main strike table)
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

// === WATCHLIST UTILITY FUNCTIONS ===

// Debounce function (SAME as main strike table)
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// === WATCHLIST INITIALIZATION ===

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  // Wait a bit for the main strike table to initialize first
  setTimeout(() => {
    initializeWatchlistTable();
  }, 100);
});

// Export functions for global access (same as main strike table)
window.updateWatchlistTable = updateWatchlistTable;
window.updateWatchlistPositionIndicator = updateWatchlistPositionIndicator; 