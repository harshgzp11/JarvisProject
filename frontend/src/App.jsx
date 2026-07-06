import { useState, useEffect, useRef } from 'react';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isVerifying, setIsVerifying] = useState(true);
  const [token, setToken] = useState(null);
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'signup'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');

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

  // Auth handshake on app startup
  useEffect(() => {
    const verifySession = async () => {
      const savedToken = localStorage.getItem('jarvis_token');
      if (!savedToken) {
        setIsVerifying(false);
        setIsAuthenticated(false);
        return;
      }
      try {
        const response = await fetch('http://localhost:8000/api/auth/verify', {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${savedToken}`
          }
        });
        if (response.ok) {
          const data = await response.json();
          setToken(savedToken);
          setIsAuthenticated(true);
          addLog({ type: 'success', message: `Session verified for user: ${data.email}` });
        } else {
          localStorage.removeItem('jarvis_token');
          setIsAuthenticated(false);
          addLog({ type: 'error', message: 'Previous session token is invalid or expired.' });
        }
      } catch (err) {
        console.error(err);
        localStorage.removeItem('jarvis_token');
        setIsAuthenticated(false);
        addLog({ type: 'error', message: 'Authentication handshake failed.' });
      } finally {
        setIsVerifying(false);
      }
    };
    verifySession();
  }, []);

  const addLog = (log) => {
    setLogs((prev) => [...prev, { ...log, id: Date.now() }]);
  };

  const toggleAuthMode = () => {
    setAuthMode((prev) => (prev === 'login' ? 'signup' : 'login'));
    setAuthError('');
    setEmail('');
    setPassword('');
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');

    if (!email.trim() || !password.trim()) {
      setAuthError('Email and password fields are required.');
      return;
    }

    if (authMode === 'signup' && password.length < 8) {
      setAuthError('Password security threshold: minimum 8 characters.');
      return;
    }

    const url = authMode === 'login' 
      ? 'http://localhost:8000/api/auth/login' 
      : 'http://localhost:8000/api/auth/signup';

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email, password })
      });

      const data = await response.json();

      if (!response.ok) {
        setAuthError(data.detail || data.message || 'Authentication transaction rejected.');
        return;
      }

      if (data.token) {
        localStorage.setItem('jarvis_token', data.token);
        setToken(data.token);
        setIsAuthenticated(true);
        setEmail('');
        setPassword('');
        addLog({ type: 'success', message: authMode === 'login' ? 'Authentication successful.' : 'Registration and authentication successful.' });
      } else if (authMode === 'signup') {
        addLog({ type: 'success', message: 'Registration verified. Please authenticate.' });
        setAuthMode('login');
      }
    } catch (err) {
      setAuthError('Network communication error with verification authority.');
      addLog({ type: 'error', message: `Auth error: ${err.message}` });
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('jarvis_token');
    setToken(null);
    setIsAuthenticated(false);
    setMessages([]);
    addLog({ type: 'info', message: 'Session terminated. De-authorized.' });
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = { text: input, sender: 'user' };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    addLog({ type: 'info', message: `dispatch_command: "${userMessage.text}"` });

    try {
      const savedToken = localStorage.getItem('jarvis_token') || token;
      const response = await fetch('http://localhost:8000/api/execute', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${savedToken}`
        },
        body: JSON.stringify({ user_input: userMessage.text }),
      });

      if (response.status === 401) {
        localStorage.removeItem('jarvis_token');
        setToken(null);
        setIsAuthenticated(false);
        addLog({ type: 'error', message: 'Session session has expired or been revoked.' });
        return;
      }

      const data = await response.json();
      
      const aiMessage = { 
        text: data.message, 
        sender: 'ai',
        status: data.status,
        intent: data.intent
      };
      
      setMessages((prev) => [...prev, aiMessage]);
      addLog({ type: data.status === 'success' ? 'success' : 'error', message: `sys_response: ${data.status} - ${data.message}` });
    } catch (error) {
      setMessages((prev) => [...prev, { text: 'Connection to system core failed.', sender: 'ai', status: 'error' }]);
      addLog({ type: 'error', message: `Communication fault: ${error.message}` });
    }
  };

  const handleQuickAction = (actionStr) => {
    setInput(actionStr);
    setTimeout(() => {
      const sendBtn = document.getElementById('send-btn');
      if (sendBtn) sendBtn.click();
    }, 100);
  };

  // 1. Session Verification Loading Interface
  if (isVerifying) {
    return (
      <div className="min-h-screen bg-[#000000] text-white flex flex-col items-center justify-center font-mono p-6">
        <div className="border border-[#27272a] bg-[#09090b] p-6 text-center max-w-sm w-full">
          <div className="text-xs text-zinc-500 mb-2 uppercase tracking-[0.2em]">handshake in progress</div>
          <div className="text-sm text-white font-bold animate-pulse tracking-wide font-mono">VERIFYING JWT SESSION...</div>
        </div>
      </div>
    );
  }

  // 2. Authentication Interface
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#000000] text-white flex flex-col items-center justify-center font-mono p-6">
        <div className="w-full max-w-md bg-[#09090b] border border-[#27272a] p-8 flex flex-col gap-6">
          <div className="flex flex-col gap-2 border-b border-[#27272a] pb-6">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 bg-white"></span>
              <h1 className="text-lg font-bold tracking-[0.15em] text-white">JARVIS SYSTEM</h1>
            </div>
            <p className="text-xs text-zinc-500 uppercase tracking-wider">
              {authMode === 'login' ? 'SECURE SYSTEM AUTHORIZATION' : 'NEW OPERATOR ENROLLMENT'}
            </p>
          </div>

          <form onSubmit={handleAuthSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-zinc-500 uppercase tracking-widest">Operator Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="operator@system.core"
                className="bg-[#000000] border border-[#27272a] text-sm text-white px-3 py-2.5 focus:border-white focus:outline-none font-mono placeholder-zinc-700"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-zinc-500 uppercase tracking-widest">Access Key</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••••••"
                className="bg-[#000000] border border-[#27272a] text-sm text-white px-3 py-2.5 focus:border-white focus:outline-none font-mono placeholder-zinc-700"
              />
            </div>

            {authError && (
              <div className="text-[11px] text-rose-500 font-mono tracking-tight leading-relaxed mt-1 flex items-start gap-1">
                <span className="shrink-0">[!]</span>
                <span>{authError}</span>
              </div>
            )}

            <button
              type="submit"
              className="bg-white hover:bg-zinc-200 text-black py-3 px-4 font-semibold text-xs uppercase tracking-wider transition-all mt-2 cursor-pointer"
            >
              {authMode === 'login' ? 'VERIFY ACCESS' : 'ENROLL OPERATOR'}
            </button>
          </form>

          <div className="border-t border-[#27272a] pt-4 text-center">
            <button
              onClick={toggleAuthMode}
              className="text-[10px] text-zinc-500 hover:text-white uppercase tracking-widest transition-colors font-mono cursor-pointer"
            >
              {authMode === 'login' ? '[ REQUEST ENROLLMENT ]' : '[ ACCESS CONSOLE LOGIN ]'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 3. Authenticated System Dashboard
  return (
    <div className="min-h-screen bg-[#000000] text-white font-mono p-6 flex flex-col md:flex-row gap-6">
      {/* Left Panel: Chat and Control Interface */}
      <div className="flex-1 flex flex-col gap-6">
        <header className="flex items-center justify-between bg-[#09090b] p-4 border border-[#27272a]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-white text-black flex items-center justify-center font-bold text-sm">
              J
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-widest uppercase">JARVIS INTERFACE</h1>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="w-1.5 h-1.5 bg-green-500"></span>
                <span className="text-[9px] text-zinc-500 uppercase tracking-widest">AUTHENTICATED CONSOLE</span>
              </div>
            </div>
          </div>
          <button 
            onClick={handleLogout} 
            className="border border-[#27272a] hover:border-white text-zinc-400 hover:text-white text-[10px] px-3 py-1.5 uppercase transition-all tracking-wider cursor-pointer"
          >
            de-authorize
          </button>
        </header>

        {/* Quick Commands Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <button onClick={() => handleQuickAction('Launch Notepad')} className="bg-[#09090b] hover:bg-[#18181b] p-4 border border-[#27272a] hover:border-[#3f3f46] transition-all text-left flex flex-col gap-1 group cursor-pointer">
            <span className="text-[10px] text-zinc-500 group-hover:text-zinc-400 transition-colors uppercase tracking-widest">launch</span>
            <span className="text-xs font-semibold text-white">notepad.exe</span>
          </button>
          <button onClick={() => handleQuickAction('Take a screenshot')} className="bg-[#09090b] hover:bg-[#18181b] p-4 border border-[#27272a] hover:border-[#3f3f46] transition-all text-left flex flex-col gap-1 group cursor-pointer">
            <span className="text-[10px] text-zinc-500 group-hover:text-zinc-400 transition-colors uppercase tracking-widest">sys_tool</span>
            <span className="text-xs font-semibold text-white">screenshot</span>
          </button>
          <button onClick={() => handleQuickAction('Volume Mute')} className="bg-[#09090b] hover:bg-[#18181b] p-4 border border-[#27272a] hover:border-[#3f3f46] transition-all text-left flex flex-col gap-1 group cursor-pointer">
            <span className="text-[10px] text-zinc-500 group-hover:text-zinc-400 transition-colors uppercase tracking-widest">audio</span>
            <span className="text-xs font-semibold text-white">mute_toggle</span>
          </button>
          <button onClick={() => handleQuickAction('Launch Calculator')} className="bg-[#09090b] hover:bg-[#18181b] p-4 border border-[#27272a] hover:border-[#3f3f46] transition-all text-left flex flex-col gap-1 group cursor-pointer">
            <span className="text-[10px] text-zinc-500 group-hover:text-zinc-400 transition-colors uppercase tracking-widest">launch</span>
            <span className="text-xs font-semibold text-white">calc.exe</span>
          </button>
        </div>

        {/* Chat Terminal Panel */}
        <div className="flex-1 bg-[#09090b] border border-[#27272a] flex flex-col overflow-hidden">
          <div className="p-3 border-b border-[#27272a] bg-[#0c0c0e] flex justify-between items-center">
            <h2 className="text-[10px] font-bold tracking-widest text-zinc-400 uppercase flex items-center gap-1.5">
              <span>CONSOLE_OUTPUT</span>
            </h2>
            <span className="text-[9px] text-zinc-600 uppercase tracking-widest">active_channel_01</span>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
            {messages.length === 0 && (
              <div className="text-center text-zinc-600 my-auto text-xs uppercase tracking-wider">
                System idle. Awaiting user input directive.
              </div>
            )}
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] border px-4 py-3 ${
                  msg.sender === 'user' 
                    ? 'bg-white text-black border-white' 
                    : `bg-[#000000] text-zinc-100 border-[#27272a] ${msg.status === 'error' ? 'border-rose-900 text-rose-300' : ''}`
                }`}>
                  <p className="text-xs whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                  {msg.sender === 'ai' && (
                    <div className="mt-2 pt-1.5 border-t border-[#1c1c1e] text-[9px] text-zinc-500 flex items-center gap-2 uppercase tracking-wider font-mono">
                      <span className={`w-1 h-1 ${msg.status === 'success' ? 'bg-zinc-400' : 'bg-rose-500'}`}></span>
                      {msg.intent && `Intent: ${msg.intent}`}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="p-4 bg-[#000000] border-t border-[#27272a]">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="ENTER INSTRUCTION COMMAND..."
                className="flex-1 bg-[#000000] border border-[#27272a] text-white px-4 py-3 text-xs focus:border-white focus:outline-none placeholder-zinc-700 font-mono"
              />
              <button 
                id="send-btn"
                onClick={handleSend}
                className="bg-white hover:bg-zinc-200 text-black px-5 font-bold text-xs uppercase tracking-wider transition-all active:scale-98 cursor-pointer"
              >
                EXECUTE
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel: Transaction logs */}
      <div className="w-full md:w-80 flex flex-col gap-4">
        <div className="bg-[#09090b] border border-[#27272a] flex-1 flex flex-col overflow-hidden font-mono">
          <div className="p-3 border-b border-[#27272a] bg-[#0c0c0e] flex justify-between items-center">
            <span className="text-[10px] text-zinc-400 font-bold tracking-widest uppercase">event_logger</span>
            <button onClick={() => setLogs([])} className="text-[9px] text-zinc-500 hover:text-white uppercase transition-colors cursor-pointer">[ clear ]</button>
          </div>
          <div className="p-4 flex-1 overflow-y-auto flex flex-col gap-3 text-[11px] leading-relaxed">
            {logs.length === 0 && <span className="text-zinc-700">Awaiting system events...</span>}
            {logs.map(log => (
              <div key={log.id} className="flex gap-2 items-start break-all">
                <span className="text-zinc-600 shrink-0">[{new Date(log.id).toLocaleTimeString()}]</span>
                <span className={
                  log.type === 'error' ? 'text-rose-500' :
                  log.type === 'success' ? 'text-zinc-300 font-semibold' :
                  'text-zinc-400'
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
