export class WarRoom {
  constructor() { this.feed = document.getElementById('chat-feed'); this.currentBubble = null; this.currentAgent = null; this.currentTurn = null; this.briefingActions = document.getElementById('briefing-actions'); }
  clear() { this.feed.innerHTML = ''; this.currentBubble = null; this.briefingActions.style.display = 'none'; }
  appendChunk(payload) {
    const { agent_id, chunk_text, turn_index } = payload;
    if(!this.currentBubble || this.currentAgent !== agent_id || this.currentTurn !== turn_index) {
      const bubble = document.createElement('div'); bubble.className = `agent-bubble ${agent_id.toLowerCase()}`;
      bubble.innerHTML = `<div class="agent-label">${agent_id}</div><div class="agent-text"></div>`;
      this.feed.appendChild(bubble); this.currentBubble = bubble; this.currentAgent = agent_id; this.currentTurn = turn_index;
    }
    const textDiv = this.currentBubble.querySelector('.agent-text'); textDiv.textContent += chunk_text; this.feed.scrollTop = this.feed.scrollHeight;
  }
  completeTurn(payload) {}
  showSystemMessage(msg) { const div = document.createElement('div'); div.className = 'agent-bubble system'; div.innerHTML = `<div class="agent-text">${msg}</div>`; this.feed.appendChild(div); this.feed.scrollTop = this.feed.scrollHeight; }
  showBriefingActions(show) { this.briefingActions.style.display = show ? 'flex' : 'none'; }
  loadTranscript(transcript) { this.clear(); transcript.forEach(turn => { const bubble = document.createElement('div'); bubble.className = `agent-bubble ${turn.agent_id.toLowerCase()}`; bubble.innerHTML = `<div class="agent-label">${turn.agent_id}</div><div class="agent-text">${turn.public_message}</div>`; this.feed.appendChild(bubble); }); this.feed.scrollTop = this.feed.scrollHeight; }
}
