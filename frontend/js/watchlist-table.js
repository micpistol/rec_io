// === WATCHLIST TABLE MODULE ===
// This module handles the watchlist table - shows exactly what's in the watchlist DB table

// === WATCHLIST DATA FETCHING ===

// Fetch watchlist data from the PostgreSQL endpoint
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
  // Initial load
  updateWatchlistTable();
  
  // Set up periodic updates (every 2 seconds)
  setInterval(updateWatchlistTable, 2000);
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
    
    // COMPLETELY REBUILD THE TABLE FROM SCRATCH
    watchlistTableBody.innerHTML = '';
    
    // Sort strikes by probability (highest to lowest)
    const sortedStrikes = data.strikes.sort((a, b) => b.probability - a.probability);
    
    // Show only the strikes that are in the database
    sortedStrikes.forEach((strikeData) => {
      const row = document.createElement('tr');
      const strike = strikeData.strike;
      
      // Strike cell
      const strikeTd = document.createElement('td');
      strikeTd.textContent = '$' + strike.toLocaleString();
      strikeTd.classList.add('center');
      row.appendChild(strikeTd);
      
      // Buffer cell
      const bufferTd = document.createElement('td');
      bufferTd.textContent = strikeData.buffer.toLocaleString(undefined, {maximumFractionDigits: 0});
      bufferTd.classList.add('center');
      row.appendChild(bufferTd);
      
      // B/M cell
      const bmTd = document.createElement('td');
      bmTd.textContent = strikeData.buffer_pct.toFixed(2);
      bmTd.classList.add('center');
      row.appendChild(bmTd);
      
      // Probability cell
      const probTd = document.createElement('td');
      const prob = strikeData.probability;
      probTd.textContent = prob.toFixed(1);
      probTd.classList.add('center');
      row.appendChild(probTd);
      
      // Side cell
      const sideTd = document.createElement('td');
      const activeSide = strikeData.active_side;
      sideTd.textContent = activeSide ? activeSide.toUpperCase() : '—';
      sideTd.classList.add('center');
      row.appendChild(sideTd);
      
      // Buy button cell
      const buyTd = document.createElement('td');
      buyTd.setAttribute('data-ticker', strikeData.ticker || '');
      buyTd.classList.add('center');
      const buySpan = document.createElement('span');
      buyTd.appendChild(buySpan);
      row.appendChild(buyTd);
      
      // Risk color coding
      row.classList.remove('ultra-safe', 'safe', 'caution', 'high-risk', 'danger-stop');
      let riskClass = '';
      if (prob >= 98) riskClass = 'ultra-safe';
      else if (prob >= 95) riskClass = 'safe';
      else if (prob >= 80) riskClass = 'caution';
      else riskClass = 'high-risk';
      row.classList.add(riskClass);
      
      // Update buy button
      const yesAsk = strikeData.yes_ask;
      const noAsk = strikeData.no_ask;
      const volume = strikeData.volume;
      const ticker = strikeData.ticker;
      const activeSide = strikeData.active_side;
      
      let activeAsk = null;
      let activeEnabled = false;
      
      if (activeSide === 'yes') {
        activeAsk = yesAsk;
        activeEnabled = yesAsk <= 98 && parseInt(volume) >= 1000;
      } else if (activeSide === 'no') {
        activeAsk = noAsk;
        activeEnabled = noAsk <= 98 && parseInt(volume) >= 1000;
      }
      
      updateWatchlistBuyButton(buySpan, strike, activeSide, activeAsk, activeEnabled, ticker);
      
      // Update position indicator
      updateWatchlistPositionIndicator(strikeTd, strike);
      
      // Add row to table
      watchlistTableBody.appendChild(row);
    });
    
  } catch (error) {
    console.error('Error updating watchlist table:', error);
  }
}

// === WATCHLIST BUY BUTTON FUNCTION ===

function updateWatchlistBuyButton(spanEl, strike, side, askPrice, isActive, ticker = null) {
  // Determine display value
  let displayValue = '—';
  if (askPrice && askPrice !== '—' && askPrice !== 0) {
    displayValue = askPrice;
  }
  
  spanEl.textContent = displayValue;
  spanEl.className = isActive ? 'price-box' : 'price-box disabled';
  spanEl.style.cursor = isActive ? 'pointer' : 'default';
  
  // Set data attributes
  if (spanEl.parentElement && ticker) {
    spanEl.parentElement.setAttribute('data-ticker', ticker);
  }
  if (ticker) {
    spanEl.setAttribute('data-ticker', ticker);
  }
  spanEl.setAttribute('data-strike', strike);
  spanEl.setAttribute('data-side', side);
  if (askPrice && askPrice !== '—' && askPrice !== 0) {
    spanEl.setAttribute('data-ask-price', askPrice);
  } else {
    spanEl.removeAttribute('data-ask-price');
  }

  if (isActive) {
    spanEl.onclick = debounce(async function(event) {
      try {
        const tradeData = await prepareTradeData(spanEl);
        
        if (!tradeData) {
          console.error('Missing trade data for watchlist button');
          return;
        }
        
        const response = await fetch('/api/trigger_open_trade', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            strike: tradeData.strike,
            side: tradeData.side,
            ticker: tradeData.ticker,
            buy_price: tradeData.buy_price,
            prob: tradeData.prob,
            symbol_open: tradeData.symbol_open,
            momentum: tradeData.momentum,
            contract: tradeData.contract,
            symbol: tradeData.symbol,
            position: tradeData.position,
            trade_strategy: tradeData.trade_strategy
          })
        });
        
        if (response.ok) {
          const result = await response.json();
          
          // Refresh panels to show new trade
          if (typeof fetchAndRenderTrades === 'function') {
            fetchAndRenderTrades();
          }
          if (typeof fetchAndRenderRecentTrades === 'function') {
            fetchAndRenderRecentTrades();
          }
        } else {
          console.error('Watchlist trade initiation failed:', response.status);
        }
      } catch (error) {
        console.error('Error initiating watchlist trade:', error);
      }
    }, 300);
  } else {
    spanEl.onclick = null;
  }
}

// === WATCHLIST POSITION INDICATOR ===

async function updateWatchlistPositionIndicator(strikeCell, strike) {
  try {
    const tradesRes = await fetch('/api/active_trades', { cache: 'no-store' });
    if (!tradesRes.ok) return;
    
    const data = await tradesRes.json();
    const activeTrades = data.active_trades || [];
    
    const hasPosition = activeTrades.some(trade => {
      const tradeStrike = parseFloat(trade.strike.replace(/[^\d.-]/g, ''));
      return tradeStrike === strike;
    });
    
    if (hasPosition) {
      strikeCell.style.backgroundColor = '#1a2a1a';
      strikeCell.style.borderLeft = '3px solid #45d34a';
    } else {
      strikeCell.style.backgroundColor = '';
      strikeCell.style.borderLeft = '';
    }
  } catch (e) {
    console.error(`[WATCHLIST POSITION INDICATOR] Error checking position for strike ${strike}:`, e);
    strikeCell.style.backgroundColor = '';
    strikeCell.style.borderLeft = '';
  }
}

// === WATCHLIST UTILITY FUNCTIONS ===

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

document.addEventListener('DOMContentLoaded', function() {
  setTimeout(() => {
    initializeWatchlistTable();
  }, 500);
});

// Export functions for global access
window.updateWatchlistTable = updateWatchlistTable;
window.updateWatchlistPositionIndicator = updateWatchlistPositionIndicator; 