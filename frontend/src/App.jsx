import { useState, useEffect, useRef } from 'react';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [logs, setLogs] = useState([]);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, logs]);

  const addLog = (log) => {
    setLogs((prev) => [...prev, { ...log, id: Date.now() }]);
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = { text: input, sender: 'user' };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    addLog({ type: 'info', message: `Sending command: ${userMessage.text}` });

    try {
      const response = await fetch('http://localhost:8000/api/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_input: userMessage.text }),
      });

      const data = await response.json();
      
      const aiMessage = { 
        text: data.message, 
        sender: 'ai',
        status: data.status,
        intent: data.intent
      };
      
      setMessages((prev) => [...prev, aiMessage]);
      addLog({ type: data.status === 'success' ? 'success' : 'error', message: `Backend Response: ${data.status} - ${data.message}` });
    } catch (error) {
      setMessages((prev) => [...prev, { text: 'Connection to AI failed.', sender: 'ai', status: 'error' }]);
      addLog({ type: 'error', message: `Connection error: ${error.message}` });
    }
  };

  const handleQuickAction = (actionStr) => {
    setInput(actionStr);
    // Give it a tiny delay so state updates, then we could auto-send, but let's just send it
    setTimeout(() => {
      document.getElementById('send-btn').click();
    }, 100);
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 font-sans p-6 flex flex-col md:flex-row gap-6">
      {/* Left Panel: Chat and Dashboard */}
      <div className="flex-1 flex flex-col gap-6">
        <header className="flex items-center justify-between bg-slate-800 p-4 rounded-xl shadow-lg border border-slate-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-500 rounded-full flex items-center justify-center shadow-lg shadow-indigo-500/50">
              <span className="font-bold text-xl">J</span>
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">
                Jarvis OS Assistant
              </h1>
              <p className="text-xs text-slate-400">System Core Online</p>
            </div>
          </div>
        </header>

        {/* Quick Actions */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <button onClick={() => handleQuickAction('Launch Notepad')} className="bg-slate-800 hover:bg-slate-700 p-4 rounded-xl shadow border border-slate-700 transition-all active:scale-95 flex flex-col items-center gap-2 group">
            <div className="p-2 bg-blue-500/10 text-blue-400 rounded-lg group-hover:bg-blue-500/20">📝</div>
            <span className="text-sm font-medium">Notepad</span>
          </button>
          <button onClick={() => handleQuickAction('Take a screenshot')} className="bg-slate-800 hover:bg-slate-700 p-4 rounded-xl shadow border border-slate-700 transition-all active:scale-95 flex flex-col items-center gap-2 group">
            <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg group-hover:bg-emerald-500/20">📸</div>
            <span className="text-sm font-medium">Screenshot</span>
          </button>
          <button onClick={() => handleQuickAction('Volume Mute')} className="bg-slate-800 hover:bg-slate-700 p-4 rounded-xl shadow border border-slate-700 transition-all active:scale-95 flex flex-col items-center gap-2 group">
            <div className="p-2 bg-rose-500/10 text-rose-400 rounded-lg group-hover:bg-rose-500/20">🔇</div>
            <span className="text-sm font-medium">Mute</span>
          </button>
          <button onClick={() => handleQuickAction('Launch Calculator')} className="bg-slate-800 hover:bg-slate-700 p-4 rounded-xl shadow border border-slate-700 transition-all active:scale-95 flex flex-col items-center gap-2 group">
            <div className="p-2 bg-amber-500/10 text-amber-400 rounded-lg group-hover:bg-amber-500/20">🧮</div>
            <span className="text-sm font-medium">Calculator</span>
          </button>
        </div>

        {/* Chat Panel */}
        <div className="flex-1 bg-slate-800 rounded-xl shadow-lg border border-slate-700 flex flex-col overflow-hidden">
          <div className="p-4 border-b border-slate-700 bg-slate-800/50">
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
              Terminal Interface
            </h2>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
            {messages.length === 0 && (
              <div className="text-center text-slate-500 my-auto text-sm">
                How can I assist your system today?
              </div>
            )}
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-2xl p-3 ${
                  msg.sender === 'user' 
                    ? 'bg-indigo-600 text-white rounded-br-sm shadow-indigo-900/50' 
                    : `bg-slate-700 text-slate-200 rounded-bl-sm border ${msg.status === 'error' ? 'border-rose-500/50' : 'border-slate-600'}`
                } shadow-md`}>
                  <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
                  {msg.sender === 'ai' && (
                    <div className="mt-1 text-[10px] text-slate-400 flex items-center gap-1">
                      <span className={`w-1.5 h-1.5 rounded-full ${msg.status === 'success' ? 'bg-emerald-400' : 'bg-rose-400'}`}></span>
                      {msg.intent && `Intent: ${msg.intent}`}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="p-4 bg-slate-900/50 border-t border-slate-700">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="Type a command (e.g., 'launch notepad')"
                className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent placeholder-slate-500 shadow-inner"
              />
              <button 
                id="send-btn"
                onClick={handleSend}
                className="bg-indigo-600 hover:bg-indigo-500 text-white p-3 rounded-xl shadow-lg shadow-indigo-600/30 transition-all active:scale-95"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 rotate-90" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel: System Logs */}
      <div className="w-full md:w-80 flex flex-col gap-4">
        <div className="bg-slate-950 rounded-xl border border-slate-800 shadow-xl flex-1 flex flex-col overflow-hidden font-mono">
          <div className="p-3 border-b border-slate-800 bg-slate-900 flex justify-between items-center">
            <span className="text-xs text-slate-400 font-semibold tracking-wider">SYSTEM LOGS</span>
            <button onClick={() => setLogs([])} className="text-xs text-slate-500 hover:text-slate-300 transition-colors">Clear</button>
          </div>
          <div className="p-3 flex-1 overflow-y-auto flex flex-col gap-2 text-xs">
            {logs.length === 0 && <span className="text-slate-600">Waiting for events...</span>}
            {logs.map(log => (
              <div key={log.id} className="flex gap-2 items-start break-all">
                <span className="text-slate-500 shrink-0">[{new Date(log.id).toLocaleTimeString()}]</span>
                <span className={
                  log.type === 'error' ? 'text-rose-400' :
                  log.type === 'success' ? 'text-emerald-400' :
                  'text-blue-400'
                }>{log.message}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
