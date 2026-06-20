from datetime import datetime
from app.models.schemas import BriefingDocument
def generate_briefing(session):
    lines = [f"# Executive Briefing: {session.concept_text[:60]}...", f"**Generated:** {datetime.utcnow().isoformat()}", ""]
    lines.append("## Debate Transcript")
    for turn in session.transcript:
        lines.append(f"**{turn.agent_id} (Turn {turn.turn_index+1}):**"); lines.append(turn.public_message); lines.append("")
    if session.final_scores:
        lines.append("## Final Telemetry Scores"); lines.append(f"- Market Validation: {session.final_scores.market_validation:.1f}/100"); lines.append(f"- Capital Efficiency: {session.final_scores.capital_efficiency:.1f}/100"); lines.append(f"- Execution Risk: {session.final_scores.execution_risk:.1f}/100")
    lines.append("\n---\n*This briefing was generated automatically by Stratum.*")
    return BriefingDocument(session_id=session.session_id, markdown_content="\n".join(lines), generated_at=datetime.utcnow())
