// btcPriceService.js
// Module to fetch live BTC price from backend API and notify subscribers

const BTC_API_URL = "http://localhost:8000/core"; // Adjust if your backend API endpoint differs

export class BtcPriceService {
  constructor(pollIntervalMs = 1000, dbUpdateCallback = null) {
    this.pollIntervalMs = pollIntervalMs;
    this.price = null;
    this.subscribers = [];
    this.polling = false;
    this.intervalId = null;
    this.dbUpdateCallback = dbUpdateCallback;
  }

  async fetchPrice() {
    try {
      const response = await fetch(BTC_API_URL);
      if (!response.ok) throw new Error("Network response not ok");
      const data = await response.json();
      if (data.btc_price !== undefined) {
        this.price = data.btc_price;
        this.notifySubscribers(this.price);
        if (this.dbUpdateCallback) {
          this.dbUpdateCallback(this.price);
        }
      }
    } catch (error) {
      console.error("Error fetching BTC price:", error);
    }
  }

  notifySubscribers(price) {
    this.subscribers.forEach((callback) => callback(price));
  }

  subscribe(callback) {
    this.subscribers.push(callback);
    // Immediately send current price if available
    if (this.price !== null) {
      callback(this.price);
    }
  }

  unsubscribe(callback) {
    this.subscribers = this.subscribers.filter((cb) => cb !== callback);
  }

  startPolling() {
    if (this.polling) return;
    this.polling = true;
    this.fetchPrice();
    this.intervalId = setInterval(() => this.fetchPrice(), this.pollIntervalMs);
  }

  stopPolling() {
    this.polling = false;
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }
}