import { Component } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Layout from "./components/Layout";
import { Button, EmptyState, ErrorState, PageSkeleton } from "./components/UI";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Meetings from "./pages/Meetings";
import CreateMeeting from "./pages/CreateMeeting";
import MeetingDetail from "./pages/MeetingDetail";
import Actions from "./pages/Actions";
import Documents from "./pages/Documents";
import Search from "./pages/Search";
import Assistant from "./pages/Assistant";
import Settings from "./pages/Settings";

function Protected() {
  const { user, loading } = useAuth();
  return loading ? (
    <PageSkeleton />
  ) : user ? (
    <Outlet />
  ) : (
    <Navigate to="/login" replace />
  );
}
class AppBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="page">
        <ErrorState
          message="The interface could not render this view. Reload to recover; your saved records are safe."
          onRetry={() => window.location.reload()}
        />
      </div>
    ) : (
      this.props.children
    );
  }
}
export default function App() {
  return (
    <AppBoundary>
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <Routes>
        <Route path="/login" element={<Auth />} />
        <Route path="/register" element={<Auth register />} />
        <Route element={<Protected />}>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="meetings" element={<Meetings />} />
            <Route path="meetings/new" element={<CreateMeeting />} />
            <Route path="meetings/:id/edit" element={<CreateMeeting />} />
            <Route path="meetings/:id" element={<MeetingDetail />} />
            <Route path="actions" element={<Actions />} />
            <Route path="documents" element={<Documents />} />
            <Route path="search" element={<Search />} />
            <Route path="assistant" element={<Assistant />} />
            <Route path="settings" element={<Settings />} />
            <Route
              path="*"
              element={
                <div className="page">
                  <EmptyState
                    title="This page isn’t in your workspace."
                    description="The link may be out of date. Return to your overview to continue."
                  >
                    <Button
                      onClick={() => {
                        window.location.href = "/dashboard";
                      }}
                    >
                      Back to dashboard
                    </Button>
                  </EmptyState>
                </div>
              }
            />
          </Route>
        </Route>
      </Routes>
    </AppBoundary>
  );
}
