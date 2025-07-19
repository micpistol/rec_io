// === LIVE DATA POLLING MODULE ===
// This module handles all live data fetching and polling for the trade monitor

// Global data holders
window.momentumData = {
  deltas: {
    '1m': null,
    '2m': null,
    '3m': null,
    '4m': null,
    '15m': null,
    '30m': null,
  },
  weightedScore: null,
};

window.CurrentMarketTitleRaw = "";
let cachedTTC = null;
let lastFetchTimestamp = 0;

// === UTILITY FUNCTIONS ===

// Helper function to format numbers as $XX,XXX.XX
function formatUSD(val) {
  if (typeof val !== "number" || isNaN(val)) return "—";
  return "$" + val.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

// Helper: decorate change cell with color and triangle
function decorateChange(el, val) {
  const num = parseFloat(val);
  if (isNaN(num)) {
    el.textContent = "—";
    el.style.backgroundColor = "";
    el.style.color = "";
    return;
  }
  const triangle = num >= 0 ? " ▲" : " ▼";
  el.textContent = `${Math.abs(num).toFixed(2)}%${triangle}`;
  el.style.color = "#fff";
  el.style.backgroundColor = num >= 0 ? "#28a745" : "#dc3545";
  el.style.padding = "2px 6px";
  el.style.borderRadius = "4px";
  el.style.display = "inline-block";
}

// === CORE DATA FETCHING FUNCTIONS ===

// Fetch core data for momentum calculations
function fetchCore() {
  fetch('/core')
    .then(response => response.json())
    .then(data => {
      window.momentumData.deltas['1m'] = data.delta_1m;
      window.momentumData.deltas['2m'] = data.delta_2m;
      window.momentumData.deltas['3m'] = data.delta_3m;
      window.momentumData.deltas['4m'] = data.delta_4m;
      window.momentumData.deltas['15m'] = data.delta_15m;
      window.momentumData.deltas['30m'] = data.delta_30m;

      // Use the weighted momentum score from the backend (single source of truth)
      window.momentumData.weightedScore = data.weighted_momentum_score;

      // Trigger momentum panel update if function exists
      if (typeof updateMomentumPanel === 'function') {
        updateMomentumPanel();
      }
    })
    .catch(console.error);
}

// Fetch BTC price data
function fetchOtherCoreData() {
  fetch('/core')
    .then(response => response.json())
    .then(data => {
      // BTC price
      if ('btc_price' in data) {
        const price = Number(data.btc_price);
        const el = document.getElementById('btc-price-value');
        if (el) el.textContent = formatUSD(price);
      }
    })
    .catch(error => {
      console.error('Live core fetch error:', error);
    });
  

}

// Fetch BTC price changes from backend API and update ticker panel
async function fetchBTCPriceChanges() {
  try {
    console.log('[LIVE-DATA] Fetching BTC price changes...');
    const res = await fetch('/btc_price_changes');
    if (!res.ok) throw new Error('Failed to fetch BTC price changes');
    const data = await res.json();
    console.log('[LIVE-DATA] BTC changes data:', data);
    
    if ('change1h' in data) {
      const el = document.getElementById('change-1h');
      console.log('[LIVE-DATA] change-1h element:', el);
      if (el) {
        decorateChange(el, data.change1h);
        console.log('[LIVE-DATA] Updated change-1h to:', el.textContent);
      }
    }
    if ('change3h' in data) {
      const el = document.getElementById('change-3h');
      console.log('[LIVE-DATA] change-3h element:', el);
      if (el) {
        decorateChange(el, data.change3h);
        console.log('[LIVE-DATA] Updated change-3h to:', el.textContent);
      }
    }
    if ('change1d' in data) {
      const el = document.getElementById('change-1d');
      console.log('[LIVE-DATA] change-1d element:', el);
      if (el) {
        decorateChange(el, data.change1d);
        console.log('[LIVE-DATA] Updated change-1d to:', el.textContent);
      }
    }
  } catch (error) {
    console.error('Error fetching BTC price changes:', error);
  }
}

// === STRIKE TABLE DATA FETCHING ===

// Main periodic fetcher for strike table
async function fetchAndUpdate() {
  try {
    const [coreRes, marketsRes] = await Promise.all([fetch('/core'), fetch('/kalshi_market_snapshot')]);
    if (!coreRes.ok || !marketsRes.ok) return;
    const coreData = await coreRes.json();
    const marketsData = await marketsRes.json();
    const latestKalshiMarkets = Array.isArray(marketsData.markets) ? marketsData.markets : [];

    // Initialize strike table if needed
    if (typeof initializeStrikeTable === 'function' && (!window.strikeRowsMap || !window.strikeRowsMap.size)) {
      const base = Math.round(coreData.btc_price / 250) * 250;
      initializeStrikeTable(base);
    }

    // Update strike table if function exists
    if (typeof updateStrikeTable === 'function') {
      updateStrikeTable(coreData, latestKalshiMarkets);
    }
    
    // Update active trades after strike table update (since active trades depend on strike table data)
    if (typeof window.fetchAndRenderTrades === 'function') {
      window.fetchAndRenderTrades();
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

    // Check if ATM strike has drifted more than 2 rows from center
    if (window.strikeRowsMap && window.strikeRowsMap.size > 0) {
      const currentCenterStrike = Math.round(coreData.btc_price / 250) * 250;
      const strikeList = Array.from(window.strikeRowsMap.keys()).sort((a, b) => a - b);
      const centerIndex = Math.floor(strikeList.length / 2);
      const currentCenter = strikeList[centerIndex];

      const drift = currentCenterStrike - currentCenter;

      // If ATM strike is more than 2 rows from center, shift table
      if (drift >= 500 || drift <= -500) {
        const newBase = currentCenter + (drift > 0 ? 250 : -250);
        if (typeof initializeStrikeTable === 'function') {
          initializeStrikeTable(newBase);
        }
      }
    }
  } catch (e) {
    console.error("Error fetching or updating strike table:", e);
  }
}

// === MARKET TITLE FETCHING ===

// Fetch the raw market title from backend
async function fetchMarketTitleRaw() {
  try {
    const res = await fetch('/market_title');
    const data = await res.json();
    window.CurrentMarketTitleRaw = data.title || "";
  } catch (e) {
    window.CurrentMarketTitleRaw = "";
    console.error("Error fetching market title:", e);
  }
}

// Update the strike panel market title display with formatting
function updateStrikePanelMarketTitle() {
  const cell = document.getElementById('strikePanelMarketTitleCell');
  if (!cell || !window.CurrentMarketTitleRaw) return;

  const timeMatch = window.CurrentMarketTitleRaw.match(/at\s(.*)\?/i);
  const timeStr = timeMatch ? timeMatch[1] : "";
  cell.textContent = `Bitcoin price today at ${timeStr}?`;
  cell.style.color = "white";
}

// === TTC CLOCK FUNCTIONS ===

function formatTTC(seconds) {
  if (seconds === null || seconds === undefined || isNaN(seconds)) {
    return '--:--';
  }
  const m = String(Math.floor(seconds / 60)).padStart(2, '0');
  const s = String(seconds % 60).padStart(2, '0');
  return `${m}:${s}`;
}

function updateClockDisplay() {
  const ttcEl = document.getElementById('strikePanelTTC');
  if (!ttcEl || cachedTTC === null) return;

  ttcEl.textContent = formatTTC(cachedTTC);

  ttcEl.style.backgroundColor = '';
  ttcEl.style.color = '';
  ttcEl.style.borderRadius = '';
  ttcEl.style.padding = '';

  if (cachedTTC >= 0 && cachedTTC <= 180) {
    ttcEl.style.backgroundColor = '#d2372b';
    ttcEl.style.color = '#fff';
    ttcEl.style.borderRadius = '6px';
    ttcEl.style.padding = '0 10px';
  } else if (cachedTTC <= 300) {
    ttcEl.style.backgroundColor = '#ffc107';
    ttcEl.style.color = '#fff';
    ttcEl.style.borderRadius = '6px';
    ttcEl.style.padding = '0 10px';
  } else if (cachedTTC <= 720) {
    ttcEl.style.backgroundColor = '#45d34a';
    ttcEl.style.color = '#fff';
    ttcEl.style.borderRadius = '6px';
    ttcEl.style.padding = '0 10px';
  } else if (cachedTTC <= 900) {
    ttcEl.style.backgroundColor = '#ffc107';
    ttcEl.style.color = '#fff';
    ttcEl.style.borderRadius = '6px';
    ttcEl.style.padding = '0 10px';
  }
}

async function fetchAndCacheTTC() {
  try {
    const res = await fetch('/core');
    const data = await res.json();
    cachedTTC = data.ttc_seconds;
    lastFetchTimestamp = Date.now();
  } catch {
    cachedTTC = null;
  }
}

// === POLLING SETUP ===

// Initialize polling when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Initial data fetches
  fetchCore();
  fetchOtherCoreData();
  fetchBTCPriceChanges();
  fetchAndUpdate();
  fetchMarketTitleRaw();
  updateStrikePanelMarketTitle();
  fetchAndCacheTTC();

  // Set up polling intervals - all at 1 second for consistency
  setInterval(fetchAndUpdate, 1000);           // Strike panel - back to original
setInterval(fetchOtherCoreData, 1000);       // BTC price data
setInterval(fetchCore, 1000);                // Momentum data - back to original
setInterval(fetchBTCPriceChanges, 1000);     // BTC price changes
setInterval(fetchMarketTitleRaw, 5000);      // Market title
setInterval(updateStrikePanelMarketTitle, 5000); // Market title display
  setInterval(() => {
    if (cachedTTC !== null) {
      cachedTTC = Math.max(0, cachedTTC - 1);
    }
    updateClockDisplay();

    if (Date.now() - lastFetchTimestamp > 10000) {
      fetchAndCacheTTC();
    }
  }, 1000); // TTC clock
  
  // Dedicated polling for active trades to ensure they update properly
  setInterval(() => {
    if (typeof window.fetchAndRenderTrades === 'function') {
      console.log('[LIVE-DATA] Dedicated active trades polling');
      window.fetchAndRenderTrades();
    }
  }, 2000); // Active trades every 2 seconds
});

// Export functions for use by other modules
window.liveData = {
  fetchCore,
  fetchOtherCoreData,
  fetchBTCPriceChanges,
  fetchAndUpdate,
  fetchMarketTitleRaw,
  updateStrikePanelMarketTitle,
  fetchAndCacheTTC,
  updateClockDisplay
}; 