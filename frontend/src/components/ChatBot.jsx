import { useState, useRef, useEffect } from "react";

const SESSION_ID = crypto.randomUUID();

function ChatBot({ apiUrl }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const res = await fetch(`${apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage, session_id: SESSION_ID }),
      });
      const data = await res.json();

      if (res.ok) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.answer, sources: data.sources },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Error: ${data.detail}` },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Failed to connect to the backend. Is it running?",
        },
      ]);
    }
    setLoading(false);
  };

  return (
    <div className="chatbot">
      <div className="messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <p>Ask questions about your organizational policies and guidelines.</p>
            <p>Example: "What is the data retention period for PHI data?"</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="message-label">
              {msg.role === "user" ? "You" : "Assistant"}
            </div>
            <div className="message-content">{msg.content}</div>
            {msg.sources && msg.sources.length > 0 && (
              <details className="sources">
                <summary>Sources ({msg.sources.length})</summary>
                {msg.sources.map((s, j) => (
                  <div key={j} className="source-chunk">
                    <div className="source-header">
                      {s.source} &mdash; {s.path}
                    </div>
                    <div className="source-text">
                      {s.text.substring(0, 300)}
                      {s.text.length > 300 ? "..." : ""}
                    </div>
                  </div>
                ))}
              </details>
            )}
          </div>
        ))}
        {loading && (
          <div className="message assistant">
            <div className="message-label">Assistant</div>
            <div className="message-content typing">Thinking...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <form className="input-form" onSubmit={sendMessage}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your guidelines..."
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

export default ChatBot;
