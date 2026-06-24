import ChatBot from "./components/ChatBot";
import DocumentViewer from "./components/DocumentViewer";

const API_URL = "http://localhost:8001/api";

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Guidelines Assistant</h1>
        <p>Ask questions about your organizational policies and guidelines</p>
        <span className="badge">Powered by AI Studio</span>
      </header>

      <div className="app-body">
        <div className="panel panel-left">
          <DocumentViewer apiUrl={API_URL} />
        </div>
        <div className="panel panel-right">
          <ChatBot apiUrl={API_URL} />
        </div>
      </div>
    </div>
  );
}

export default App;
