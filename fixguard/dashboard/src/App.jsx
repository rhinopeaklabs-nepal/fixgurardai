import { Route, Routes, useLocation } from "react-router-dom";
import Nav from "./components/Nav";
import Home from "./pages/Home";
import AuditDetail from "./pages/AuditDetail";
import PromptStudio from "./pages/PromptStudio";
import History from "./pages/History";
import Compare from "./pages/Compare";
import Architecture from "./pages/Architecture";
import SharedReport from "./pages/SharedReport";

export default function App() {
  // The public report is standalone: a client following a shared link should
  // not see the owner's navigation.
  const isPublic = useLocation().pathname.startsWith("/r/");
  return (
    <>
      {!isPublic && <Nav />}
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/a/:id" element={<AuditDetail />} />
        <Route path="/prompts" element={<PromptStudio />} />
        <Route path="/history" element={<History />} />
        <Route path="/a/:id/compare" element={<Compare />} />
        <Route path="/architecture" element={<Architecture />} />
        <Route path="/r/:token" element={<SharedReport />} />
        <Route path="*" element={<Home />} />
      </Routes>
    </>
  );
}
