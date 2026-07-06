import { useState, useEffect, useRef } from 'react';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isVerifying, setIsVerifying] = useState(true);
  const [token, setToken] = useState(null);
  const [authError, setAuthError] = useState('');
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [googleClientId, setGoogleClientId] = useState('');

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

  // Fetch Google Client ID on mount
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/auth/google/config');
        if (response.ok) {
          const data = await response.json();
          setGoogleClientId(data.client_id);
        }
      } catch (err) {
        console.error('Failed to load Google OAuth configuration:', err);
      }
    };
    fetchConfig();
  }, []);

  // Listen for Google Auth callback message from the popup window
  useEffect(() => {
    const handleOAuthMessage = async (event) => {
      if (event.data && event.data.type === "GOOGLE_AUTH_SUCCESS") {
        const googleIdToken = event.data.token;
        setIsSigningIn(true);
        setAuthError('');
        try {
          const response = await fetch('http://localhost:8000/api/auth/google/verify', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token: googleIdToken })
          });
          const data = await response.json();
          if (response.ok && data.token) {
            localStorage.setItem('jarvis_token', data.token);
            setToken(data.token);
            setIsAuthenticated(true);
            addLog({ type: 'success', message: 'Google authentication successful.' });
          } else {
            setAuthError(data.detail || 'Google authentication rejected by authority.');
            addLog({ type: 'error', message: 'Google authentication rejected.' });
          }
        } catch (err) {
          setAuthError('Connection to system core failed during Google verification.');
          addLog({ type: 'error', message: `Verification failed: ${err.message}` });
        } finally {
          setIsSigningIn(false);
        }
      }
    };
    window.addEventListener('message', handleOAuthMessage);
    return () => window.removeEventListener('message', handleOAuthMessage);
  }, [googleClientId]);

  const handleGoogleSignIn = () => {
    if (!googleClientId) {
      setAuthError('Google Client ID not configured on system core. Set GOOGLE_CLIENT_ID in backend env.');
      return;
    }
    setAuthError('');
    const width = 500;
    const height = 650;
    const left = window.screen.width / 2 - width / 2;
    const top = window.screen.height / 2 - height / 2;
    const state = Math.random().toString(36).substring(2);
    const nonce = Math.random().toString(36).substring(2);
    
    const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?` + 
      `client_id=${googleClientId}` + 
      `&redirect_uri=http://localhost:8000/api/auth/google/callback` + 
      `&response_type=id_token` + 
      `&scope=openid%20email%20profile` + 
      `&state=${state}` + 
      `&nonce=${nonce}`;

    window.open(
      authUrl,
      "Google Sign-In",
      `width=${width},height=${height},left=${left},top=${top}`
    );
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
              SECURE SYSTEM AUTHORIZATION
            </p>
          </div>

          <div className="flex flex-col gap-4">
            <p className="text-[11px] text-zinc-400 text-center leading-relaxed font-mono">
              Jarvis requires active operator authorization. Please authorize console identity below.
            </p>

            <button
              onClick={handleGoogleSignIn}
              disabled={isSigningIn}
              className="flex items-center justify-center gap-3 bg-[#09090b] border border-[#27272a] hover:border-white text-white py-3.5 px-4 font-semibold text-xs uppercase tracking-wider transition-all mt-2 cursor-pointer w-full disabled:opacity-50"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
              {isSigningIn ? 'AUTHENTICATING...' : 'SIGN IN WITH GOOGLE'}
            </button>

            {!googleClientId && (
              <div className="text-[10px] text-zinc-600 font-mono tracking-tight text-center leading-relaxed mt-2 border border-[#27272a] border-dashed p-3">
                [!] System note: Backend <code className="text-zinc-400">GOOGLE_CLIENT_ID</code> is empty. Configure it in your backend environment variables to enable authentication.
              </div>
            )}

            {authError && (
              <div className="text-[11px] text-rose-500 font-mono tracking-tight leading-relaxed mt-2 flex items-start gap-1 justify-center">
                <span>[!]</span>
                <span>{authError}</span>
              </div>
            )}
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
