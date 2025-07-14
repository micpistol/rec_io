// Add no-op definitions for missing functions to prevent ReferenceError
if (typeof window.updateWatchlistDisplay !== 'function') {
  window.updateWatchlistDisplay = function() {};
}
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
  for (let i = basePrice - 6 * step; i <= basePrice + 6 * step; i += step) {
    rows.push(i);
  }
  return rows;
}

function initializeStrikeTable(basePrice) {
  const strikeTableBody = document.querySelector('#strike-table tbody');
  const strikes = buildStrikeTableRows(basePrice);
  strikeTableBody.innerHTML = ''; // only clear once at start
  window.strikeRowsMap.clear();

  strikes.forEach(strike => {
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
  
  // Update watchlist after strike table is initialized
  if (window.updateWatchlistDisplay) {
    console.log('[STRIKE TABLE] Strike table initialized, updating watchlist');
    setTimeout(() => {
      window.updateWatchlistDisplay();
    }, 100);
  }
}

// === STRIKE TABLE UPDATE LOGIC ===

async function fetchProbabilities(symbol, currentPrice, ttcMinutes, strikes, year = null) {
  try {
    const ttcSeconds = ttcMinutes * 60;
    
    // Get current momentum score from the UI
    const momentumScore = getCurrentMomentumScore();
    
    console.log('[STRIKE TABLE] Fetching probabilities for:', {
      currentPrice,
      ttcSeconds,
      momentumScore,
      strikes: strikes.slice(0, 5) + '...' + strikes.slice(-5) // Show first and last 5 strikes
    });
    
    const res = await fetch(window.location.origin + '/api/strike_probabilities', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_price: currentPrice,
        ttc_seconds: ttcSeconds,
        strikes: strikes,
        momentum_score: momentumScore
      })
    });
    const data = await res.json();
    console.log('[STRIKE TABLE] API Response:', data); // DEBUG LOG
    if (data.status === 'ok' && Array.isArray(data.probabilities)) {
      // Map: strike -> probability (using prob_within for display)
      const probMap = new Map();
      data.probabilities.forEach(row => {
        probMap.set(Math.round(row.strike), row.prob_within);
      });
      return probMap;
    }
    return null;
  } catch (e) {
    console.error('Probability fetch error:', e);
    return null;
  }
}

