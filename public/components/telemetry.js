export class Telemetry {
  constructor() {
    this.bars = { market: document.getElementById('market-bar'), capital: document.getElementById('capital-bar'), risk: document.getElementById('risk-bar') };
    this.values = { market: document.getElementById('market-value'), capital: document.getElementById('capital-value'), risk: document.getElementById('risk-value') };
    this.status = document.getElementById('session-status');
  }
  reset() { this.update({ market_validation:0, capital_efficiency:0, execution_risk:0 }); this.status.textContent = 'Standing by'; }
  update(scores) {
    const { market_validation, capital_efficiency, execution_risk } = scores;
    this.setBar('market', market_validation); this.setBar('capital', capital_efficiency); this.setBar('risk', execution_risk);
    this.status.textContent = `Live · MV:${Math.round(market_validation)} CE:${Math.round(capital_efficiency)} ER:${Math.round(execution_risk)}`;
  }
  setBar(type, value) { const bar = this.bars[type]; const valSpan = this.values[type]; if(bar) bar.style.width = value + '%'; if(valSpan) valSpan.textContent = Math.round(value); }
}
