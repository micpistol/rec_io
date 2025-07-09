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

    // Adj B/M cell
    const adjBmTd = document.createElement('td');
    row.appendChild(adjBmTd);

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
      adjBmTd,
      probTd,
      yesSpan,
      noSpan
    });
  });
}

// === STRIKE TABLE UPDATE LOGIC ===

async function fetchProbabilities(symbol, currentPrice, ttcMinutes, strikes, year = null) {
  try {
    // Use the correct fingerprint for BTC (from the working test)
    const fingerprint = [2.14e-7, -1.95, 0.98];
    
    const res = await fetch('http://localhost:5001/api/strike_probabilities', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fingerprint: fingerprint,
        current_price: currentPrice,
        ttc_minutes: ttcMinutes,
        strikes: strikes
      })
    });
    const data = await res.json();
    console.log('[STRIKE TABLE] API Response:', data); // DEBUG LOG
    if (data.status === 'ok' && Array.isArray(data.probabilities)) {
      // Map: strike -> probability
      const probMap = new Map();
      data.probabilities.forEach(row => {
        probMap.set(Math.round(row['Strike']), row['Prob Touch (%)']);
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
    const { row, bufferTd, bmTd, adjBmTd, probTd, yesSpan, noSpan } = cells;

    // Buffer
    const buffer = centerPrice - strike;
    bufferTd.textContent = Math.abs(buffer).toLocaleString(undefined, {maximumFractionDigits: 0});

    // B/M and Adj B/M
    const bpm = Math.abs(buffer) / ttcMinutes;
    const adjBpm = bpm * Math.sqrt(ttcMinutes / 15);
    bmTd.textContent = Math.round(bpm).toLocaleString();
    adjBmTd.textContent = adjBpm.toFixed(1);

    // --- PATCH: Use model-based probability for Prob Touch (%) ---
    let prob = probMap && probMap.has(strike) ? probMap.get(strike) : null;
    if (prob !== null && prob !== undefined) {
      // Invert the probability for display
      probTd.textContent = (100 - prob).toFixed(1);
      row.className = '';
    } else {
      probTd.textContent = '—';
      row.className = '';
    }
    // --- END PATCH ---

    // Find markets for yes/no asks - use more flexible matching
    const matchingMarket = latestKalshiMarkets.find(m => {
      const marketStrike = Math.round(m.floor_strike);
      return marketStrike === strike || Math.abs(marketStrike - strike) <= 1;
    });
    const ticker = matchingMarket ? matchingMarket.ticker : null;
    const yesAsk = matchingMarket && typeof matchingMarket.yes_ask === "number" ? Math.round(matchingMarket.yes_ask) : 0;
    const noAsk = matchingMarket && typeof matchingMarket.no_ask === "number" ? Math.round(matchingMarket.no_ask) : 0;
    const isYesActive = yesAsk > noAsk && yesAsk < 99 && yesAsk >= 40;
    const isNoActive = noAsk > yesAsk && noAsk < 99 && noAsk >= 40;
    updateYesNoButton(yesSpan, strike, "yes", yesAsk, isYesActive, ticker);
    updateYesNoButton(noSpan, strike, "no", noAsk, isNoActive, ticker);
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
function updateYesNoButton(spanEl, strike, side, askPrice, isActive, ticker = null) {
  const key = `${strike}-${side}`;
  const prev = lastButtonStates.get(key);
  if (prev && prev.askPrice === askPrice && prev.isActive === isActive) {
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
      openTrade(spanEl);
    }, 300);
  } else {
    spanEl.onclick = null;
  }

  lastButtonStates.set(key, { askPrice, isActive });
}

// === TRADE EXECUTION ===

function openTrade(target) {
  // Play sound and popup immediately
  playSound('open');
  showTradeOpenedPopup();

  const btn = target;
  if (btn?.disabled) return;
  btn.disabled = true;

  // --- Visual feedback: row flash highlight ---
  let row = btn.closest('tr');
  if (row) {
    row.classList.add('strike-row-flash');
    setTimeout(() => row.classList.remove('strike-row-flash'), 600);
  }

  // --- Immediately trigger trade table update (no debounce, no delay, no backend wait) ---
  fetchAndRenderTrades();

  // Defer backend logic to next tick to decouple from UI thread
  setTimeout(() => {
    (async () => {
      try {
        const now = new Date();
        const btnText = btn?.textContent?.trim() || '';
        // Convert prices like 96 to 0.96
        const buy_price = parseFloat((parseFloat(btnText) / 100).toFixed(2));

        const posInput = document.getElementById('position-size');
        const rawBasePos = posInput ? parseInt(posInput.value, 10) : NaN;
        const validBase = Number.isFinite(rawBasePos) && rawBasePos > 0 ? rawBasePos : null;

        const multiplierBtn = document.querySelector('.multiplier-btn.active');
        const multiplier = multiplierBtn ? parseInt(multiplierBtn.dataset.multiplier, 10) : 1;

        const position = validBase !== null ? validBase * multiplier : null;

        const symbol = getSelectedSymbol();
        const contract = getTruncatedMarketTitle();
        // Get the strike and side from data attributes on the parent td or span
        let strike = null;
        let side = null;
        // Attempt to find strike and side from parent td or span
        // Find the row
        let row2 = btn.closest('tr');
        if (row2) {
          // First td is strike cell
          const strikeCell = row2.querySelector('td');
          if (strikeCell) {
            // Remove $ and commas, parse as number
            strike = parseFloat(strikeCell.textContent.replace(/\$|,/g, ''));
          }
          // Determine side by column index
          const tds = Array.from(row2.children);
          for (let i = 0; i < tds.length; ++i) {
            if (tds[i].contains(btn)) {
              if (i === 5) side = 'yes';
              if (i === 6) side = 'no';
            }
          }
        }
        // Fallback: try to get from btn.dataset
        if (!strike && btn.dataset.strike) strike = parseFloat(btn.dataset.strike);
        if (!side && btn.dataset.side) side = btn.dataset.side;
        // Get ticker from data-ticker attribute (on td or span)
        let kalshiTicker = btn.dataset.ticker || null;
        if (!kalshiTicker && btn.parentElement && btn.parentElement.dataset.ticker) {
          kalshiTicker = btn.parentElement.dataset.ticker;
        }
        // Fallback: try to find from latestKalshiMarkets if available
        if (!kalshiTicker && window.latestKalshiMarkets && Array.isArray(window.latestKalshiMarkets) && strike != null) {
          const match = window.latestKalshiMarkets.find(m => Math.round(m.floor_strike) === strike);
          if (match) kalshiTicker = match.ticker;
        }
        const symbol_open = getCurrentBTCTickerPrice();
        const momentum = getCurrentMomentumScore();
        // Use window.coreData for volatility if present
        const volatility = window.coreData?.volatility_score != null
          ? parseFloat(window.coreData.volatility_score.toFixed(2))
          : null;

        // === Generate unique ticket ID just before payload definition ===
        const ticket_id = 'TICKET-' + Math.random().toString(36).substr(2, 9) + '-' + Date.now();

        // === Immediately log the initial entry to backend ===
        fetch('/api/log_event', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ticket_id: ticket_id,
            message: "MONITOR: TICKET INITIATED — CONFIRMED"
          })
        });
        // === Prune old trade logs right after logging event ===
        fetch('/api/prune_trade_logs', { method: 'POST' });

        // === Construct new payload as specified ===
        const payload = {
          ticket_id:         ticket_id,
          status:            "pending",
          date:              now.toISOString().split("T")[0],
          time:              now.toLocaleTimeString('en-US', { hour12: false }),
          symbol:            symbol,
          market:            "Kalshi",
          trade_strategy:    "Hourly HTC",
          contract:          contract,
          strike:            `$${Number(strike).toLocaleString()}`,
          side:              side && side.toUpperCase() === 'YES' ? 'Y' : (side && side.toUpperCase() === 'NO' ? 'N' : (side ? side[0].toUpperCase() : null)),
          ticker:            kalshiTicker,
          buy_price:         buy_price,
          // position will be set below if valid
          symbol_open:       symbol_open,
          symbol_close:      null,
          momentum:          momentum,
          momentum_delta:    null,
          volatility:        volatility,
          volatility_delta:  null,
          win_loss:          null
        };
        if (position !== null) {
          payload.position = position;
        }

        // 🔍 Log to console for now — we'll send this to backend and executor in next step
        console.log("Prepared trade payload:", payload);

        fetch('/trades', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        })
        .then(() => {
          // (Optionally, trigger another refresh here, but already done above)
          fetchAndRenderRecentTrades();
        })
        .catch(err => console.error('Failed to open trade:', err))
        .finally(() => setTimeout(() => (btn.disabled = false), 500));
      } catch (err) {
        console.error('Failed to open trade:', err);
        setTimeout(() => (btn.disabled = false), 500);
      }
    })();
  }, 0);
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
window.openTrade = openTrade;
window.updateYesNoButton = updateYesNoButton;
window.updatePositionIndicator = updatePositionIndicator;

