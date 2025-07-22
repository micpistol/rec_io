
// === CENTRALIZED TRADE EXECUTION CONTROLLER ===
// This file centralizes ALL trade execution to prevent multiple functions
// and add proper safety controls for live money trading

// Global configuration
window.TRADE_CONFIG = {
  DEMO_MODE: false,  // Set to false for live trading
  MAX_POSITION_SIZE: 1000,
  ENABLE_SOUNDS: true,
  ENABLE_POPUPS: true
};

// Trade execution state
window.TRADE_STATE = {
  isExecuting: false,
  lastTradeId: null,
  pendingTrades: new Set(),
  executedTrades: new Set()
};

// === CENTRALIZED TRADE EXECUTION FUNCTION ===
// This is the ONLY function that should execute trades
window.executeTrade = async function(tradeData) {
  // Prevent multiple simultaneous executions
  if (window.TRADE_STATE.isExecuting) {
    return { success: false, error: 'Trade already executing' };
  }

  // Validate trade data
  if (!tradeData || !tradeData.symbol || !tradeData.side || !tradeData.buy_price) {
    return { success: false, error: 'Invalid trade data' };
  }

  // Check position size limits
  if (tradeData.position && tradeData.position > window.TRADE_CONFIG.MAX_POSITION_SIZE) {
    return { success: false, error: 'Position size too large' };
  }

  // Generate unique ticket ID
  const ticket_id = 'TICKET-' + Math.random().toString(36).substr(2, 9) + '-' + Date.now();
  
  // Add to pending trades
  window.TRADE_STATE.pendingTrades.add(ticket_id);
  window.TRADE_STATE.isExecuting = true;

  try {
    // Create the trade payload
    // Force Eastern Time Zone for all dates and times
    const now = new Date();
    const easternTime = new Date(now.toLocaleString("en-US", {timeZone: "America/New_York"}));
    const easternDate = easternTime.toLocaleDateString('en-CA'); // YYYY-MM-DD format
    const easternTimeString = easternTime.toLocaleTimeString('en-US', { hour12: false });
    
    // Patch: Format momentum as integer (e.g., 0.04 -> 4)
    let rawMomentum = tradeData.momentum;
    let momentum = 0;
    if (rawMomentum !== undefined && rawMomentum !== null && rawMomentum !== "") {
      momentum = Math.round(parseFloat(rawMomentum) * 100);
    }

    const payload = {
      ticket_id: ticket_id,
      status: "pending",
      date: easternDate,
      time: easternTimeString,
      symbol: tradeData.symbol,
      market: "Kalshi",
      trade_strategy: tradeData.trade_strategy || "Hourly HTC",
      contract: tradeData.contract,
      strike: tradeData.strike,
      side: tradeData.side,
      ticker: tradeData.ticker,
      buy_price: tradeData.buy_price,
      symbol_open: tradeData.symbol_open,
      symbol_close: null,
      momentum: momentum, // PATCHED: send formatted integer
      prob: tradeData.prob,
      
      
      win_loss: null
    };

    if (tradeData.position !== null) {
      payload.position = tradeData.position;
    }

    // === DEMO MODE CHECK ===
    if (window.TRADE_CONFIG.DEMO_MODE) {
      // Audio alert already played in trade_monitor.html when button was clicked
      window.TRADE_STATE.executedTrades.add(ticket_id);
      window.TRADE_STATE.lastTradeId = ticket_id;
      return { 
        success: true, 
        ticket_id: ticket_id, 
        demo: true,
        message: 'Demo trade created successfully'
      };
    }

    // Execute the actual trade
    const response = await fetch('/trades', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Trade execution failed: ${response.status}`);
    }

    const result = await response.json();
    
    // Add to executed trades
    window.TRADE_STATE.executedTrades.add(ticket_id);
    window.TRADE_STATE.lastTradeId = ticket_id;

    // Audio alert already played in trade_monitor.html when button was clicked

    return { 
      success: true, 
      ticket_id: ticket_id, 
      demo: false,
      result: result
    };

  } catch (error) {
    return { 
      success: false, 
      error: error.message,
      ticket_id: ticket_id
    };
  } finally {
    // Remove from pending trades
    window.TRADE_STATE.pendingTrades.delete(ticket_id);
    window.TRADE_STATE.isExecuting = false;
  }
};

// === CENTRALIZED CLOSE TRADE FUNCTION ===
// This is the ONLY function that should close trades
window.closeTrade = async function(tradeId, sellPrice, event) {
  
  // Audio is already played in trade_monitor.html when button was clicked
  
  // Prevent multiple simultaneous executions
  if (window.TRADE_STATE.isExecuting) {
    return { success: false, error: 'Trade already executing' };
  }

  // Validate inputs
  if (!tradeId || !sellPrice) {
    return { success: false, error: 'Invalid close trade parameters' };
  }

  // Generate unique ticket ID
  const ticket_id = 'TICKET-' + Math.random().toString(36).substr(2, 9) + '-' + Date.now();
  
  // Add to pending trades
  window.TRADE_STATE.pendingTrades.add(ticket_id);
  window.TRADE_STATE.isExecuting = true;

  try {
    // Fetch trade details to construct the close ticket
    const tradeRes = await fetch(`/trades/${tradeId}`);
    if (!tradeRes.ok) {
      throw new Error('Failed to fetch trade for closing');
    }
    const trade = await tradeRes.json();



    // === Get the ACTUAL position count from the trade data ===
    let count = trade.position;
    
    // Validate that we have a valid position count
    if (count === null || count === undefined || isNaN(count) || count <= 0) {
      throw new Error(`Invalid position count: ${count}. Trade ID: ${tradeId}`);
    }

    // Invert side
    let invertedSide = null;
    if (trade.side === 'Y' || trade.side === 'YES') invertedSide = 'N';
    else if (trade.side === 'N' || trade.side === 'NO') invertedSide = 'Y';
    else invertedSide = trade.side;

    // Use current BTC price for symbol_close
    const symbolClose = typeof getCurrentBTCTickerPrice === 'function' ? getCurrentBTCTickerPrice() : null;

    // Compose payload to match open ticket, plus intent: 'close'
    const payload = {
      ticket_id:        ticket_id,
      intent:           'close',
      ticker:           trade.ticker,
      side:             invertedSide,
      count:            count,
      action:           'close',
      type:             'market',
      time_in_force:    'IOC',
      buy_price:        sellPrice,
      symbol_close:     symbolClose
    };

    // === DEMO MODE CHECK ===
    if (window.TRADE_CONFIG.DEMO_MODE) {
      // Audio alert already played in trade_monitor.html when button was clicked
      window.TRADE_STATE.executedTrades.add(ticket_id);
      window.TRADE_STATE.lastTradeId = ticket_id;
      return { 
        success: true, 
        ticket_id: ticket_id, 
        demo: true,
        message: 'Demo close trade created successfully'
      };
    }

    // Execute the actual close trade
    const response = await fetch('/trades', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Close trade execution failed: ${response.status}`);
    }

    const result = await response.json();
    
    // Add to executed trades
    window.TRADE_STATE.executedTrades.add(ticket_id);
    window.TRADE_STATE.lastTradeId = ticket_id;

    // Audio and popup already handled in trade_monitor.html when button was clicked

    return { 
      success: true, 
      ticket_id: ticket_id, 
      demo: false,
      result: result
    };

  } catch (error) {
    return { 
      success: false, 
      error: error.message,
      ticket_id: ticket_id
    };
  } finally {
    // Remove from pending trades
    window.TRADE_STATE.pendingTrades.delete(ticket_id);
    window.TRADE_STATE.isExecuting = false;
  }
};

