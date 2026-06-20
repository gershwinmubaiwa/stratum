import { Registry } from './components/registry.js';
import { WarRoom } from './components/warroom.js';
import { Telemetry } from './components/telemetry.js';

class App {
  constructor() {
    this.registry = new Registry();
    this.warroom = new WarRoom();
    this.telemetry = new Telemetry();
    this.currentSessionId = null;
    this.eventSource = null;
    this.isDebateActive = false;
    window.app = this;

    document.getElementById('start-debate-btn').addEventListener('click', () => this.startDebate());
    document.getElementById('interject-btn').addEventListener('click', () => this.showInterjectModal());
    document.querySelector('.close-btn').addEventListener('click', () => this.hideInterjectModal());
    document.getElementById('submit-interject').addEventListener('click', () => this.submitInterject());
    document.getElementById('copy-briefing-btn').addEventListener('click', () => this.copyBriefing());
    document.getElementById('download-briefing-btn').addEventListener('click', () => this.downloadBriefing());
    document.getElementById('new-debate-btn').addEventListener('click', () => {
      document.getElementById('concept-input').value = '';
      document.getElementById('chat-feed').innerHTML = '';
      this.telemetry.reset();
      this.currentSessionId = null;
      this.closeStream();
    });
    this.registry.poll();
  }

  async startDebate() {
    const concept = document.getElementById('concept-input').value.trim();
    if (!concept) { alert('Please enter a concept.'); return; }
    try {
      const res = await fetch('/api/debate/start', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({concept_text:concept}) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed');
      this.currentSessionId = data.session_id;
      this.isDebateActive = true;
      document.getElementById('interject-btn').style.display = 'inline-block';
      document.getElementById('start-debate-btn').disabled = true;
      this.warroom.clear();
      this.telemetry.reset();
      this.connectStream(data.session_id);
    } catch(e) { alert('Error: '+e.message); }
  }

  connectStream(id) {
    this.closeStream();
    const url = `/api/debate/stream/${id}`;
    this.eventSource = new EventSource(url);
    this.eventSource.addEventListener('chunk', (e) => {
      const payload = JSON.parse(e.data);
      this.warroom.appendChunk(payload);
    });
    this.eventSource.addEventListener('complete', (e) => {
      const payload = JSON.parse(e.data);
      this.warroom.completeTurn(payload);
      this.telemetry.update(payload.telemetry_scores);
    });
    this.eventSource.addEventListener('briefing_ready', (e) => {
      const payload = JSON.parse(e.data);
      this.warroom.showBriefingActions(true);
      this.isDebateActive = false;
      document.getElementById('start-debate-btn').disabled = false;
      document.getElementById('interject-btn').style.display = 'none';
      window._briefingContent = payload.markdown_content;
    });
    this.eventSource.addEventListener('error', (e) => {
      try { const err = JSON.parse(e.data); this.warroom.showSystemMessage('Error: '+err.message); } catch {}
    });
    this.eventSource.onerror = () => { console.warn('SSE error, reconnecting...'); };
  }

  closeStream() { if(this.eventSource) { this.eventSource.close(); this.eventSource = null; } }
  showInterjectModal() { document.getElementById('interject-modal').style.display = 'flex'; }
  hideInterjectModal() { document.getElementById('interject-modal').style.display = 'none'; }
  async submitInterject() {
    const directive = document.getElementById('interject-input').value.trim();
    if(!directive) { alert('Enter directive.'); return; }
    if(!this.currentSessionId) return;
    try {
      const res = await fetch(`/api/debate/interject/${this.currentSessionId}`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:this.currentSessionId, directive_text:directive}) });
      if(!res.ok) throw new Error('Interjection failed');
      this.warroom.showSystemMessage(`[INTERJECT] Course Correction Injected: "${directive}"`);
      this.hideInterjectModal();
      document.getElementById('interject-input').value = '';
    } catch(e) { alert('Interject error: '+e.message); }
  }
  async copyBriefing() { if(window._briefingContent) { try { await navigator.clipboard.writeText(window._briefingContent); alert('Copied!'); } catch {} } }
  downloadBriefing() { if(this.currentSessionId) window.open(`/api/briefing/${this.currentSessionId}/download`, '_blank'); }
}
const app = new App();
