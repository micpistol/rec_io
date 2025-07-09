// === WATCHLIST MODULE ===
// This module handles all watchlist functionality including data management, display updates, and RECO filtering

// === WATCHLIST DATA MANAGEMENT ===
let watchlistData = [];
let ignoreWsUpdates = false; // Global scope for WebSocket sync
let watchlistRowsMap = new Map(); // Persistent watchlist rows

// Load watchlist from preferences on page load
async function loadWatchlistFromPreferences() {
  try {
    const response = await fetch('/api/get_watchlist');
    const data = await response.json();
    watchlistData = data.watchlist || [];
    console.log('Loaded watchlist from preferences:', watchlistData);
    updateWatchlistDisplay();
  } catch (error) {
    console.error('Error loading watchlist from preferences:', error);
  }
}

// Save watchlist to preferences
async function saveWatchlistToPreferences() {
  console.log('saveWatchlistToPreferences called with watchlistData:', watchlistData);
  console.log('ignoreWsUpdates:', ignoreWsUpdates);
  if (ignoreWsUpdates) {
    console.log('Skipping save due to ignoreWsUpdates flag');
    return;
  }
  try {
    console.log('Saving watchlist to preferences:', watchlistData);
    const response = await fetch('/api/set_watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ watchlist: watchlistData })
    });
    console.log('Save response status:', response.status);
    if (!response.ok) {
      console.error('Save failed with status:', response.status);
    } else {
      console.log('Watchlist saved successfully');
    }
  } catch (error) {
    console.error('Error saving watchlist to preferences:', error);
  }
}

// === WATCHLIST MANIPULATION FUNCTIONS ===

function addToWatchlist(strikeRow) {
  console.log('addToWatchlist called with strikeRow:', strikeRow);
  const strike = parseFloat(strikeRow.children[0].textContent.replace(/[\$,]/g, ''));
  console.log('Parsed strike value:', strike);
  if (watchlistData.includes(strike)) {
    console.log('Strike already in watchlist, skipping');
    return; // Already in watchlist
  }
  console.log('Adding strike to watchlistData');
  watchlistData.push(strike);
  console.log('Updated watchlistData:', watchlistData);

  updateWatchlistDisplay();
  saveWatchlistToPreferences();
}

function removeFromWatchlist(strike) {
  watchlistData = watchlistData.filter(item => item !== strike);
  updateWatchlistDisplay();
  saveWatchlistToPreferences();
}

// === WATCHLIST DISPLAY MANAGEMENT ===

