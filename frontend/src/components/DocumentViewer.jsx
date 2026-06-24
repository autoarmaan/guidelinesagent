import { useState, useEffect } from "react";

function DocumentViewer({ apiUrl }) {
  const [documents, setDocuments] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiUrl}/documents`);
      if (!res.ok) throw new Error(`Failed to load documents (${res.status})`);
      const data = await res.json();
      setDocuments(data);
      if (data.length > 0 && !selected) {
        setSelected(data[0].name);
      }
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const formatSize = (bytes) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const pdfUrl = selected
    ? `${apiUrl}/documents/${encodeURIComponent(selected)}`
    : null;

  return (
    <div className="doc-viewer">
      <div className="doc-sidebar">
        <div className="doc-sidebar-header">
          <h3>Documents</h3>
          <button onClick={fetchDocuments} disabled={loading} title="Refresh">
            {loading ? "..." : "\u21BB"}
          </button>
        </div>
        {error && <div className="doc-error">{error}</div>}
        <ul className="doc-list">
          {documents.map((doc) => (
            <li
              key={doc.name}
              className={`doc-item ${selected === doc.name ? "active" : ""}`}
              onClick={() => setSelected(doc.name)}
              title={doc.name}
            >
              <span className="doc-name">{doc.name}</span>
              <span className="doc-size">{formatSize(doc.size)}</span>
            </li>
          ))}
        </ul>
        {!loading && documents.length === 0 && !error && (
          <div className="doc-empty">No documents found.</div>
        )}
      </div>
      <div className="doc-preview">
        {pdfUrl ? (
          <iframe src={pdfUrl} title={selected} />
        ) : (
          <div className="doc-placeholder">Select a document to preview</div>
        )}
      </div>
    </div>
  );
}

export default DocumentViewer;
