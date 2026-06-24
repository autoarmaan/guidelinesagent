import { useState, useEffect, useRef } from "react";

function DocumentViewer({ apiUrl, navigateTo }) {
  const [documents, setDocuments] = useState([]);
  const [selected, setSelected] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const prevNavRef = useRef(null);

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
        setPdfUrl(`${apiUrl}/documents/${encodeURIComponent(data[0].name)}`);
      }
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  // Handle citation navigation from chatbot
  useEffect(() => {
    if (!navigateTo || navigateTo === prevNavRef.current) return;
    prevNavRef.current = navigateTo;

    const match = documents.find((d) => d.name === navigateTo.source)
      || documents.find(
        (d) => d.name.split("/").pop() === navigateTo.source.split("/").pop()
      );

    if (!match) return;

    const base = `${apiUrl}/documents/${encodeURIComponent(match.name)}`;
    const url = navigateTo.page ? `${base}#page=${navigateTo.page}` : base;

    setSelected(match.name);
    setPdfUrl(url);
  }, [navigateTo, documents]);

  const handleDocClick = (name) => {
    setSelected(name);
    setPdfUrl(`${apiUrl}/documents/${encodeURIComponent(name)}`);
  };

  const formatSize = (bytes) => {
    if (!bytes) return "";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

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
              onClick={() => handleDocClick(doc.name)}
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
          <iframe src={pdfUrl} title={selected} key={pdfUrl} />
        ) : (
          <div className="doc-placeholder">Select a document to preview</div>
        )}
      </div>
    </div>
  );
}

export default DocumentViewer;
