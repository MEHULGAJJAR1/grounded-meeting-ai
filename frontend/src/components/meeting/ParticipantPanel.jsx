import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Avatar } from "../UI";
export function ParticipantsBody({ speakerData, meeting }) {
  return (
    <>
      <p className="section-context">
        Provided participant names are meeting metadata. Speaking share is a
        word count of explicit speaker labels, not inferred airtime or
        personality.
      </p>
      {speakerData.length > 0 && (
        <div className="participant-chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={speakerData}
              margin={{ left: -15, right: 20, top: 10, bottom: 0 }}
              barSize={35}
            >
              <CartesianGrid vertical={false} stroke="#edf0ee" />
              <XAxis
                dataKey="name"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "#6d7b72" }}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
                tick={{ fontSize: 10, fill: "#7c8980" }}
              />
              <Tooltip contentStyle={{ borderRadius: 10, fontSize: 12 }} />
              <Bar
                isAnimationActive={false}
                dataKey="words"
                name="Explicitly labelled words"
                radius={[5, 5, 0, 0]}
                fill="#7aa996"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="participant-grid">
        {meeting.participant_analysis.map((p, index) => (
          <div className="participant-card" key={p.id}>
            <div>
              <Avatar name={p.name} index={index} />
              <span>
                <strong>{p.name}</strong>
                <small>
                  {p.word_count === null
                    ? "Provided metadata only"
                    : `${p.word_count} labelled words · ${Math.round(p.speaking_share * 100)}% share`}
                </small>
              </span>
            </div>
            <p>
              {p.assigned_tasks} assigned{" "}
              {p.assigned_tasks === 1 ? "task" : "tasks"}
            </p>
            <div className="participant-topics">
              {p.topics.length ? (
                p.topics.map((t) => <span key={t}>{t}</span>)
              ) : (
                <span className="muted">No speaker-topic evidence</span>
              )}
            </div>
          </div>
        ))}
      </div>
      {!speakerData.length && (
        <p className="extractive-note">
          No explicit speaker labels are available. Contribution metrics are
          unavailable.
        </p>
      )}
    </>
  );
}
