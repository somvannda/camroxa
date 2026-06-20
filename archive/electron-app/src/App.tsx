import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Home from "@/pages/Home";
import { WebglExportRunner } from "@/components/spectrum/WebglExportRunner";

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const webglExportJobId = String(params.get("webglExportJobId") || "").trim();
  if (webglExportJobId) {
    return <WebglExportRunner jobId={webglExportJobId} />;
  }
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
      </Routes>
    </Router>
  );
}
