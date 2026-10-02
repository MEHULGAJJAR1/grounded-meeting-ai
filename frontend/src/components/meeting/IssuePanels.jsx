import { Badge, Button, SupportBadge } from "../UI";
import { Evidence } from "../Evidence";
export function RisksBody({ meeting, locked, busy, riskStatus, locate }) {
  return !meeting.risks.length ? (
    <p className="muted empty-line">No supported risks were extracted.</p>
  ) : (
    <div className="intelligence-list">
      {meeting.risks.map((risk) => (
        <article key={risk.id}>
          <div className="intelligence-item-top">
            <Badge value={risk.category} />
            <Badge value={risk.status} />
            <Button
              variant="ghost"
              disabled={locked}
              busy={busy === risk.id}
              onClick={() => riskStatus(risk)}
            >
              {risk.status === "Open" ? "Mark resolved" : "Reopen risk"}
            </Button>
          </div>
          <p>{risk.text}</p>
          <div className="claim-meta">
            <SupportBadge item={risk} />
            <Evidence evidence={risk.evidence} onLocate={locate} />
          </div>
        </article>
      ))}
    </div>
  );
}

export function QuestionsBody({
  meeting,
  locked,
  reopenQuestion,
  setQuestion,
  setAnswer,
  locate,
}) {
  return !meeting.questions.length ? (
    <p className="muted empty-line">
      No supported unanswered questions were extracted.
    </p>
  ) : (
    <div className="intelligence-list">
      {meeting.questions.map((q) => (
        <article key={q.id}>
          <div className="intelligence-item-top">
            <Badge value={q.status} />
            <Button
              variant="ghost"
              disabled={locked}
              onClick={() =>
                q.status === "Answered"
                  ? reopenQuestion(q)
                  : (setQuestion(q), setAnswer(q.answer))
              }
            >
              {q.status === "Answered" ? "Reopen question" : "Add an answer"}
            </Button>
          </div>
          <p>{q.text}</p>
          {q.answer && (
            <div className="human-answer">
              <strong>Human-provided answer</strong>
              <p>{q.answer}</p>
            </div>
          )}
          <div className="claim-meta">
            <SupportBadge item={q} />
            <Evidence evidence={q.evidence} onLocate={locate} />
          </div>
        </article>
      ))}
    </div>
  );
}
