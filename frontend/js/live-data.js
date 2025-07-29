
// === LIVE DATA POLLING MODULE ===
// This module handles left column data fetching for the trade monitor
// Left column: BTC price, price changes, momentum score (all from endpoints)

// Global data holders
window.momentumData = {
  weightedScore: null,
  deltas: {}, // New: to store individual minute deltas
};

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

// Fetch core data (momentum score only - BTC price now handled by strike table)
function fetchCore() {
  fetch('/core')
    .then(response => response.json())
    .then(data => {
      // Update weighted momentum score
      window.momentumData.weightedScore = data.weighted_momentum_score;

      // Update individual momentum deltas
      if (data.delta_1m !== undefined) window.momentumData.deltas['1m'] = data.delta_1m;
      if (data.delta_2m !== undefined) window.momentumData.deltas['2m'] = data.delta_2m;
      if (data.delta_3m !== undefined) window.momentumData.deltas['3m'] = data.delta_3m;
      if (data.delta_4m !== undefined) window.momentumData.deltas['4m'] = data.delta_4m;
      if (data.delta_15m !== undefined) window.momentumData.deltas['15m'] = data.delta_15m;
      if (data.delta_30m !== undefined) window.momentumData.deltas['30m'] = data.delta_30m;

      // Trigger momentum panel update if function exists
      if (typeof updateMomentumPanel === 'function') {
        updateMomentumPanel();
      }
    })
    .catch(console.error);
}

// Fetch BTC price changes from backend API and update ticker panel
async function fetchBTCPriceChanges() {
  try {
    const res = await fetch('/btc_price_changes');
    if (!res.ok) throw new Error('Failed to fetch BTC price changes');
    const data = await res.json();
    
    // Update 1h, 3h, 1d change numbers in the price panel
    if ('change1h' in data) {
      const el = document.getElementById('change-1h');
      if (el) decorateChange(el, data.change1h);
    }
    if ('change3h' in data) {
      const el = document.getElementById('change-3h');
      if (el) decorateChange(el, data.change3h);
    }
    if ('change1d' in data) {
      const el = document.getElementById('change-1d');
      if (el) decorateChange(el, data.change1d);
    }
  } catch (error) {
    console.error('Error fetching BTC price changes:', error);
  }
}

// === AUTO ENTRY INDICATOR FUNCTIONS ===

// Update the auto entry indicator display
function updateAutoEntryIndicator(data) {
  const indicator = document.getElementById('autoEntryIndicator');
  if (!indicator) {
    console.error('Auto entry indicator element not found');
    return;
  }
  
  if (data.enabled && data.ttc_within_window) {
    // Show the indicator when AUTO ENTRY is ON and TTC is within window
    indicator.style.display = 'flex';
  } else {
    // Hide the indicator when conditions are not met
    indicator.style.display = 'none';
  }
}

// === POLLING SETUP ===

// Initialize polling when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Initial data fetches
  fetchCore();
  fetchBTCPriceChanges();

  // Set up polling intervals
  setInterval(fetchBTCPriceChanges, 60000);    // Price changes every minute (unchanged frequency)
});

// Export functions for use by other modules
window.liveData = {
  fetchCore,
  fetchBTCPriceChanges
}; 
