import { useState } from "react";
import ChatBot from "./components/ChatBot";

const API_URL = "http://localhost:8000/api";

function App() {
  const [uploading, setUploading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    setStatusMessage("");
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setStatusMessage(data.message || data.detail);
    } catch {
      setStatusMessage("Upload failed. Is the backend running?");
    }
    setUploading(false);
  };

  const handleIngest = async () => {
    setIngesting(true);
    setStatusMessage("");
    try {
      const res = await fetch(`${API_URL}/ingest`, { method: "POST" });
      const data = await res.json();
      setStatusMessage(data.message || data.detail);
    } catch {
      setStatusMessage("Ingestion failed. Is the backend running?");
    }
    setIngesting(false);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Guidelines Assistant</h1>
        <p>Ask questions about your organizational policies and guidelines</p>
      </header>

      <div className="controls">
        <label className="upload-btn">
          {uploading ? "Uploading..." : "Upload Document (.docx)"}
          <input
            type="file"
            accept=".docx"
            onChange={handleUpload}
            disabled={uploading}
            hidden
          />
        </label>
        <button onClick={handleIngest} disabled={ingesting}>
          {ingesting ? "Processing..." : "Ingest Documents"}
        </button>
        {statusMessage && <span className="status">{statusMessage}</span>}
      </div>

      <ChatBot apiUrl={API_URL} />
    </div>
  );
}

export default App;