// === Spanner Row Helper ===
function createSpannerRow(currentPrice) {
  const spannerRow = document.createElement("tr");
  spannerRow.className = "spanner-row";
  const spannerTd = document.createElement("td");
  spannerTd.colSpan = 7;
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

// === Add-to-Watchlist Click Handlers ===
function addStrikeTableClickHandlers() {
  const strikeTable = document.getElementById('strike-table');
  if (!strikeTable) return;
  const rows = strikeTable.querySelectorAll('tbody tr');
  rows.forEach(row => {
    // Remove existing click handlers first
    row.removeEventListener('click', row._watchlistClickHandler);
    // Check if RECO is enabled - if so, don't add click handlers
    if (window.recoEnabled) {
      row.style.cursor = 'default';
      row.title = 'RECO mode - manual selection disabled';
      Array.from(row.children).forEach((cell, idx) => {
        if (idx >= 0 && idx <= 4) {
          cell.style.cursor = 'default';
          cell.title = 'RECO mode - manual selection disabled';
        } else {
          cell.style.cursor = 'default';
          cell.title = '';
        }
      });
      return; // Skip adding click handlers when RECO is enabled
    }
    // RECO is disabled - add normal click handlers
    row.style.cursor = '';
    row.title = '';
    Array.from(row.children).forEach((cell, idx) => {
      if (idx >= 0 && idx <= 4) {
        cell.style.cursor = 'pointer';
        cell.title = 'Click to add to watchlist';
      } else {
        cell.style.cursor = 'default';
        cell.title = '';
      }
    });
    const clickHandler = (event) => {
      // Only trigger if not clicking on YES or NO columns (6 or 7)
      const cell = event.target.closest('td');
      if (!cell) return;
      const cellIndex = Array.from(row.children).indexOf(cell);
      if (cellIndex === 5 || cellIndex === 6) return; // YES or NO columns
      if (typeof window.addToWatchlist === 'function') window.addToWatchlist(row);
    };
    row._watchlistClickHandler = clickHandler;
    row.addEventListener('click', clickHandler);
  });
}
window.addStrikeTableClickHandlers = addStrikeTableClickHandlers;

// === WATCHLIST FUNCTIONS moved to watchlist.js === 