// Function to update the watchlist display with persistent rows
function updateWatchlistDisplay() {
  const watchlistBody = document.getElementById('watchlist-body');
  if (!watchlistBody) return;
  const strikeTable = document.getElementById('strike-table');
  if (!strikeTable) return;
  const strikeRows = Array.from(strikeTable.querySelectorAll('tbody tr'));

  // Build a map of strike value to strike table row
  const strikeRowMap = new Map();
  strikeRows.forEach(row => {
    const cell = row.querySelector('td');
    if (!cell) return;
    const cellStrike = parseFloat(cell.textContent.replace(/[\$,]/g, ''));
    strikeRowMap.set(cellStrike, row);
  });

  // Sort watchlist data by strike value (ascending)
  watchlistData.sort((a, b) => a - b);
  
  // If watchlist is empty, clear and return
  if (watchlistData.length === 0) {
    watchlistBody.innerHTML = '';
    watchlistRowsMap.clear();
    return;
  }
  
  // Get current price for spanner row positioning
  const currentPriceEl = document.getElementById('btc-price-value');
  const currentPrice = currentPriceEl ? parseFloat(currentPriceEl.textContent.replace(/\$|,/g, '')) : 0;
  console.log('Watchlist debug - currentPriceEl:', currentPriceEl, 'currentPrice:', currentPrice, 'watchlistData:', watchlistData);
  
  // Find the correct index to insert the spanner row
  let spannerIndex = watchlistData.length; // default to end
  for (let i = 0; i < watchlistData.length; i++) {
    const strike = watchlistData[i];
    if (currentPrice < strike) {
      spannerIndex = i;
      break;
    }
  }
  console.log('Watchlist debug - spannerIndex:', spannerIndex);
  
  // Remove any existing spanner rows first
  watchlistBody.querySelectorAll('.spanner-row').forEach(row => row.remove());
  
  // Only rebuild if the watchlist structure has changed
  const currentStrikes = new Set(watchlistData);
  const existingStrikes = new Set();
  watchlistBody.querySelectorAll('tr:not(.spanner-row)').forEach(row => {
    const strikeCell = row.querySelector('td');
    if (strikeCell) {
      const strike = parseFloat(strikeCell.textContent.replace(/[\$,]/g, ''));
      existingStrikes.add(strike);
    }
  });
  
  // Check if we need to rebuild the structure
  const needsRebuild = watchlistData.length !== existingStrikes.size || 
                       !watchlistData.every(strike => existingStrikes.has(strike));
  
  if (needsRebuild) {
    // Clear and rebuild only when structure changes
    watchlistBody.innerHTML = '';
    
    watchlistData.forEach((strike, index) => {
      const marketRow = strikeRowMap.get(strike);
      if (!marketRow) return;
      
      // Create new persistent row
      const row = document.createElement('tr');
      row.className = marketRow.className + ' watchlist-row';
      row.dataset.strike = strike;
      Array.from(marketRow.children).forEach((cell, cellIndex) => {
        const newCell = cell.cloneNode(true);
        if (cellIndex === 0) {
          newCell.style.cursor = 'pointer';
          newCell.title = 'Click to remove from watchlist';
          newCell.onclick = () => removeFromWatchlist(strike);
        } else {
          newCell.style.cursor = '';
          newCell.title = '';
        }
        row.appendChild(newCell);
      });
      
      // Remove ATM border highlight from all cells in the watchlist row
      Array.from(row.children).forEach(cell => {
        cell.style.borderTop = '';
        cell.style.borderBottom = '';
      });
      
      // Store references to cells for in-place updates
      const yesCell = row.children[5];
      const noCell = row.children[6];
      let yesSpan = yesCell.querySelector('span');
      let noSpan = noCell.querySelector('span');
      
      if (!yesSpan) {
        yesSpan = document.createElement('span');
        yesCell.appendChild(yesSpan);
      }
      if (!noSpan) {
        noSpan = document.createElement('span');
        noCell.appendChild(noSpan);
      }
      
      const rowObj = {
        tr: row,
        yesSpan: yesSpan,
        noSpan: noSpan,
        strike: strike
      };
      watchlistRowsMap.set(strike, rowObj);
      
      // Add to DOM
      watchlistBody.appendChild(row);
      
      // Insert spanner row after this row if this is the correct position
      if (index === spannerIndex - 1) {
        const spannerRow = createSpannerRow(currentPrice);
        watchlistBody.appendChild(spannerRow);
      }
    });
    
    // If spanner should be at the beginning, add it first
    if (spannerIndex === 0) {
      const spannerRow = createSpannerRow(currentPrice);
      watchlistBody.insertBefore(spannerRow, watchlistBody.firstChild);
    }
  } else {
    // Just update existing rows in place
    watchlistData.forEach(strike => {
      const marketRow = strikeRowMap.get(strike);
      if (!marketRow) return;
      
      const rowObj = watchlistRowsMap.get(strike);
      if (!rowObj) return;
      
      // Update buffer, B/M, adj, and risk cells with live data from market row
      const bufferCell = rowObj.tr.children[1];
      const bmCell = rowObj.tr.children[2];
      const adjCell = rowObj.tr.children[3];
      const riskCell = rowObj.tr.children[4];
      
      if (bufferCell && marketRow.children[1]) {
        const oldBuffer = bufferCell.textContent;
        const newBuffer = marketRow.children[1].textContent;
        if (oldBuffer !== newBuffer) {
          console.log(`Watchlist: Updating buffer for strike ${strike} from ${oldBuffer} to ${newBuffer}`);
          bufferCell.textContent = newBuffer;
        }
      }
      if (bmCell && marketRow.children[2]) {
        const oldBm = bmCell.textContent;
        const newBm = marketRow.children[2].textContent;
        if (oldBm !== newBm) {
          console.log(`Watchlist: Updating B/M for strike ${strike} from ${oldBm} to ${newBm}`);
          bmCell.textContent = newBm;
        }
      }
      if (adjCell && marketRow.children[3]) {
        const oldAdj = adjCell.textContent;
        const newAdj = marketRow.children[3].textContent;
        if (oldAdj !== newAdj) {
          console.log(`Watchlist: Updating Adj for strike ${strike} from ${oldAdj} to ${newAdj}`);
          adjCell.textContent = newAdj;
        }
      }
      if (riskCell && marketRow.children[4]) {
        const oldRisk = riskCell.textContent;
        const newRisk = marketRow.children[4].textContent;
        if (oldRisk !== newRisk) {
          console.log(`Watchlist: Updating Risk for strike ${strike} from ${oldRisk} to ${newRisk}`);
          riskCell.textContent = newRisk;
        }
      }
      
      // Update YES/NO buttons in place (only if prices changed)
      [5, 6].forEach(idx => {
        const marketCell = marketRow.children[idx];
        if (!marketCell) return;
        
        const marketSpan = marketCell.querySelector('span');
        let askPrice = marketSpan ? marketSpan.textContent : '';
        let isActive = marketSpan ? !marketSpan.classList.contains('disabled') : false;
        let ticker = marketSpan ? marketSpan.getAttribute('data-ticker') : null;
        const side = idx === 5 ? 'yes' : 'no';
        
        if (idx === 5) {
          updateYesNoButton(rowObj.yesSpan, strike, side, askPrice, isActive, ticker);
        } else {
          updateYesNoButton(rowObj.noSpan, strike, side, askPrice, isActive, ticker);
        }
      });
    });
    
    // Update or create spanner row
    let existingSpanner = watchlistBody.querySelector('.spanner-row');
    console.log('Watchlist spanner debug - currentPrice:', currentPrice, 'existingSpanner:', !!existingSpanner);
    
    if (existingSpanner) {
      const newSpanner = createSpannerRow(currentPrice);
      existingSpanner.replaceWith(newSpanner);
      console.log('Replaced existing spanner row');
    } else {
      // Create spanner row if it doesn't exist
      const spannerRow = createSpannerRow(currentPrice);
      
      // Find the correct position to insert the spanner row
      const rows = Array.from(watchlistBody.children);
      let insertIndex = rows.length; // default to end
      
      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        if (row.classList.contains('spanner-row')) continue;
        
        const strikeCell = row.querySelector('td');
        if (strikeCell) {
          const strike = parseFloat(strikeCell.textContent.replace(/[\$,]/g, ''));
          if (currentPrice < strike) {
            insertIndex = i;
            break;
          }
        }
      }
      
      console.log('Watchlist spanner debug - insertIndex:', insertIndex, 'rows.length:', rows.length);
      
      if (insertIndex < rows.length) {
        watchlistBody.insertBefore(spannerRow, rows[insertIndex]);
        console.log('Inserted spanner row at index:', insertIndex);
      } else {
        watchlistBody.appendChild(spannerRow);
        console.log('Appended spanner row to end');
      }
    }
  }
  
  // Clean up removed strikes from the persistent map
  for (const [strike, rowObj] of watchlistRowsMap.entries()) {
    if (!currentStrikes.has(strike)) {
      watchlistRowsMap.delete(strike);
    }
  }
}

