// === CENTRALIZED TRADE EXECUTION CONTROLLER ===
// This file centralizes ALL trade execution to prevent multiple functions
// and add proper safety controls for live money trading

// Global configuration
window.TRADE_CONFIG = {
  DEMO_MODE: false,  // Set to false for live trading
  REQUIRE_CONFIRMATION: true,
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
    console.warn('Trade execution blocked: Another trade is currently executing');
    return { success: false, error: 'Trade already executing' };
  }

  // Validate trade data
  if (!tradeData || !tradeData.symbol || !tradeData.side || !tradeData.buy_price) {
    console.error('Invalid trade data:', tradeData);
    return { success: false, error: 'Invalid trade data' };
  }

  // Check position size limits
  if (tradeData.position && tradeData.position > window.TRADE_CONFIG.MAX_POSITION_SIZE) {
    console.error('Position size exceeds limit:', tradeData.position);
    return { success: false, error: 'Position size too large' };
  }

  // Generate unique ticket ID
  const ticket_id = 'TICKET-' + Math.random().toString(36).substr(2, 9) + '-' + Date.now();
  
  // Add to pending trades
  window.TRADE_STATE.pendingTrades.add(ticket_id);
  window.TRADE_STATE.isExecuting = true;

  try {
    // Create the trade payload
    const payload = {
      ticket_id: ticket_id,
      status: "pending",
      date: new Date().toISOString().split("T")[0],
      time: new Date().toLocaleTimeString('en-US', { hour12: false }),
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
      momentum: tradeData.momentum,
      prob: tradeData.prob,
      volatility: tradeData.volatility,
      volatility_delta: null,
      win_loss: null
    };

    if (tradeData.position !== null) {
      payload.position = tradeData.position;
    }

    console.log('Trade execution payload:', payload);

    // === DEMO MODE CHECK ===
    if (window.TRADE_CONFIG.DEMO_MODE) {
      // No popup, just log
      if (window.TRADE_CONFIG.ENABLE_SOUNDS && typeof playSound === 'function') {
        playSound('open');
      }
      window.TRADE_STATE.executedTrades.add(ticket_id);
      window.TRADE_STATE.lastTradeId = ticket_id;
      return { 
        success: true, 
        ticket_id: ticket_id, 
        demo: true,
        message: 'Demo trade created successfully'
      };
    }

    // === LIVE TRADING MODE ===
    if (window.TRADE_CONFIG.REQUIRE_CONFIRMATION) {
      const confirmMessage = `CONFIRM LIVE TRADE\n\n\n` +
        `Symbol: ${tradeData.symbol}\n` +
        `Contract: ${tradeData.contract}\n` +
        `Strike: ${tradeData.strike}\n` +
        `Side: ${tradeData.side}\n` +
        `Price: $${tradeData.buy_price}\n` +
        `Position: ${tradeData.position || 'Not set'}\n` +
        `Prob: ${tradeData.prob || 'Not available'}\n\n\n` +
        `⚠️  This will execute a REAL TRADE with REAL MONEY\n\n` +
        `Are you sure you want to proceed?`;

      const confirmed = confirm(confirmMessage);
      if (!confirmed) {
        console.log('Trade cancelled by user');
        return { success: false, error: 'Trade cancelled by user' };
      }
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

    // Play sound if enabled
    if (window.TRADE_CONFIG.ENABLE_SOUNDS && typeof playSound === 'function') {
      playSound('open');
    }

    console.log('Trade executed successfully:', result);
    return { 
      success: true, 
      ticket_id: ticket_id, 
      demo: false,
      result: result
    };

  } catch (error) {
    console.error('Trade execution failed:', error);
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
  if (btn?.disabled) return null;

  const btnText = btn?.textContent?.trim() || '';
  const buy_price = parseFloat((parseFloat(btnText) / 100).toFixed(2));

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
  const volatility = window.coreData?.volatility_score != null
    ? parseFloat(window.coreData.volatility_score.toFixed(2))
    : null;

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
  console.log('PROB extraction for strike', strike, ':', prob);
  if (!prob) {
    alert('ERROR: Could not find PROB value for this strike. No ticket created.');
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
    volatility: volatility,
    prob: prob,
    trade_strategy: tradeStrategy
  };
};

// === SAFETY CONTROLS ===

// Function to toggle demo mode
window.toggleDemoMode = function() {
  window.TRADE_CONFIG.DEMO_MODE = !window.TRADE_CONFIG.DEMO_MODE;
  console.log('Demo mode:', window.TRADE_CONFIG.DEMO_MODE ? 'ON' : 'OFF');
  
  // Show status
  const status = window.TRADE_CONFIG.DEMO_MODE ? 
    '🟢 DEMO MODE - No real trades will be executed' : 
    '🔴 LIVE MODE - Real trades will be executed';
  
  alert(status);
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
console.log('Trade Execution Controller initialized');
console.log('Demo mode:', window.TRADE_CONFIG.DEMO_MODE ? 'ON' : 'OFF'); 