// PATCHED updateStrikeTable to use model-based probabilities for RISK
async function updateStrikeTable(coreData, latestKalshiMarkets) {
  const strikeTableBody = document.querySelector('#strike-table tbody');
  if (!coreData || typeof coreData.btc_price !== 'number') return;

  const base = Math.round(coreData.btc_price / 250) * 250;
  const ttcSeconds = coreData.ttc_seconds || 1;
  const ttcMinutes = ttcSeconds / 60;
  const centerPrice = coreData.btc_price;
  const symbol = getSelectedSymbol ? getSelectedSymbol() : 'BTC';
  const year = '2021'; // TODO: make dynamic if needed

  // Remove any existing spanner rows first
  // strikeTableBody.querySelectorAll('.spanner-row').forEach(row => row.remove());

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

  // Find the correct index to insert the spanner row - STABLE PLACEMENT
  let spannerIndex = strikeRows.length; // default to end
  for (let i = 0; i < strikes.length; i++) {
    const strike = strikes[i];
    if (centerPrice < strike) {
      spannerIndex = i;
      break;
    }
  }

  window.strikeRowsMap.forEach((cells, strike) => {
    const { row, bufferTd, bmTd, probTd, yesSpan, noSpan } = cells;

    // Buffer
    const buffer = centerPrice - strike;
    bufferTd.textContent = Math.abs(buffer).toLocaleString(undefined, {maximumFractionDigits: 0});

    // B/M
    const bpm = Math.abs(buffer) / ttcMinutes;
    bmTd.textContent = Math.round(bpm).toLocaleString();

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
      yesSpan.textContent = yesAsk > 0 ? yesAsk : '—';
      noSpan.textContent = noAsk > 0 ? noAsk : '—';
      yesSpan.className = 'price-box disabled';
      noSpan.className = 'price-box disabled';
      yesSpan.style.cursor = 'default';
      noSpan.style.cursor = 'default';
      yesSpan.onclick = null;
      noSpan.onclick = null;
      // Set data attributes for reference
      if (ticker) {
        yesSpan.setAttribute('data-ticker', ticker);
        noSpan.setAttribute('data-ticker', ticker);
      }
      yesSpan.setAttribute('data-strike', strike);
      yesSpan.setAttribute('data-side', 'yes');
      noSpan.setAttribute('data-strike', strike);
      noSpan.setAttribute('data-side', 'no');
    } else if (window.plusMinusMode) {
      // DIFF mode
      let prob = probMap && probMap.has(strike) ? probMap.get(strike) : null;
      let yesDisplay = '—';
      let noDisplay = '—';
      let yesEdge = null;
      let noEdge = null;
      if (prob !== null && prob !== undefined) {
        if (strike < centerPrice) {
          // BELOW money line
          yesEdge = prob - yesAsk;
          noEdge = 100 - prob - noAsk;
        } else if (strike > centerPrice) {
          // ABOVE money line
          yesEdge = 100 - prob - yesAsk;
          noEdge = prob - noAsk;
        } else {
          // At the money
          yesEdge = prob - yesAsk;
          noEdge = 100 - prob - noAsk;
        }
        if (yesAsk > 0) {
          let val = Math.round(yesEdge);
          yesDisplay = (val > 0 ? '+' : '') + val;
        }
        if (noAsk > 0) {
          let val = Math.round(noEdge);
          noDisplay = (val > 0 ? '+' : '') + val;
        }
      }
      yesSpan.textContent = yesDisplay;
      noSpan.textContent = noDisplay;

      // In DIFF mode, both buttons are independently active if their own ask/volume is valid and ask != 100
      const isYesActive = (volume >= 1000) && (yesAsk !== 100);
      const isNoActive = (volume >= 1000) && (noAsk !== 100);

      yesSpan.className = isYesActive ? 'price-box' : 'price-box disabled';
      noSpan.className = isNoActive ? 'price-box' : 'price-box disabled';
      yesSpan.style.cursor = isYesActive ? 'pointer' : 'default';
      noSpan.style.cursor = isNoActive ? 'pointer' : 'default';

      // Set data attributes for openTrade
      if (ticker) {
        yesSpan.setAttribute('data-ticker', ticker);
        noSpan.setAttribute('data-ticker', ticker);
      }
      yesSpan.setAttribute('data-strike', strike);
      yesSpan.setAttribute('data-side', 'yes');
      noSpan.setAttribute('data-strike', strike);
      noSpan.setAttribute('data-side', 'no');

      // Attach click handlers if active
      if (isYesActive) {
        yesSpan.onclick = debounce(function(event) {
          const btn = yesSpan;
          const tradeData = window.prepareTradeData ? window.prepareTradeData(btn) : null;
          if (tradeData) {
            window.executeTrade(tradeData);
          }
        }, 300);
      } else {
        yesSpan.onclick = null;
      }
      if (isNoActive) {
        noSpan.onclick = debounce(function(event) {
          const btn = noSpan;
          const tradeData = window.prepareTradeData ? window.prepareTradeData(btn) : null;
          if (tradeData) {
            window.executeTrade(tradeData);
          }
        }, 300);
      } else {
        noSpan.onclick = null;
      }
    } else {
      // PRICE mode
      const isYesActive = (volume >= 1000) && yesAsk > noAsk && yesAsk < 99 && yesAsk >= 40;
      const isNoActive = (volume >= 1000) && noAsk > yesAsk && noAsk < 99 && noAsk >= 40;
      updateYesNoButton(yesSpan, strike, "yes", yesAsk, isYesActive, ticker);
      updateYesNoButton(noSpan, strike, "no", noAsk, isNoActive, ticker);
    }
    updatePositionIndicator(cells.row.children[0], strike);
  });

  // --- GUARANTEED SPANNER ROW LOGIC ---
  console.log('[SPANNER] strikeRows.length:', strikeRows.length);
  if (strikeRows.length > 0) {
    // Always check for spanner row after all strike rows are rendered
    let spannerRow = strikeTableBody.querySelector('.spanner-row');
    const allRows = Array.from(strikeTableBody.children);
    console.log('[SPANNER] allRows:', allRows.map(r => r.className));
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
      console.log('[SPANNER] Creating spanner row at index', insertIndex);
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
        console.log('[SPANNER] Moving spanner row from', currentSpannerIndex, 'to', insertIndex);
        if (insertIndex < allRows.length) {
          strikeTableBody.insertBefore(spannerRow, allRows[insertIndex]);
        } else {
          strikeTableBody.appendChild(spannerRow);
        }
      } else {
        console.log('[SPANNER] Spanner row already at correct position', insertIndex);
      }
    }
  }
  
  if (typeof window.addStrikeTableClickHandlers === 'function') window.addStrikeTableClickHandlers();
  // Sync watchlist with live strike table data
  if (typeof window.syncWatchlistWithStrikeTable === 'function') {
    setTimeout(() => {
      console.log('[STRIKE TABLE] Strike table updated, syncing watchlist');
      window.syncWatchlistWithStrikeTable();
    }, 100);
  } else {
    console.log('[STRIKE TABLE] syncWatchlistWithStrikeTable function not found');
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
      console.log('[DEBUG] Setting background color for', strikeCell, 'to #1a2a1a');
      strikeCell.style.backgroundColor = '#1a2a1a'; // Very subtle green tint
      strikeCell.style.borderLeft = '3px solid #45d34a'; // Green left border
    } else {
      console.log('[DEBUG] Clearing background color for', strikeCell);
      strikeCell.style.backgroundColor = '';
      strikeCell.style.borderLeft = '';
    }
  } catch (e) {
    console.error('Error updating position indicator:', e);
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
function updateYesNoButton(spanEl, strike, side, askPrice, isActive, ticker = null, forceRefresh = false) {
  const key = `${strike}-${side}`;
  const prev = lastButtonStates.get(key);
  if (!forceRefresh && !window.forceButtonRefresh && prev && prev.askPrice === askPrice && prev.isActive === isActive) {
    // No change; skip update
    return;
  }

  spanEl.textContent = askPrice > 0 ? askPrice : '—';
  spanEl.className = isActive ? 'price-box' : 'price-box disabled';
  spanEl.style.cursor = isActive ? 'pointer' : 'default';

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

  if (isActive) {
    spanEl.onclick = debounce(function(event) {
      // Use centralized trade controller
      if (typeof window.prepareTradeData === 'function' && typeof window.executeTrade === 'function') {
        const tradeData = window.prepareTradeData(spanEl);
        if (tradeData) {
          window.executeTrade(tradeData);
        }
      } else {
        console.error('Centralized trade controller not available');
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

// Function to immediately redraw all YES/NO buttons when DIF mode changes
function redrawYesNoButtonsForDIFMode() {
  console.log('FORCE REDRAWING ALL YES/NO BUTTONS for DIF mode change to:', window.plusMinusMode);
  
  // Set global flag to force refresh
  window.forceButtonRefresh = true;
  
  // Clear the button state cache to force full redraw
  if (window.lastButtonStates) {
    window.lastButtonStates.clear();
  }
  
  // Force immediate redraw of all buttons using current data
  if (window.strikeRowsMap && window.strikeRowsMap.size > 0) {
    // Get current data from the page
    const btcPriceEl = document.getElementById('btc-price');
    const centerPrice = btcPriceEl ? parseFloat(btcPriceEl.textContent.replace(/[^\d.-]/g, '')) : null;
    
    if (centerPrice) {
      // Create minimal core data object
      const coreData = { btc_price: centerPrice, ttc_seconds: 60 };
      
      // Reconstruct market data from current DOM state
      const latestKalshiMarkets = [];
      window.strikeRowsMap.forEach((cells, strike) => {
        const { yesSpan, noSpan } = cells;
        const ticker = yesSpan.getAttribute('data-ticker') || noSpan.getAttribute('data-ticker');
        
        if (ticker) {
          // Extract current values and reconstruct original prices
          let yesAsk = 0;
          let noAsk = 0;
          
          const yesText = yesSpan.textContent;
          const noText = noSpan.textContent;
          
          // If switching FROM DIF mode, reconstruct original prices from differences
          if (!window.plusMinusMode) {
            const probCell = cells.probTd;
            const probText = probCell ? probCell.textContent : '—';
            const prob = probText !== '—' ? parseFloat(probText) : null;
            
            if (prob !== null && !isNaN(prob)) {
              if (strike < centerPrice && yesText !== '—' && yesText.includes('+')) {
                const diff = parseFloat(yesText.replace(/[^\d.-]/g, ''));
                if (!isNaN(diff)) {
                  yesAsk = Math.round(prob - diff);
                }
              } else if (strike > centerPrice && noText !== '—' && noText.includes('+')) {
                const diff = parseFloat(noText.replace(/[^\d.-]/g, ''));
                if (!isNaN(diff)) {
                  noAsk = Math.round(prob - diff);
                }
              }
            }
          } else {
            // If switching TO DIF mode, current values should be prices
            if (yesText && yesText !== '—' && !yesText.includes('+') && !yesText.includes('-')) {
              yesAsk = parseFloat(yesText) || 0;
            }
            if (noText && noText !== '—' && !noText.includes('+') && !noText.includes('-')) {
              noAsk = parseFloat(noText) || 0;
            }
          }
          
          latestKalshiMarkets.push({
            ticker: ticker,
            floor_strike: strike,
            yes_ask: yesAsk,
            no_ask: noAsk
          });
        }
      });
      
      // Call updateStrikeTable with reconstructed data
      if (typeof updateStrikeTable === 'function') {
        console.log('Calling updateStrikeTable with reconstructed data to force complete redraw');
        updateStrikeTable(coreData, latestKalshiMarkets);
      }
      
      // Reset the force refresh flag after a short delay
      setTimeout(() => {
        window.forceButtonRefresh = false;
      }, 100);
    }
  }
}

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
    const contractMatch = window.CurrentMarketTitleRaw.match(/at\s(.+?)\s*(?:EDT|EST|PDT|PST)?\?/i);
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

// Play a sound by type, allowing overlapping playback
function playSound(type) {
  const soundId = type === 'open' ? 'openTradeSound' : 'closeTradeSound';
  const original = document.getElementById(soundId);
  if (!original) return;

  const clone = original.cloneNode(true); // Allow overlapping playback
  clone.volume = type === 'open' ? 0.1 : 0.2; // Set volume inline
  clone.play().catch(err => console.error(`Failed to play sound clone:`, err));
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
window.redrawYesNoButtonsForDIFMode = redrawYesNoButtonsForDIFMode;
window.addStrikeTableRowClickHandlers = addStrikeTableRowClickHandlers;

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

// === STRIKE TABLE ROW CLICK HANDLERS ===
// Global watchlist state (like the old watchlist.js)
let strikeTableWatchlistData = [];

// Load current watchlist on page load
async function loadStrikeTableWatchlist() {
  try {
    const response = await fetch('/api/get_watchlist');
    const data = await response.json();
    strikeTableWatchlistData = data.watchlist || [];
    console.log('Loaded watchlist for strike table:', strikeTableWatchlistData);
  } catch (error) {
    console.error('Error loading watchlist for strike table:', error);
  }
}

// Save watchlist to preferences (like the old watchlist.js)
async function saveStrikeTableWatchlist() {
  try {
    console.log('Saving watchlist from strike table:', strikeTableWatchlistData);
    const response = await fetch('/api/set_watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ watchlist: strikeTableWatchlistData })
    });
    if (!response.ok) {
      console.error('Failed to save watchlist:', response.status);
    } else {
      console.log('Watchlist saved successfully from strike table');
    }
  } catch (error) {
    console.error('Error saving watchlist from strike table:', error);
  }
}

function addStrikeTableRowClickHandlers() {
  const strikeTable = document.getElementById('strike-table');
  if (!strikeTable) return;
  const rows = strikeTable.querySelectorAll('tbody tr');
  rows.forEach(row => {
    // Set pointer cursor and title for first 4 columns
    Array.from(row.children).forEach((cell, idx) => {
      if (idx >= 0 && idx <= 3) {
        cell.style.cursor = 'pointer';
        cell.title = 'Click to add to watchlist';
      } else {
        cell.style.cursor = 'default';
        cell.title = '';
      }
    });
    // Remove any previous click handler
    row.removeEventListener('click', row._strikeTableClickHandler);
    // Attach new click handler
    const clickHandler = (event) => {
      const cell = event.target.closest('td');
      if (!cell) return;
      const cellIndex = Array.from(row.children).indexOf(cell);
      if (cellIndex >= 0 && cellIndex <= 3) {
        const strikeCell = row.children[0];
        if (!strikeCell) return;
        const strike = parseFloat(strikeCell.textContent.replace(/[$,]/g, ''));
        if (!isNaN(strike)) {
          // Add to local watchlist array (like the old watchlist.js)
          if (!strikeTableWatchlistData.includes(strike)) {
            strikeTableWatchlistData.push(strike);
            console.log('Added strike to watchlist:', strike);
            console.log('Updated watchlist:', strikeTableWatchlistData);
            
            // Visual feedback - flash the row
            row.classList.add('strike-row-flash');
            setTimeout(() => {
              row.classList.remove('strike-row-flash');
            }, 550);
            
            // Save the entire updated array to backend
            saveStrikeTableWatchlist();
            
            // Refresh the watchlist display
            if (typeof window.refreshWatchlist === 'function') {
              setTimeout(() => {
                console.log('[STRIKE TABLE] Refreshing watchlist after adding strike');
                window.refreshWatchlist();
              }, 100);
            } else {
              console.log('[STRIKE TABLE] refreshWatchlist function not found');
            }
          } else {
            console.log('Strike already in watchlist:', strike);
          }
        }
      }
    };
    row._strikeTableClickHandler = clickHandler;
    row.addEventListener('click', clickHandler);
  });
}

// Attach handlers after table is rendered
if (typeof window !== 'undefined') {
  document.addEventListener('DOMContentLoaded', async () => {
    // Load current watchlist first
    await loadStrikeTableWatchlist();
    addStrikeTableRowClickHandlers();
    // Also re-attach after every update
    const originalUpdateStrikeTable = window.updateStrikeTable;
    if (originalUpdateStrikeTable) {
      window.updateStrikeTable = function(...args) {
        originalUpdateStrikeTable.apply(this, args);
        setTimeout(() => {
          addStrikeTableRowClickHandlers();
        }, 100);
      };
    }
  });
} 

// === STRIKE TABLE WEBSOCKET UPDATES ===
// WebSocket connection for real-time database change notifications
let dbChangeWebSocket = null;

function connectDbChangeWebSocket() {
  if (dbChangeWebSocket && dbChangeWebSocket.readyState === WebSocket.OPEN) {
    return; // Already connected
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/db_changes`;
  
  dbChangeWebSocket = new WebSocket(wsUrl);
  
  dbChangeWebSocket.onopen = function() {
    console.log('[STRIKE TABLE] WebSocket connected for database changes');
  };
  
  dbChangeWebSocket.onmessage = function(event) {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'db_change' && data.database === 'trades') {
        console.log('[STRIKE TABLE] Received trades.db change notification, updating...');
        fetchAndRenderStrikeTable();
      }
    } catch (error) {
      console.error('[STRIKE TABLE] Error parsing WebSocket message:', error);
    }
  };
  
  dbChangeWebSocket.onclose = function() {
    console.log('[STRIKE TABLE] WebSocket disconnected, attempting to reconnect...');
    setTimeout(connectDbChangeWebSocket, 3000);
  };
  
  dbChangeWebSocket.onerror = function(error) {
    console.error('[STRIKE TABLE] WebSocket error:', error);
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
} 

 