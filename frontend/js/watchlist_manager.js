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

  // For each strike in the watchlist, find the corresponding row in the main table
  sortedStrikes.forEach(strike => {
    // Find the row by matching the first cell (strike value)
    const row = strikeRows.find(tr => {
      const cell = tr.children[0];
      if (!cell) return false;
      // Remove $ and commas, parse as number
      const val = parseFloat(cell.textContent.replace(/[$,]/g, ''));
      return val === strike;
    });
    if (row) {
      // Create a new row and move all cells (not clone) for live updates
      const mirrorRow = document.createElement('tr');
      mirrorRow.className = row.className + ' watchlist-row';
      for (let i = 0; i < row.children.length; i++) {
        mirrorRow.appendChild(row.children[i].cloneNode(true));
      }
      // Add click-to-remove functionality
      mirrorRow.style.cursor = 'pointer';
      mirrorRow.title = 'Click to remove from watchlist';
      mirrorRow.addEventListener('click', () => removeStrikeFromWatchlist(strike));
      watchlistBody.appendChild(mirrorRow);
    }
  });
}

// Re-render the watchlist whenever the strike table updates
window.syncWatchlistWithStrikeTable = updateWatchlistMirror;

// Re-load the watchlist from backend when needed
window.refreshWatchlist = loadWatchlistStrikes;

// Initial load
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(loadWatchlistStrikes, 1000);
}); 