// === RECO FILTERING ===

// Function to apply RECO filtering criteria
function applyRecoFilter(strikeRows) {
  if (!window.recoEnabled) return []; // Return empty if RECO is off
  
  const filteredStrikes = [];
  
  strikeRows.forEach(row => {
    const cells = Array.from(row.children);
    if (cells.length < 7) return; // Need at least 7 columns
    
    // Get Adj B/M value (column 3, index 3)
    const adjBmCell = cells[3];
    const adjBmText = adjBmCell ? adjBmCell.textContent.trim() : '';
    const adjBm = parseFloat(adjBmText.replace(/[^\d.-]/g, '')) || 0;
    
    // Get YES and NO prices (columns 5 and 6, indices 5 and 6)
    const yesCell = cells[5];
    const noCell = cells[6];
    
    let yesPrice = 0;
    let noPrice = 0;
    let yesActive = false;
    let noActive = false;
    
    if (yesCell) {
      const yesSpan = yesCell.querySelector('span');
      if (yesSpan && !yesSpan.classList.contains('disabled')) {
        yesPrice = parseFloat(yesSpan.textContent) || 0;
        yesActive = true;
      }
    }
    
    if (noCell) {
      const noSpan = noCell.querySelector('span');
      if (noSpan && !noSpan.classList.contains('disabled')) {
        noPrice = parseFloat(noSpan.textContent) || 0;
        noActive = true;
      }
    }
    
    // Get the higher of the two active prices
    const activePrice = Math.max(yesActive ? yesPrice : 0, noActive ? noPrice : 0);
    
    // Apply RECO criteria: Adj B/M > 25 AND active price ≤ 97
    if (adjBm > 25 && activePrice <= 97 && activePrice > 0) {
      // Get strike value from first column
      const strikeCell = cells[0];
      const strikeText = strikeCell ? strikeCell.textContent.trim() : '';
      const strike = parseFloat(strikeText.replace(/[\$,]/g, '')) || 0;
      
      if (strike > 0) {
        filteredStrikes.push(strike);
      }
    }
  });
  
  console.log('RECO filter applied. Found', filteredStrikes.length, 'strikes meeting criteria');
  return filteredStrikes;
}