// === TRADE EXECUTION HELPER FUNCTIONS ===

// Function to prepare trade data from button click
window.prepareTradeData = function(target) {
  const btn = target;
  
  if (btn?.disabled) {
    return null;
  }

  // Get the actual ask price from data attribute (not the display text)
  const askPrice = btn?.dataset?.askPrice;
  
  let buy_price = 0;
  if (askPrice) {
    // Convert from cents to dollars (e.g., "96" becomes 0.96)
    buy_price = parseFloat(askPrice) / 100;
  }

  const posInput = document.getElementById('position-size');
  const rawBasePos = posInput ? parseInt(posInput.value, 10) : NaN;
  const validBase = Number.isFinite(rawBasePos) && rawBasePos > 0 ? rawBasePos : null;

  const multiplierBtn = document.querySelector('.multiplier-btn.active');
  const multiplier = multiplierBtn ? parseInt(multiplierBtn.dataset.multiplier, 10) : 1;

  const position = validBase !== null ? validBase * multiplier : null;

  const symbol = typeof getSelectedSymbol === 'function' ? getSelectedSymbol() : 'BTC';
  const contract = typeof getTruncatedMarketTitle === 'function' ? getTruncatedMarketTitle() : 'BTC Market';

  // Get strike and side from button context
  let strike = null;
  let side = null;
  let row = btn.closest('tr');
  
  if (row) {
    const strikeCell = row.querySelector('td');
    if (strikeCell) {
      strike = parseFloat(strikeCell.textContent.replace(/\$|,/g, ''));
    }
    
    const tds = Array.from(row.children);
    for (let i = 0; i < tds.length; ++i) {
      if (tds[i].contains(btn)) {
        if (i === 4) side = 'Y';
        if (i === 5) side = 'N';
      }
    }
  }

  // Fallback to dataset attributes
  if (!strike && btn.dataset.strike) strike = parseFloat(btn.dataset.strike);
  if (!side && btn.dataset.side) side = btn.dataset.side;

  // Get ticker
  let kalshiTicker = btn.dataset.ticker || null;
  if (!kalshiTicker && btn.parentElement && btn.parentElement.dataset.ticker) {
    kalshiTicker = btn.parentElement.dataset.ticker;
  }

  // Get other data
  const symbol_open = typeof getCurrentBTCTickerPrice === 'function' ? getCurrentBTCTickerPrice() : null;
  const momentum = typeof getCurrentMomentumScore === 'function' ? getCurrentMomentumScore() : null;
  

  // Get the PROB value from the strike table for this specific strike
  let prob = null;
  if (strike) {
    const strikeFormatted = '$' + Number(strike).toLocaleString();
    
    const strikeTableRows = document.querySelectorAll('#strike-table tbody tr');
    
    for (const row of strikeTableRows) {
      const firstTd = row.querySelector('td');
      if (!firstTd) continue;
      const firstTdText = firstTd.textContent.trim();
      
      if (firstTdText === strikeFormatted) {
        const tds = row.querySelectorAll('td');
        
        if (tds.length > 3) {
          const probText = tds[3].textContent.trim(); // FIXED: Use the Prob column
          
          if (probText && probText !== '—') {
            prob = probText; // Keep as string (e.g., "97.6")
          }
        }
        break;
      }
    }
  }

  if (!prob) {
    return null;
  }

  // Get trade strategy
  const tradeStrategyPicker = document.getElementById('trade-strategy-picker');
  const tradeStrategy = tradeStrategyPicker ? tradeStrategyPicker.value : "Hourly HTC";

  return {
    symbol: symbol,
    contract: contract,
    strike: `$${Number(strike).toLocaleString()}`,
    side: side,
    ticker: kalshiTicker,
    buy_price: buy_price,
    position: position,
    symbol_open: symbol_open,
    momentum: momentum,
    
    prob: prob,
    trade_strategy: tradeStrategy
  };
};

// === SAFETY CONTROLS ===

// Function to toggle demo mode
window.toggleDemoMode = function() {
  window.TRADE_CONFIG.DEMO_MODE = !window.TRADE_CONFIG.DEMO_MODE;
  return window.TRADE_CONFIG.DEMO_MODE;
};

// Function to get current trade state
window.getTradeState = function() {
  return {
    demoMode: window.TRADE_CONFIG.DEMO_MODE,
    isExecuting: window.TRADE_STATE.isExecuting,
    pendingTrades: Array.from(window.TRADE_STATE.pendingTrades),
    executedTrades: Array.from(window.TRADE_STATE.executedTrades),
    lastTradeId: window.TRADE_STATE.lastTradeId
  };
};

// Initialize the controller 
document.addEventListener('DOMContentLoaded', function() {
  // Controller initialized silently
}); 
