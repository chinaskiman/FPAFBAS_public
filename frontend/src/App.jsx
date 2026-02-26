import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import JournalPage from "./pages/JournalPage.jsx";
import JournalDetailPage from "./pages/JournalDetailPage.jsx";
import LevelsPage from "./pages/LevelsPage.jsx";
import OpsPage from "./pages/OpsPage.jsx";
import ReplayPage from "./pages/ReplayPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import ForwardTestPage from "./pages/ForwardTestPage.jsx";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage view="dashboard" />} />
        <Route path="/replay" element={<ReplayPage />} />
        <Route path="/journal" element={<JournalPage />} />
        <Route path="/journal/:signalId" element={<JournalDetailPage />} />
        <Route path="/levels" element={<LevelsPage />} />
        <Route path="/forward-test" element={<ForwardTestPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/ops" element={<OpsPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}
