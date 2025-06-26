// AppState.js
// Simple global state manager with subscription support

class AppState {
  constructor() {
    this.state = {
      btcPrice: null,
    };
    this.listeners = new Set();
  }

  // Subscribe to state changes
  subscribe(callback) {
    this.listeners.add(callback);
    // Immediately notify with current state
    callback(this.state);
  }

  // Unsubscribe from state changes
  unsubscribe(callback) {
    this.listeners.delete(callback);
  }

  // Internal method to notify all listeners of a state change
  _notify() {
    for (const callback of this.listeners) {
      callback(this.state);
    }
  }

  // Update BTC price and notify if changed
  setBtcPrice(price) {
    if (this.state.btcPrice !== price) {
      this.state.btcPrice = price;
      this._notify();
    }
  }

  // Get current BTC price
  getBtcPrice() {
    return this.state.btcPrice;
  }
}

// Export a singleton instance
const appState = new AppState();
export default appState;