// Function to update watchlist based on RECO state
function updateWatchlistBasedOnReco() {
  console.log('updateWatchlistBasedOnReco called, RECO enabled:', window.recoEnabled);
  
  if (window.recoEnabled) {
    // RECO is ON - apply automatic filtering
    console.log('Applying RECO filtering...');
    const strikeTable = document.getElementById('strike-table');
    if (!strikeTable) return;
    
    const strikeRows = Array.from(strikeTable.querySelectorAll('tbody tr'));
    const filteredStrikes = applyRecoFilter(strikeRows);
    
    // Update watchlist with filtered strikes
    watchlistData = filteredStrikes;
    updateWatchlistDisplay();
    saveWatchlistToPreferences();
  } else {
    // RECO is OFF - do absolutely nothing, don't touch the watchlist
    console.log('RECO is OFF - leaving manual watchlist alone');
  }
}

// === CLICK HANDLER MANAGEMENT ===

// Function to enable/disable click handlers based on RECO state
function updateClickHandlersForReco() {
  // Simply call addStrikeTableClickHandlers which now handles RECO state
  if (typeof window.addStrikeTableClickHandlers === 'function') {
    window.addStrikeTableClickHandlers();
  }
}

// === INITIALIZATION ===

// Initialize watchlist functionality when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Load watchlist from preferences on page load
  loadWatchlistFromPreferences();
  
  // Add click handlers to existing strike table rows
  if (typeof window.addStrikeTableClickHandlers === 'function') {
    window.addStrikeTableClickHandlers();
  }
  
  // Also add handlers when strike table is updated
  const originalUpdateStrikeTable = window.updateStrikeTable;
  if (originalUpdateStrikeTable) {
    window.updateStrikeTable = function(...args) {
      originalUpdateStrikeTable.apply(this, args);
      setTimeout(() => {
        if (typeof window.addStrikeTableClickHandlers === 'function') {
          window.addStrikeTableClickHandlers();
        }
        updateWatchlistDisplay(); // Update watchlist after strike table updates
        updateWatchlistBasedOnReco(); // Apply RECO filtering if enabled
        updateClickHandlersForReco(); // Update click handlers based on RECO state
      }, 100); // Small delay to ensure rows are rendered
    };
  }
});

// === GLOBAL FUNCTION EXPORTS ===
window.updateWatchlistDisplay = updateWatchlistDisplay;
window.updateWatchlistBasedOnReco = updateWatchlistBasedOnReco;
window.updateClickHandlersForReco = updateClickHandlersForReco;
window.addToWatchlist = addToWatchlist;
window.removeFromWatchlist = removeFromWatchlist;
window.loadWatchlistFromPreferences = loadWatchlistFromPreferences;
window.saveWatchlistToPreferences = saveWatchlistToPreferences; 