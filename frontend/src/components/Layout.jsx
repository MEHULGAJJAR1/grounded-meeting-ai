import { useEffect, useRef, useState } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Bell,
  BookOpen,
  CalendarDays,
  ChevronRight,
  FileText,
  LayoutDashboard,
  ListTodo,
  LogOut,
  Menu,
  MessageSquareText,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { api, errorMessage } from "../services/api";
import { dateLabel } from "../services/format";
import { Avatar, Brand, EmptyState } from "./UI";

const LINKS = [
  ["/dashboard", "Dashboard", LayoutDashboard],
  ["/meetings", "Meetings", CalendarDays],
  ["/actions", "Action items", ListTodo],
  ["/documents", "Documents", FileText],
  ["/assistant", "AI assistant", MessageSquareText],
  ["/search", "Smart search", Search],
];
const TITLES = {
  dashboard: "Overview",
  meetings: "Meetings",
  actions: "Action items",
  documents: "Documents",
  assistant: "AI assistant",
  search: "Smart search",
  settings: "Settings",
};

export default function Layout() {
  const { user, logout, configuration } = useAuth();
  const toast = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [search, setSearch] = useState("");
  const searchInput = useRef(null);
  const [notifications, setNotifications] = useState({ items: [], unread: 0 });
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notificationLoading, setNotificationLoading] = useState(false);
  useEffect(() => {
    setMobileOpen(false);
    setNotificationsOpen(false);
    if (location.hash) {
      requestAnimationFrame(() =>
        document
          .getElementById(location.hash.slice(1))
          ?.scrollIntoView({ block: "start" }),
      );
    } else window.scrollTo({ top: 0 });
  }, [location.pathname, location.hash]);
  useEffect(() => {
    const handler = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "k") {
        event.preventDefault();
        searchInput.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  useEffect(() => {
    api
      .get("/notifications")
      .then(({ data }) => setNotifications(data))
      .catch(() => {});
  }, [location.pathname]);
  async function toggleNotifications() {
    setNotificationsOpen(!notificationsOpen);
    if (!notificationsOpen) {
      setNotificationLoading(true);
      try {
        const { data } = await api.get("/notifications");
        setNotifications(data);
      } catch (error) {
        toast(errorMessage(error), "error");
      } finally {
        setNotificationLoading(false);
      }
    }
  }
  async function openNotification(item) {
    try {
      await api.put(`/notifications/${item.id}/read`);
      setNotifications((old) => ({
        items: old.items.map((n) =>
          n.id === item.id ? { ...n, is_read: true } : n,
        ),
        unread: Math.max(0, old.unread - (item.is_read ? 0 : 1)),
      }));
    } catch (error) {
      toast(errorMessage(error), "error");
    }
    if (item.meeting_id) navigate(`/meetings/${item.meeting_id}`);
    else setNotificationsOpen(false);
  }
  async function signOut() {
    try {
      await logout();
      navigate("/login");
    } catch {
      navigate("/login");
    }
  }
  return (
    <div className="app-shell">
      {mobileOpen && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
        <div className="sidebar-brand">
          <Brand />
          <button
            className="icon-btn mobile-only"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <div className="workspace-label">
          <span className="workspace-icon">G</span>
          <div>
            My workspace<small>Personal workspace</small>
          </div>
          <span className="workspace-dot" />
        </div>
        <Link to="/meetings/new" className="btn btn-primary new-meeting">
          <Plus size={17} />
          New meeting
        </Link>
        <div className="nav-label">WORKSPACE</div>
        <nav className="main-nav" aria-label="Main navigation">
          {LINKS.map(([to, label, Icon]) => (
            <NavLink
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
              to={to}
              key={to}
            >
              <Icon size={19} />
              <span>{label}</span>
              {to === "/assistant" && <span className="nav-ai">AI</span>}
            </NavLink>
          ))}
        </nav>
        <div className="nav-divider" />
        <nav aria-label="Account navigation">
          <NavLink
            to="/settings"
            className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
          >
            <Settings size={19} />
            <span>Settings</span>
          </NavLink>
        </nav>
        <div className="sidebar-bottom">
          <div className="trust-card">
            <ShieldCheck size={22} />
            <h4>Evidence. Not guesswork.</h4>
            <p>Every insight has a source. Every action has a trail.</p>
            <Link to="/settings#ai">
              How grounding works <ChevronRight size={14} />
            </Link>
          </div>
          <div className="user-strip">
            <Link to="/settings" className="user-link">
              <Avatar name={user.name} />
              <span>
                {user.name}
                <small>
                  {user.is_demo ? "Sample workspace" : "Your account"}
                </small>
              </span>
            </Link>
            <button
              onClick={signOut}
              className="icon-btn"
              aria-label="Log out"
              title="Log out"
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-btn mobile-only"
              aria-label="Open navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={22} />
            </button>
            <span className="breadcrumb">
              Workspace <ChevronRight size={14} />{" "}
              <strong>
                {TITLES[location.pathname.split("/")[1]] || "Workspace"}
              </strong>
            </span>
          </div>
          <div className="topbar-right">
            <form
              className="global-search"
              onSubmit={(event) => {
                event.preventDefault();
                if (search.trim())
                  navigate(`/search?q=${encodeURIComponent(search.trim())}`);
              }}
            >
              <Search size={16} />
              <input
                ref={searchInput}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search your workspace"
                aria-label="Search workspace"
              />
              <kbd>⌘ K</kbd>
            </form>
            <Link
              className={`engine-indicator ${configuration?.provider === "openai" ? "openai" : ""}`}
              to="/settings#ai"
            >
              <span />
              {configuration?.provider === "openai" ? "OpenAI" : "Local engine"}
            </Link>
            <div className="notification-wrap">
              <button
                className="icon-btn bell-button"
                aria-label="Notifications"
                aria-expanded={notificationsOpen}
                onClick={toggleNotifications}
              >
                <Bell size={20} />
                {notifications.unread > 0 && (
                  <span className="notification-dot" />
                )}
              </button>
              {notificationsOpen && (
                <div className="notification-menu">
                  <div className="popover-heading">
                    <h3>Notifications</h3>
                    <button
                      className="icon-btn"
                      aria-label="Close notifications"
                      onClick={() => setNotificationsOpen(false)}
                    >
                      <X size={16} />
                    </button>
                  </div>
                  {notificationLoading ? (
                    <p className="muted padded">Loading notifications…</p>
                  ) : !notifications.items.length ? (
                    <EmptyState
                      compact
                      icon={Bell}
                      title="You're all caught up"
                      description="Processing and deadline reminders will appear here."
                    />
                  ) : (
                    <div className="notification-list">
                      {notifications.items.map((item) => (
                        <button
                          className={`notification-item ${item.is_read ? "read" : ""}`}
                          key={item.id}
                          onClick={() => openNotification(item)}
                        >
                          <span className="notification-item-icon">
                            <Bell size={16} />
                          </span>
                          <span>
                            <strong>{item.title}</strong>
                            <small>{item.message}</small>
                            <em>{dateLabel(item.created_at)}</em>
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
            <Link to="/settings" aria-label="Account settings">
              <Avatar name={user.name} small />
            </Link>
          </div>
        </header>
        {user.is_demo && (
          <div className="demo-banner">
            <BookOpen size={14} />
            <span>
              Sample workspace · fictional meetings, real extraction and working
              records.
            </span>
            <Link to="/register">
              Create your own account <ChevronRight size={13} />
            </Link>
          </div>
        )}
        <main id="main-content">
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>Grounded · clarity you can trace.</span>
          <span>
            <ShieldCheck size={12} />
            Private to your workspace
          </span>
        </footer>
      </div>
    </div>
  );
}
