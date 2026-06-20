export class Registry {
  constructor() { this.pollInterval = null; }
  poll() { this.pollInterval = setInterval(() => this.fetchRegistry(), 5000); this.fetchRegistry(); }
  async fetchRegistry() { try { const res = await fetch('/api/registry'); const data = await res.json(); this.render(data); } catch {} }
  render(entries) {
    const container = document.getElementById('registry-list'); container.innerHTML = '';
    entries.forEach(entry => {
      const div = document.createElement('div'); div.className = 'registry-item';
      div.innerHTML = `<div class="summary">${entry.concept_summary}</div><div class="status">${entry.status} · ${new Date(entry.created_at).toLocaleTimeString()}</div>`;
      div.addEventListener('click', () => this.loadSession(entry.session_id));
      container.appendChild(div);
    });
  }
  async loadSession(id) { try { const res = await fetch(`/api/registry/${id}`); const data = await res.json(); if(window.app) { window.app.warroom.loadTranscript(data.transcript || []); if(data.final_scores) window.app.telemetry.update(data.final_scores); } } catch {} }
}
