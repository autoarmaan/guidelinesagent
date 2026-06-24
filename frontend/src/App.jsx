import ChatBot from "./components/ChatBot";

const API_URL = "http://localhost:8000/api";

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Guidelines Assistant</h1>
        <p>Ask questions about your organizational policies and guidelines</p>
        <span className="badge">Powered by AI Studio</span>
      </header>

      <ChatBot apiUrl={API_URL} />
    </div>
  );
}

export default App;
