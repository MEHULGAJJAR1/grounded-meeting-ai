import { Link } from "react-router-dom";
import { Copy, FileText } from "lucide-react";
import { Badge } from "../UI";
export function TranscriptBody({ copy, meeting, transcriptLines, highlight }) {
  return (
    <>
      <div className="transcript-toolbar">
        <p>
          Source lines are numbered after whitespace-only preprocessing.
          Uploaded page references are preserved.
        </p>
        <button className="text-btn" onClick={() => copy(meeting.transcript)}>
          <Copy size={14} />
          Copy original
        </button>
      </div>
      {meeting.transcript ? (
        <div className="transcript-view">
          {transcriptLines.map((line, index) => (
            <div
              id={`transcript-line-${index + 1}`}
              className={`transcript-line ${highlight && index + 1 >= highlight[0] && index + 1 <= highlight[1] ? "highlight" : ""}`}
              key={index}
            >
              <span>{index + 1}</span>
              <p>{line || " "}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted empty-line">No transcript is attached.</p>
      )}
      {!!meeting.documents.length && (
        <div className="source-documents">
          <h3>Source documents</h3>
          {meeting.documents.map((d) => (
            <Link to="/documents" key={d.id}>
              <FileText size={15} />
              {d.filename}
              <Badge value={d.processing_status} />
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
