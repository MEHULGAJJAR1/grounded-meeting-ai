import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useNavigate } from "react-router-dom";
import { ListTodo, UserRound } from "lucide-react";
import { CHART_COLORS, dateLabel } from "../services/format";
const tooltipStyle = {
  border: "1px solid #e4e9e5",
  borderRadius: 10,
  fontSize: 12,
  boxShadow: "0 4px 16px #203b2610",
};
export default function DashboardCharts({ chartData, data }) {
  const navigate = useNavigate();
  return (
    <>
      <div className="charts-top-grid">
        <section className="card status-chart">
          <div className="card-heading">
            <div>
              <h2>Action overview</h2>
              <p>A status for every next step</p>
            </div>
            <span className="subtle-chip">All time</span>
          </div>
          <div className="donut-layout">
            <div className="donut-container">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    isAnimationActive={false}
                    data={chartData.by_status.filter((d) => d.value > 0)}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={65}
                    outerRadius={86}
                    paddingAngle={3}
                    stroke="none"
                  >
                    {chartData.by_status
                      .filter((d) => d.value > 0)
                      .map((entry) => (
                        <Cell
                          key={entry.name}
                          fill={
                            CHART_COLORS[
                              [
                                "Pending",
                                "In Progress",
                                "Completed",
                                "Blocked",
                                "Cancelled",
                              ].indexOf(entry.name)
                            ]
                          }
                        />
                      ))}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              <div className="donut-label">
                <strong>{data.total_action_items}</strong>
                <span>total actions</span>
              </div>
            </div>
            <div className="chart-legend">
              {chartData.by_status.map((entry, index) => (
                <button
                  key={entry.name}
                  onClick={() =>
                    navigate(
                      `/actions?status=${encodeURIComponent(entry.name)}`,
                    )
                  }
                >
                  <span
                    className="legend-dot"
                    style={{ background: CHART_COLORS[index] }}
                  />
                  <span>{entry.name}</span>
                  <strong>{entry.value}</strong>
                </button>
              ))}
            </div>
          </div>
        </section>
        <section className="card priority-chart">
          <div className="card-heading">
            <div>
              <h2>Priority breakdown</h2>
              <p>Focus on what matters most</p>
            </div>
            <ListTodo size={18} className="muted" />
          </div>
          <div className="chart-box priority-box">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData.by_priority}
                barSize={36}
                margin={{ top: 5, right: 8, bottom: 0, left: -22 }}
              >
                <CartesianGrid
                  vertical={false}
                  stroke="#edf0ee"
                  strokeDasharray="3 3"
                />
                <XAxis
                  dataKey="name"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#7b8680", fontSize: 11 }}
                  dy={7}
                />
                <YAxis
                  allowDecimals={false}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#9aa49e", fontSize: 10 }}
                />
                <Tooltip
                  cursor={{ fill: "#f5f8f6" }}
                  contentStyle={tooltipStyle}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="value"
                  name="Actions"
                  radius={[5, 5, 0, 0]}
                >
                  {chartData.by_priority.map((entry, index) => (
                    <Cell
                      key={entry.name}
                      fill={["#bed8ce", "#7bafa0", "#e9b77a", "#e98d83"][index]}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>
      <div className="charts-lower-grid">
        <section className="card activity-chart">
          <div className="card-heading">
            <div>
              <h2>Meeting momentum</h2>
              <p>Meetings recorded by calendar month</p>
            </div>
            <span className="subtle-chip">Last 6 months</span>
          </div>
          <div className="chart-box activity-box">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData.over_time.map((entry) => ({
                  ...entry,
                  label: dateLabel(`${entry.month}-01`, {
                    day: undefined,
                  }),
                }))}
                margin={{ top: 5, right: 10, bottom: 0, left: -24 }}
              >
                <defs>
                  <linearGradient id="meetingFill" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#268166" stopOpacity={0.16} />
                    <stop offset="100%" stopColor="#268166" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  vertical={false}
                  stroke="#edf0ee"
                  strokeDasharray="3 3"
                />
                <XAxis
                  dataKey="label"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#7b8680", fontSize: 11 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  allowDecimals={false}
                  tick={{ fill: "#9aa49e", fontSize: 10 }}
                />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend
                  iconType="circle"
                  iconSize={7}
                  wrapperStyle={{ fontSize: 11, paddingTop: 10 }}
                />
                <Area
                  isAnimationActive={false}
                  type="monotone"
                  dataKey="meetings"
                  name="Meetings"
                  stroke="#258469"
                  fill="url(#meetingFill)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="card owner-chart">
          <div className="card-heading">
            <div>
              <h2>Who’s on it?</h2>
              <p>Top six owners by recorded action count</p>
            </div>
            <UserRound size={18} className="muted" />
          </div>
          <div className="chart-box owner-box">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={chartData.by_owner.slice(0, 6)}
                margin={{ top: 0, left: 0, bottom: 0, right: 20 }}
                barSize={12}
              >
                <XAxis type="number" allowDecimals={false} hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={92}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#637168", fontSize: 11 }}
                />
                <Tooltip cursor={false} contentStyle={tooltipStyle} />
                <Bar
                  isAnimationActive={false}
                  dataKey="value"
                  name="Tasks"
                  radius={[0, 4, 4, 0]}
                  fill="#78a996"
                  label={{
                    position: "right",
                    fill: "#637168",
                    fontSize: 11,
                  }}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      </div>

      <div className="charts-top-grid">
        <TrendPanel
          data={chartData.over_time}
          metric="decisions"
          title="Decisions over time"
          description="Confirmed, tentative and rejected records"
          color="#9585d4"
        />
        <TrendPanel
          data={chartData.over_time}
          metric="risks"
          title="Risks over time"
          description="Risk and blocker records by meeting month"
          color="#d6a369"
        />
      </div>
    </>
  );
}
function TrendPanel({ data, metric, title, description, color }) {
  return (
    <section className="card activity-chart">
      <div className="card-heading">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <span className="subtle-chip">Last 6 months</span>
      </div>
      <div className="chart-box priority-box">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data.map((entry) => ({
              ...entry,
              label: dateLabel(`${entry.month}-01`, { day: undefined }),
            }))}
            barSize={30}
            margin={{ top: 5, right: 10, bottom: 0, left: -22 }}
          >
            <CartesianGrid
              vertical={false}
              stroke="#edf0ee"
              strokeDasharray="3 3"
            />
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#7b8680", fontSize: 11 }}
            />
            <YAxis
              allowDecimals={false}
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#9aa49e", fontSize: 10 }}
            />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar
              dataKey={metric}
              name={title.split(" over")[0]}
              fill={color}
              radius={[5, 5, 0, 0]}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
