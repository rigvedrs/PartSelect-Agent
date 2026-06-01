import React from "react";
import "./App.css";
import ChatWidget from "./components/ChatWidget";

function App() {
  return (
    <div className="app-page">
      <div className="app-hero">
        <h1>PartSelect</h1>
        <p>AI Assistant for PartSelect</p>
      </div>
      <ChatWidget />
    </div>
  );
}

export default App;
