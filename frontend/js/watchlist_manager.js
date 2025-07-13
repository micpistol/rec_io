// === WATCHLIST MANAGER (LIVE MIRROR) ===
// Displays the actual strike table rows in the watchlist panel for live updates and interactivity

let watchlistStrikes = [];

async function loadWatchlistStrikes() {
  try {
    const response = await fetch('/api/get_watchlist');
    const data = await response.json();
    watchlistStrikes = data.watchlist || [];
    updateWatchlistMirror();
  } catch (error) {
    console.error('[WATCHLIST MANAGER] Error loading watchlist:', error);
  }
}

async function removeStrikeFromWatchlist(strike) {
  // Remove from local array
  watchlistStrikes = watchlistStrikes.filter(s => s !== strike);
  // Save to backend
  await fetch('/api/set_watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ watchlist: watchlistStrikes })
  });
  // Refresh display
  updateWatchlistMirror();
}

function updateWatchlistMirror() {
  const watchlistBody = document.getElementById('watchlist-body');
  if (!watchlistBody) return;
  watchlistBody.innerHTML = '';

  // Find the main strike table
  const strikeTable = document.getElementById('strike-table');
  if (!strikeTable) return;
  const strikeRows = Array.from(strikeTable.querySelectorAll('tbody tr'));

  // Sort strikes in ascending order
  const sortedStrikes = [...watchlistStrikes].sort((a, b) => a - b);

  // Get current price for spanner row positioning
  const currentPriceEl = document.getElementById('btc-price-value');
  const currentPrice = currentPriceEl ? parseFloat(currentPriceEl.textContent.replace(/\$|,/g, '')) : 0;

  // Find the correct index to insert the spanner row
  let spannerIndex = sortedStrikes.length; // default to end
  for (let i = 0; i < sortedStrikes.length; i++) {
    if (currentPrice < sortedStrikes[i]) {
      spannerIndex = i;
      break;
    }
  }

  // Render rows and insert spanner row at the correct position
  sortedStrikes.forEach((strike, idx) => {
    if (idx === spannerIndex) {
      // Insert spanner row before this strike
      const spannerRow = createSpannerRow(currentPrice);
      watchlistBody.appendChild(spannerRow);
    }
    // Find the row by matching the first cell (strike value)
    const row = strikeRows.find(tr => {
      const cell = tr.children[0];
      if (!cell) return false;
      const val = parseFloat(cell.textContent.replace(/[$,]/g, ''));
      return val === strike;
    });
    if (row) {
      const mirrorRow = document.createElement('tr');
      mirrorRow.className = row.className + ' watchlist-row';
      for (let i = 0; i < row.children.length; i++) {
        mirrorRow.appendChild(row.children[i].cloneNode(true));
      }
      mirrorRow.style.cursor = 'pointer';
      mirrorRow.title = 'Click to remove from watchlist';
      mirrorRow.addEventListener('click', () => removeStrikeFromWatchlist(strike));
      watchlistBody.appendChild(mirrorRow);
    }
  });
  // If spanner should be at the end (current price above all strikes or no strikes)
  if (spannerIndex === sortedStrikes.length) {
    const spannerRow = createSpannerRow(currentPrice);
    watchlistBody.appendChild(spannerRow);
  }
}

// Helper function to create spanner row
function createSpannerRow(currentPrice) {
  const spannerRow = document.createElement("tr");
  spannerRow.className = "spanner-row";
  const spannerTd = document.createElement("td");
  spannerTd.colSpan = 6; // Match the number of columns in the watchlist table

  // --- Add arrow icons based on momentum score ---
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
  // SVGs for straight arrows (no margin)
  const svgDown = `<svg width="16" height="16" style="vertical-align:middle;" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8 2v12M8 14l4-4M8 14l-4-4" stroke="#45d34a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const svgUp = `<svg width="16" height="16" style="vertical-align:middle;" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8 14V2M8 2l4 4M8 2l-4 4" stroke="#dc3545" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
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

// Re-render the watchlist whenever the strike table updates
window.syncWatchlistWithStrikeTable = updateWatchlistMirror;

// Re-load the watchlist from backend when needed
window.refreshWatchlist = loadWatchlistStrikes;

// Initial load
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(loadWatchlistStrikes, 1000);
}); 