import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import ChatWidget from './components/ChatWidget';
import reportWebVitals from './reportWebVitals';

const embedRoot = document.getElementById('partselect-chat-widget');
const appRoot = document.getElementById('root');
const rootElement = embedRoot || appRoot;

if (rootElement) {
  const root = createRoot(rootElement);
  root.render(
    <React.StrictMode>
      {embedRoot ? <ChatWidget /> : <App />}
    </React.StrictMode>
  );
}

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
