import { useState, useEffect, useRef } from 'react';

const parseJwt = (token) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      window.atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    console.error('Error decoding JWT token:', e);
    return null;
  }
};

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isVerifying, setIsVerifying] = useState(true);
  const [token, setToken] = useState(null);
  const [user, setUser] = useState({ name: '', email: '', picture: '' });
  const [authError, setAuthError] = useState('');
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [googleClientId, setGoogleClientId] = useState('');

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [command, setCommand] = useState('');
  const [logs, setLogs] = useState([]);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [metrics, setMetrics] = useState({ cpu: 0, ram: 0 });
  const [dbLogs, setDbLogs] = useState([]);
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [files, setFiles] = useState([]);
  const [isOverlayOpen, setIsOverlayOpen] = useState(false);
  const overlayInputRef = useRef(null);
  const recognitionRef = useRef(null);

  const fetchWorkspaceFiles = async () => {
    const savedToken = localStorage.getItem('jarvis_token');
    if (!savedToken) return;
    try {
      const response = await fetch('http://localhost:8000/api/system/files', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${savedToken}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setFiles(data);
      }
    } catch (err) {
      console.error("Failed to fetch workspace files:", err);
    }
  };

  // Initialize the browser speech recognition adapter once
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSpeechSupported(false);
      recognitionRef.current = null;
      return;
    }

    setSpeechSupported(true);
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      setIsListening(false);
    };

    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript?.trim();
      if (transcript) {
        setInput(transcript);
      }
    };

    recognitionRef.current = recognition;
    return () => {
      recognition.stop?.();
      recognitionRef.current = null;
    };
  }, []);

  const toggleVoiceRecognition = () => {
    const recognition = recognitionRef.current;
    if (!recognition) return;

    if (isListening) {
      recognition.stop();
      return;
    }

    try {
      recognition.start();
    } catch (err) {
      console.error('Unable to start speech recognition:', err);
    }
  };

  useEffect(() => {
    const handleGlobalKeyDown = (event) => {
      if (event.ctrlKey && event.code === 'Space') {
        event.preventDefault();
        setIsOverlayOpen((prev) => !prev);
      }
      if (event.key === 'Escape' && isOverlayOpen) {
        setIsOverlayOpen(false);
      }
    };
    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
  }, [isOverlayOpen]);

  useEffect(() => {
    if (isOverlayOpen) {
      overlayInputRef.current?.focus();
    }
  }, [isOverlayOpen]);

  // Poll database workspace files listing
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchWorkspaceFiles();
    const interval = setInterval(fetchWorkspaceFiles, 3000);
    return () => clearInterval(interval);
  }, [isAuthenticated, token]);

  const fetchLogs = async () => {
    const savedToken = localStorage.getItem('jarvis_token');
    if (!savedToken) return;
    try {
      const response = await fetch('http://localhost:8000/api/system/logs', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${savedToken}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setDbLogs(data);
      }
    } catch (err) {
      console.error("Failed to fetch system logs:", err);
    }
  };

  // Poll hardware metrics every 3 seconds
  useEffect(() => {
    if (!isAuthenticated) return;
    const fetchMetrics = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/system/metrics');
        if (response.ok) {
          const data = await response.json();
          setMetrics({ cpu: data.cpu, ram: data.ram });
        }
      } catch (err) {
        console.error("Metrics poll failed:", err);
      }
    };
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 3000);
    return () => clearInterval(interval);
  }, [isAuthenticated]);

  // Poll database assistant logs every 3 seconds
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, [isAuthenticated, token]);

  // Reconstruct chat thread messages from active database logs to sync voice and quick dispatches
  useEffect(() => {
    if (dbLogs && dbLogs.length > 0) {
      const thread = [];
      dbLogs.forEach((log) => {
        if (log.user_input) {
          thread.push({
            text: log.user_input,
            sender: 'user'
          });
        }
        if (log.ai_response) {
          thread.push({
            text: log.ai_response,
            sender: 'ai',
            intent: log.detected_intent || 'GENERAL_QUERY',
            action: null,
            execution_type: null,
            payload: null
          });
        }
      });
      setMessages(thread);
    }
  }, [dbLogs]);

  const triggerSystemAction = async (message) => {
    try {
      const savedToken = localStorage.getItem('jarvis_token') || token;
      addLog({ type: 'info', message: `dispatch_quick_action: "${message}"` });
      
      const response = await fetch('http://localhost:8000/api/assistant/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${savedToken}`
        },
        body: JSON.stringify({ message }),
      });
      
      if (response.ok) {
        const data = await response.json();
        addLog({ 
          type: data.action !== 'none' ? 'success' : 'info', 
          message: `quick_action_response: [${data.intent}] - ${data.response}` 
        });
        fetchLogs();
        fetchWorkspaceFiles();
      } else {
        addLog({ type: 'error', message: 'Quick action request rejected.' });
      }
    } catch (error) {
      addLog({ type: 'error', message: `Quick action failed: ${error.message}` });
    }
  };

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (activeTab === 'assistant') {
      scrollToBottom();
    }
  }, [messages, activeTab]);

  useEffect(() => {
    const logContainer = document.getElementById('log-container');
    if (logContainer) {
      logContainer.scrollTop = logContainer.scrollHeight;
    }
  }, [logs, activeTab]);

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
          
          // Load user details from storage
          const savedUser = localStorage.getItem('jarvis_user');
          if (savedUser) {
            setUser(JSON.parse(savedUser));
          } else if (data.email) {
            setUser({
              name: data.email.split('@')[0],
              email: data.email,
              picture: ''
            });
          }
          addLog({ type: 'success', message: `Session verified for user: ${data.email}` });
        } else {
          localStorage.removeItem('jarvis_token');
          localStorage.removeItem('jarvis_user');
          setIsAuthenticated(false);
          addLog({ type: 'error', message: 'Previous session token is invalid or expired.' });
        }
      } catch (err) {
        console.error(err);
        localStorage.removeItem('jarvis_token');
        localStorage.removeItem('jarvis_user');
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
            // Decode Google ID Token for profile details
            const decoded = parseJwt(googleIdToken);
            if (decoded) {
              const userInfo = {
                name: decoded.name || '',
                email: decoded.email || '',
                picture: decoded.picture || ''
              };
              localStorage.setItem('jarvis_user', JSON.stringify(userInfo));
              setUser(userInfo);
            }
            
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
    localStorage.removeItem('jarvis_user');
    setToken(null);
    setUser({ name: '', email: '', picture: '' });
    setIsAuthenticated(false);
    setMessages([]);
    addLog({ type: 'info', message: 'Session terminated. De-authorized.' });
  };

  const handleSend = async (messageText) => {
    const outgoingText = typeof messageText === 'string' ? messageText : input;
    if (!outgoingText.trim()) return;

    const userMessage = { text: outgoingText, sender: 'user' };
    setMessages((prev) => [...prev, userMessage]);
    setCommand('');
    addLog({ type: 'info', message: `dispatch_command: "${userMessage.text}"` });

    try {
      const savedToken = localStorage.getItem('jarvis_token') || token;
      const response = await fetch('http://localhost:8000/api/assistant/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${savedToken}`
        },
        body: JSON.stringify({ message: userMessage.text }),
      });

      if (response.status === 401) {
        localStorage.removeItem('jarvis_token');
        localStorage.removeItem('jarvis_user');
        setToken(null);
        setIsAuthenticated(false);
        addLog({ type: 'error', message: 'Session session has expired or been revoked.' });
        return;
      }

      const data = await response.json();
      
      const aiMessage = { 
        text: data.response, 
        sender: 'ai',
        intent: data.intent,
        action: data.action,
        execution_type: data.execution_type || null,
        payload: data.payload || null
      };
      
      setMessages((prev) => [...prev, aiMessage]);
      setInput('');
      overlayInputRef.current?.focus();
      addLog({ 
        type: data.action !== 'none' ? 'success' : 'info', 
        message: `sys_response: [${data.intent}] - ${data.response}` 
      });
    } catch (error) {
      setMessages((prev) => [...prev, { text: 'Connection to system core failed.', sender: 'ai', intent: 'GENERAL_QUERY', action: 'none' }]);
      addLog({ type: 'error', message: `Communication fault: ${error.message}` });
    }
  };

  const handleQuickAction = (actionStr) => {
    setInput(actionStr);
    setActiveTab('assistant');
    setTimeout(() => {
      const sendBtn = document.getElementById('send-btn');
      if (sendBtn) sendBtn.click();
    }, 150);
  };

  // 1. Session Verification Loading Interface
  if (isVerifying) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6 font-sans">
        <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-8 max-w-sm w-full text-center shadow-sm">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-bold mb-1">Handshake in progress</div>
          <div className="text-xs font-bold text-zinc-100 tracking-wide font-mono">VERIFYING JWT SESSION...</div>
        </div>
      </div>
    );
  }

  // 2. Authentication Interface (Immersive Dark-Mode Premium - Split-Screen View)
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen w-screen bg-[#000000] flex items-center justify-center p-8 md:p-16 lg:p-24 relative overflow-hidden font-sans select-none text-zinc-300">
        <div className="w-full max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-24 items-center">
          
          {/* Left Column: Giant Solid White Triangle Logo (desktop view) */}
          <div className="hidden lg:flex items-center justify-center w-full h-full z-10">
            <span className="text-white text-[200px] lg:text-[320px] font-extrabold select-none leading-none drop-shadow-[0_0_40px_rgba(255,255,255,0.03)]">
              ▲
            </span>
          </div>

          {/* Right Column: Content Assembly */}
          <div className="max-w-md w-full mx-auto lg:mx-0 text-center lg:text-left flex flex-col items-center lg:items-start space-y-14 z-10 lg:pl-12">
            {/* Small top logo for mobile and tablet/split-screen viewports - clean white-filled triangle ▲ */}
            <div className="text-white text-9xl font-extrabold select-none lg:hidden leading-none mb-8">
              ▲
            </div>

            <div className="space-y-4">
              <h1 className="text-3xl md:text-4xl lg:text-5xl font-extrabold tracking-tighter text-white font-sans leading-tight text-center lg:text-left">
                Access Jarvis System Core.
              </h1>
            </div>

            {/* Form actions and buttons */}
            <div className="space-y-4 w-full flex flex-col items-center lg:items-start">
              <button
                onClick={handleGoogleSignIn}
                disabled={isSigningIn}
                className="w-full max-w-[320px] h-12 bg-white text-zinc-900 rounded-full font-bold flex items-center justify-center space-x-3 hover:bg-zinc-100 transition-all duration-200 shadow-md cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98] group"
              >
                <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                <span className="text-sm font-bold text-zinc-950">Continue with Google</span>
              </button>

              <button
                onClick={async () => {
                  try {
                    setIsSigningIn(true);
                    setAuthError('');
                    const response = await fetch('http://localhost:8000/api/auth/google/verify', {
                      method: 'POST',
                      headers: {
                        'Content-Type': 'application/json'
                      },
                      body: JSON.stringify({ token: 'mock_google_id_token' })
                    });
                    const data = await response.json();
                    if (response.ok && data.token) {
                      const userInfo = {
                        name: 'Test Operator',
                        email: 'operator@jarvis.local',
                        picture: ''
                      };
                      localStorage.setItem('jarvis_token', data.token);
                      localStorage.setItem('jarvis_user', JSON.stringify(userInfo));
                      setToken(data.token);
                      setUser(userInfo);
                      setIsAuthenticated(true);
                      addLog({ type: 'success', message: 'Mock Google authentication bypass successful.' });
                    } else {
                      setAuthError(data.detail || 'Mock authentication rejected.');
                    }
                  } catch (err) {
                    setAuthError('Connection to system core failed.');
                  } finally {
                    setIsSigningIn(false);
                  }
                }}
                disabled={isSigningIn}
                className="w-full max-w-[320px] h-12 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full font-bold flex items-center justify-center transition-all duration-200 mt-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-sm font-sans"
              >
                BYPASS FOR TESTING (MOCK)
              </button>

              {!googleClientId && (
                <div className="text-[9px] text-zinc-550 font-mono tracking-tight leading-relaxed max-w-xs border border-zinc-900 border-dashed p-3 rounded bg-zinc-950/20 text-center lg:text-left">
                  [!] Presets missing: Core <code className="text-zinc-400 bg-zinc-900 px-1 py-0.5 rounded">GOOGLE_CLIENT_ID</code> parameter is empty. Configure environment settings to proceed.
                </div>
              )}

              {authError && (
                <div className="text-[10px] text-rose-450 font-mono tracking-tight leading-relaxed bg-red-950/20 p-3 rounded-lg border border-red-900/30 flex items-start gap-2 max-w-xs text-center lg:text-left">
                  <span className="font-semibold shrink-0 select-none">[!]</span>
                  <span>{authError}</span>
                </div>
              )}
            </div>

            <div className="pt-6 border-t border-zinc-900 max-w-md w-full text-center lg:text-left">
              <span className="text-[10px] font-mono text-emerald-500 uppercase tracking-widest font-semibold">
                SYSTEM STATUS: ACTIVE
              </span>
            </div>
          </div>

        </div>
      </div>
    );
  }

  // Navigation configurations
  const navItems = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: (
        <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2v-4zM14 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2v-4z" />
        </svg>
      )
    },
    {
      id: 'assistant',
      label: 'AI Assistant',
      icon: (
        <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
      )
    },
    {
      id: 'settings',
      label: 'Core Settings',
      icon: (
        <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      )
    },
    {
      id: 'profile',
      label: 'Profile',
      icon: (
        <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      )
    }
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return (
          <div className="space-y-8 max-w-7xl">
            {/* Header Greeting */}
            <div>
              <h1 className="text-xl font-bold text-gray-900 tracking-tight font-sans">Welcome back, {user.name ? user.name.split(' ')[0] : 'Operator'}</h1>
              <p className="text-xs text-gray-500 mt-1 font-medium font-sans">Observe system status metrics and trigger localized scripts.</p>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {/* Metric Card 1 */}
              <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm flex flex-col justify-between hover:border-gray-200 transition-colors duration-200">
                <span className="text-[10px] uppercase tracking-wider text-gray-400 font-bold font-sans">System Core</span>
                <div className="mt-4 flex items-baseline justify-between">
                  <span className="text-base font-bold text-gray-900 font-sans">Active</span>
                  <span className="text-[10px] text-emerald-600 font-bold flex items-center gap-1 font-sans">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    VERIFIED
                  </span>
                </div>

                <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-6 shadow-sm flex flex-col h-[280px]">
                  <div className="flex justify-between items-center mb-4 shrink-0">
                    <div>
                      <h3 className="text-sm font-bold text-zinc-100">Smart File Memory Indexer</h3>
                      <p className="text-xs text-zinc-400 mt-0.5">Workspace Files in C:\Users\Public\JarvisWorkspace</p>
                    </div>
                    <button
                      onClick={fetchWorkspaceFiles}
                      className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 hover:underline cursor-pointer"
                    >
                      Sync Index
                    </button>
                  </div>
                  
                  <div className="flex-1 overflow-y-auto space-y-2 pr-1 text-[11px] font-medium scrollbar-thin">
                    {files.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center text-zinc-550 border border-dashed border-zinc-850/60 p-4 rounded-xl">
                        <span className="italic block font-mono text-[10px]">[ INDEX EMPTY ]</span>
                        <span className="block mt-1 leading-relaxed text-zinc-500">No memory files found inside the workspace namespace. Ask the assistant to write notes or create files to populate.</span>
                      </div>
                    ) : (
                      files.map(file => (
                        <div key={file.name} className="flex justify-between items-center p-2.5 bg-zinc-900/30 border border-zinc-850/60 hover:border-zinc-700/60 rounded-xl transition-all duration-150">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span className="w-2 h-2 rounded bg-indigo-500 shrink-0"></span>
                            <div className="min-w-0">
                              <span className="font-mono text-zinc-200 block truncate text-xs">{file.name}</span>
                              <span className="text-[10px] text-zinc-550 block font-mono mt-0.5">{new Date(file.modified).toLocaleTimeString()}</span>
                            </div>
                          </div>
                          <span className="text-[10px] text-zinc-500 font-mono shrink-0 select-none bg-zinc-950 px-2 py-0.5 rounded border border-zinc-900">{(file.size / 1024).toFixed(2)} KB</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
              {/* Metric Card 2 */}
              <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm flex flex-col justify-between hover:border-gray-200 transition-colors duration-200">
                <span className="text-[10px] uppercase tracking-wider text-gray-400 font-bold font-sans">Local LLM Router</span>
                <div className="mt-4 flex items-baseline justify-between">
                  <span className="text-base font-bold text-gray-900 font-sans">Llama 3.2</span>
                  <span className="text-[10px] text-gray-400 font-bold font-sans">OLLAMA</span>
                </div>

                <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-6 shadow-sm flex flex-col h-[280px]">
                  <div className="flex justify-between items-center mb-4 shrink-0">
                    <div>
                      <h3 className="text-sm font-bold text-zinc-100">Smart File Memory Indexer</h3>
                      <p className="text-xs text-zinc-400 mt-0.5">Workspace Files in C:\Users\Public\JarvisWorkspace</p>
                    </div>
                    <button
                      onClick={fetchWorkspaceFiles}
                      className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 hover:underline cursor-pointer"
                    >
                      Sync Index
                    </button>
                  </div>
                  
                  <div className="flex-1 overflow-y-auto space-y-2 pr-1 text-[11px] font-medium scrollbar-thin">
                    {files.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center text-zinc-550 border border-dashed border-zinc-850/60 p-4 rounded-xl">
                        <span className="italic block font-mono text-[10px]">[ INDEX EMPTY ]</span>
                        <span className="block mt-1 leading-relaxed text-zinc-500">No memory files found inside the workspace namespace. Ask the assistant to write notes or create files to populate.</span>
                      </div>
                    ) : (
                      files.map(file => (
                        <div key={file.name} className="flex justify-between items-center p-2.5 bg-zinc-900/30 border border-zinc-850/60 hover:border-zinc-700/60 rounded-xl transition-all duration-150">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span className="w-2 h-2 rounded bg-indigo-500 shrink-0"></span>
                            <div className="min-w-0">
                              <span className="font-mono text-zinc-200 block truncate text-xs">{file.name}</span>
                              <span className="text-[10px] text-zinc-550 block font-mono mt-0.5">{new Date(file.modified).toLocaleTimeString()}</span>
                            </div>
                          </div>
                          <span className="text-[10px] text-zinc-500 font-mono shrink-0 select-none bg-zinc-950 px-2 py-0.5 rounded border border-zinc-900">{(file.size / 1024).toFixed(2)} KB</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
              {/* Metric Card 3 */}
              <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm flex flex-col justify-between hover:border-gray-200 transition-colors duration-200">
                <span className="text-[10px] uppercase tracking-wider text-gray-400 font-bold font-sans">Session Messages</span>
                <div className="mt-4 flex items-baseline justify-between">
                  <span className="text-base font-bold text-gray-900 font-sans">{messages.length}</span>
                  <span className="text-[10px] text-gray-400 font-bold font-sans">TOTAL</span>
                </div>

                <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-6 shadow-sm flex flex-col h-[280px]">
                  <div className="flex justify-between items-center mb-4 shrink-0">
                    <div>
                      <h3 className="text-sm font-bold text-zinc-100">Smart File Memory Indexer</h3>
                      <p className="text-xs text-zinc-400 mt-0.5">Workspace Files in C:\Users\Public\JarvisWorkspace</p>
                    </div>
                    <button
                      onClick={fetchWorkspaceFiles}
                      className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 hover:underline cursor-pointer"
                    >
                      Sync Index
                    </button>
                  </div>
                  
                  <div className="flex-1 overflow-y-auto space-y-2 pr-1 text-[11px] font-medium scrollbar-thin">
                    {files.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center text-zinc-550 border border-dashed border-zinc-850/60 p-4 rounded-xl">
                        <span className="italic block font-mono text-[10px]">[ INDEX EMPTY ]</span>
                        <span className="block mt-1 leading-relaxed text-zinc-500">No memory files found inside the workspace namespace. Ask the assistant to write notes or create files to populate.</span>
                      </div>
                    ) : (
                      files.map(file => (
                        <div key={file.name} className="flex justify-between items-center p-2.5 bg-zinc-900/30 border border-zinc-850/60 hover:border-zinc-700/60 rounded-xl transition-all duration-150">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span className="w-2 h-2 rounded bg-indigo-500 shrink-0"></span>
                            <div className="min-w-0">
                              <span className="font-mono text-zinc-200 block truncate text-xs">{file.name}</span>
                              <span className="text-[10px] text-zinc-550 block font-mono mt-0.5">{new Date(file.modified).toLocaleTimeString()}</span>
                            </div>
                          </div>
                          <span className="text-[10px] text-zinc-500 font-mono shrink-0 select-none bg-zinc-950 px-2 py-0.5 rounded border border-zinc-900">{(file.size / 1024).toFixed(2)} KB</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
              {/* Metric Card 4 */}
              <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm flex flex-col justify-between hover:border-gray-200 transition-colors duration-200">
                <span className="text-[10px] uppercase tracking-wider text-gray-400 font-bold font-sans">Operator Session</span>
                <div className="mt-4 flex items-baseline justify-between">
                  <span className="text-base font-bold text-gray-900 truncate block max-w-[150px] font-sans">{user.name ? user.name.split(' ')[0] : 'Operator'}</span>
                  <span className="text-[10px] text-indigo-600 font-bold font-sans">AUTHENTICATED</span>
                </div>

                <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-6 shadow-sm flex flex-col h-[280px]">
                  <div className="flex justify-between items-center mb-4 shrink-0">
                    <div>
                      <h3 className="text-sm font-bold text-zinc-100">Smart File Memory Indexer</h3>
                      <p className="text-xs text-zinc-400 mt-0.5">Workspace Files in C:\Users\Public\JarvisWorkspace</p>
                    </div>
                    <button
                      onClick={fetchWorkspaceFiles}
                      className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 hover:underline cursor-pointer"
                    >
                      Sync Index
                    </button>
                  </div>
                  
                  <div className="flex-1 overflow-y-auto space-y-2 pr-1 text-[11px] font-medium scrollbar-thin">
                    {files.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center text-zinc-550 border border-dashed border-zinc-850/60 p-4 rounded-xl">
                        <span className="italic block font-mono text-[10px]">[ INDEX EMPTY ]</span>
                        <span className="block mt-1 leading-relaxed text-zinc-500">No memory files found inside the workspace namespace. Ask the assistant to write notes or create files to populate.</span>
                      </div>
                    ) : (
                      files.map(file => (
                        <div key={file.name} className="flex justify-between items-center p-2.5 bg-zinc-900/30 border border-zinc-850/60 hover:border-zinc-700/60 rounded-xl transition-all duration-150">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span className="w-2 h-2 rounded bg-indigo-500 shrink-0"></span>
                            <div className="min-w-0">
                              <span className="font-mono text-zinc-200 block truncate text-xs">{file.name}</span>
                              <span className="text-[10px] text-zinc-550 block font-mono mt-0.5">{new Date(file.modified).toLocaleTimeString()}</span>
                            </div>
                          </div>
                          <span className="text-[10px] text-zinc-500 font-mono shrink-0 select-none bg-zinc-950 px-2 py-0.5 rounded border border-zinc-900">{(file.size / 1024).toFixed(2)} KB</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Dashboard Contents Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Left Main Card: Quick Operations */}
              <div className="lg:col-span-2 space-y-6">
                <div className="bg-white border border-gray-100 rounded-xl p-6 shadow-sm">
                  <div className="mb-5">
                    <h3 className="text-sm font-bold text-gray-900 font-sans">System Integration Controls</h3>
                    <p className="text-xs text-gray-400 mt-0.5 font-sans">Automate active workspace sessions with direct process mapping.</p>
                  </div>
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <button 
                      onClick={() => handleQuickAction('Launch Notepad')} 
                      className="flex flex-col items-start justify-between gap-1 p-4 bg-gray-50/40 hover:bg-indigo-50/20 border border-gray-100 hover:border-indigo-100 rounded-xl transition-all duration-200 text-left group cursor-pointer"
                    >
                      <span className="text-[9px] uppercase tracking-wider text-gray-400 group-hover:text-indigo-500 font-bold transition-colors">Launch</span>
                      <span className="text-xs font-bold text-gray-700 group-hover:text-indigo-700 transition-colors">Notepad</span>
                    </button>
                    
                    <button 
                      onClick={() => handleQuickAction('Take a screenshot')} 
                      className="flex flex-col items-start justify-between gap-1 p-4 bg-gray-50/40 hover:bg-indigo-50/20 border border-gray-100 hover:border-indigo-100 rounded-xl transition-all duration-200 text-left group cursor-pointer"
                    >
                      <span className="text-[9px] uppercase tracking-wider text-gray-400 group-hover:text-indigo-500 font-bold transition-colors">Capture</span>
                      <span className="text-xs font-bold text-gray-700 group-hover:text-indigo-700 transition-colors">Screenshot</span>
                    </button>
                    
                    <button 
                      onClick={() => handleQuickAction('Volume Mute')} 
                      className="flex flex-col items-start justify-between gap-1 p-4 bg-gray-50/40 hover:bg-indigo-50/20 border border-gray-100 hover:border-indigo-100 rounded-xl transition-all duration-200 text-left group cursor-pointer"
                    >
                      <span className="text-[9px] uppercase tracking-wider text-gray-400 group-hover:text-indigo-500 font-bold transition-colors">Audio Control</span>
                      <span className="text-xs font-bold text-gray-700 group-hover:text-indigo-700 transition-colors">Volume Mute</span>
                    </button>
                    
                    <button 
                      onClick={() => handleQuickAction('Launch Calculator')} 
                      className="flex flex-col items-start justify-between gap-1 p-4 bg-gray-50/40 hover:bg-indigo-50/20 border border-gray-100 hover:border-indigo-100 rounded-xl transition-all duration-200 text-left group cursor-pointer"
                    >
                      <span className="text-[9px] uppercase tracking-wider text-gray-400 group-hover:text-indigo-500 font-bold transition-colors">Launch</span>
                      <span className="text-xs font-bold text-gray-700 group-hover:text-indigo-700 transition-colors">Calculator</span>
                    </button>
                  </div>
                </div>

                <div className="bg-white border border-gray-100 rounded-xl p-6 shadow-sm">
                  <h3 className="text-sm font-bold text-gray-900 mb-2">Natural Language Instructions</h3>
                  <p className="text-xs text-gray-500 leading-relaxed font-medium">
                    Jarvis integrates with local resources using natural command routing. 
                    Ask the assistant to automate workflows:
                  </p>
                  <ul className="mt-3.5 space-y-2 text-xs text-gray-500 font-medium">
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                      <span>"Open edge browser for me"</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                      <span>"Mute volume" or "Turn up the sound"</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                      <span>"Launch notepad and screenshot"</span>
                    </li>
                  </ul>
                </div>

                <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-6 shadow-sm flex flex-col h-[280px]">
                  <div className="flex justify-between items-center mb-4 shrink-0">
                    <div>
                      <h3 className="text-sm font-bold text-zinc-100">Smart File Memory Indexer</h3>
                      <p className="text-xs text-zinc-400 mt-0.5">Workspace Files in C:\Users\Public\JarvisWorkspace</p>
                    </div>
                    <button
                      onClick={fetchWorkspaceFiles}
                      className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 hover:underline cursor-pointer"
                    >
                      Sync Index
                    </button>
                  </div>
                  
                  <div className="flex-1 overflow-y-auto space-y-2 pr-1 text-[11px] font-medium scrollbar-thin">
                    {files.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center text-zinc-550 border border-dashed border-zinc-850/60 p-4 rounded-xl">
                        <span className="italic block font-mono text-[10px]">[ INDEX EMPTY ]</span>
                        <span className="block mt-1 leading-relaxed text-zinc-500">No memory files found inside the workspace namespace. Ask the assistant to write notes or create files to populate.</span>
                      </div>
                    ) : (
                      files.map(file => (
                        <div key={file.name} className="flex justify-between items-center p-2.5 bg-zinc-900/30 border border-zinc-850/60 hover:border-zinc-700/60 rounded-xl transition-all duration-150">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span className="w-2 h-2 rounded bg-indigo-500 shrink-0"></span>
                            <div className="min-w-0">
                              <span className="font-mono text-zinc-200 block truncate text-xs">{file.name}</span>
                              <span className="text-[10px] text-zinc-550 block font-mono mt-0.5">{new Date(file.modified).toLocaleTimeString()}</span>
                            </div>
                          </div>
                          <span className="text-[10px] text-zinc-500 font-mono shrink-0 select-none bg-zinc-950 px-2 py-0.5 rounded border border-zinc-900">{(file.size / 1024).toFixed(2)} KB</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* Event Logger Card */}
              <div className="bg-white border border-gray-100 rounded-xl shadow-sm flex flex-col h-[400px]">
                <div className="px-5 py-4 border-b border-gray-100 flex justify-between items-center shrink-0">
                  <div>
                    <h3 className="text-xs font-bold text-gray-900">Event Logger</h3>
                    <p className="text-[10px] text-gray-400 mt-0.5">Real-time console stream</p>
                  </div>
                  <button 
                    onClick={() => setLogs([])}
                    className="text-[10px] font-bold text-gray-400 hover:text-gray-900 hover:bg-gray-50 px-2 py-1 rounded transition-colors cursor-pointer"
                  >
                    Clear
                  </button>
                </div>
                <div 
                  id="log-container"
                  className="flex-1 overflow-y-auto p-5 font-mono text-[10px] leading-relaxed bg-[#0c0d0f] text-gray-300 rounded-b-xl space-y-2.5 scrollbar-thin"
                >
                  {logs.length === 0 ? (
                    <span className="text-gray-500 italic block">Awaiting system events...</span>
                  ) : (
                    logs.map(log => (
                      <div key={log.id} className="flex gap-2 items-start break-all border-b border-gray-900/60 pb-1.5">
                        <span className="text-gray-600 shrink-0 select-none">[{new Date(log.id).toLocaleTimeString()}]</span>
                        <span className={
                          log.type === 'error' ? 'text-rose-400 font-semibold' :
                          log.type === 'success' ? 'text-emerald-400 font-semibold' :
                          'text-indigo-300 font-semibold'
                        }>{log.message}</span>
                      </div>
                    ))
                  )}
                </div>

                <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-6 shadow-sm flex flex-col h-[280px]">
                  <div className="flex justify-between items-center mb-4 shrink-0">
                    <div>
                      <h3 className="text-sm font-bold text-zinc-100">Smart File Memory Indexer</h3>
                      <p className="text-xs text-zinc-400 mt-0.5">Workspace Files in C:\Users\Public\JarvisWorkspace</p>
                    </div>
                    <button
                      onClick={fetchWorkspaceFiles}
                      className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 hover:underline cursor-pointer"
                    >
                      Sync Index
                    </button>
                  </div>
                  
                  <div className="flex-1 overflow-y-auto space-y-2 pr-1 text-[11px] font-medium scrollbar-thin">
                    {files.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center text-zinc-550 border border-dashed border-zinc-850/60 p-4 rounded-xl">
                        <span className="italic block font-mono text-[10px]">[ INDEX EMPTY ]</span>
                        <span className="block mt-1 leading-relaxed text-zinc-500">No memory files found inside the workspace namespace. Ask the assistant to write notes or create files to populate.</span>
                      </div>
                    ) : (
                      files.map(file => (
                        <div key={file.name} className="flex justify-between items-center p-2.5 bg-zinc-900/30 border border-zinc-850/60 hover:border-zinc-700/60 rounded-xl transition-all duration-150">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span className="w-2 h-2 rounded bg-indigo-500 shrink-0"></span>
                            <div className="min-w-0">
                              <span className="font-mono text-zinc-200 block truncate text-xs">{file.name}</span>
                              <span className="text-[10px] text-zinc-550 block font-mono mt-0.5">{new Date(file.modified).toLocaleTimeString()}</span>
                            </div>
                          </div>
                          <span className="text-[10px] text-zinc-500 font-mono shrink-0 select-none bg-zinc-950 px-2 py-0.5 rounded border border-zinc-900">{(file.size / 1024).toFixed(2)} KB</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      case 'assistant':
        return (
          <div className="flex flex-col h-[calc(100vh-12rem)] min-h-[500px] max-w-5xl mx-auto">
            {/* Chat header */}
            <div className="px-2 py-4 border-b border-zinc-800/60 flex justify-between items-center shrink-0 text-white">
              <div>
                <h3 className="text-sm font-bold text-zinc-100 font-sans">AI Assistant Copilot</h3>
                <p className="text-xs text-zinc-400 mt-0.5 font-sans">Execute desktop automation through natural language.</p>
              </div>
              <span className="text-[10px] px-2.5 py-1 bg-zinc-900 border border-zinc-800/60 rounded-full font-mono font-bold text-emerald-400">
                ACTIVE
              </span>
            </div>

            {/* Chat Message Stream */}
            <div className="flex-1 overflow-y-auto py-6 space-y-6 flex flex-col bg-transparent">
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-8">
                  <div className="w-12 h-12 rounded-full bg-zinc-900 flex items-center justify-center text-zinc-400 mb-4 border border-zinc-850">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  </div>
                  <h4 className="text-xs font-mono font-bold text-zinc-300 uppercase tracking-wider">No active logs</h4>
                  <p className="text-[11px] text-zinc-500 max-w-xs mt-1 leading-relaxed font-medium">Submit a command using the execution portal below to begin system dispatches.</p>
                </div>
              ) : (
                messages.map((msg, idx) => (
                  <div key={idx} className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'} w-full`}>
                    {msg.sender === 'user' ? (
                      <div className="bg-zinc-900 text-zinc-100 rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-[85%] text-sm self-end shadow-sm leading-relaxed whitespace-pre-wrap font-sans">
                        {msg.text}
                      </div>
                    ) : (
                      <div className="flex flex-col items-start space-y-2 w-full">
                        {(msg.intent || msg.execution_type) && (
                          <div className="flex flex-wrap gap-2 pl-1">
                            {msg.intent && (
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[9px] font-mono font-bold bg-zinc-900 text-zinc-400 border border-zinc-800 uppercase tracking-widest">
                                [{msg.intent.replace(/_/g, ' ')}]
                              </span>
                            )}
                            {msg.execution_type && msg.execution_type !== 'NONE' && (
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[9px] font-mono font-bold uppercase tracking-widest border ${
                                msg.execution_type === 'SHELL_COMMAND'
                                  ? 'bg-emerald-950/40 text-emerald-400 border-emerald-900/40'
                                  : msg.execution_type === 'BROWSER_URL'
                                  ? 'bg-sky-950/40 text-sky-400 border-sky-900/40'
                                  : msg.execution_type === 'PYTHON_SCRIPT'
                                  ? 'bg-amber-950/40 text-amber-400 border-amber-900/40'
                                  : 'bg-indigo-950/40 text-indigo-400 border-indigo-900/30'
                              }`}>
                                [{msg.execution_type.replace(/_/g, ' ')}]
                              </span>
                            )}
                          </div>
                        )}
                        {msg.payload && (
                          <div className="pl-1 max-w-[90%]">
                            <code className="inline-block text-[10px] font-mono text-zinc-400 bg-zinc-900/80 border border-zinc-800 rounded-lg px-3 py-1.5 break-all leading-snug">
                              $ {msg.payload}
                            </code>
                          </div>
                        )}
                        <div className="text-zinc-200 text-sm font-sans leading-relaxed whitespace-pre-wrap pl-1 max-w-[85%]">
                          {msg.text}
                        </div>
                      </div>
                    )}
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Chat Input Console */}
            <div className="py-4 bg-transparent shrink-0">
              <div className="relative flex items-center max-w-4xl mx-auto w-full">
                <textarea
                  rows="1"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder="Ask Jarvis to automate your desktop..."
                  className="w-full bg-zinc-900 border border-zinc-800 text-sm text-zinc-100 rounded-xl pl-4 pr-12 py-3 focus:border-zinc-700 focus:ring-0 focus:outline-none transition-all placeholder-zinc-500 font-sans resize-none min-h-[44px] max-h-[120px] scrollbar-thin"
                  style={{ height: 'auto' }}
                />
                <button
                  id="send-btn"
                  onClick={handleSend}
                  className="absolute right-3 p-1.5 rounded-full text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-all cursor-pointer active:scale-95 shrink-0"
                  title="Send message"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9-2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        );
      case 'settings':
        return (
          <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-6 shadow-sm space-y-6 max-w-7xl">
            <div>
              <h3 className="text-sm font-bold text-zinc-100">Desktop System Mappings</h3>
              <p className="text-xs text-zinc-400 mt-1 font-sans">Preset automation route records configured locally.</p>
            </div>

            <div className="border border-zinc-800/60 rounded-xl overflow-hidden shadow-sm">
              <table className="w-full text-left text-[11px] border-collapse font-medium">
                <thead>
                  <tr className="bg-zinc-900/30 border-b border-zinc-800/60 text-zinc-400 font-bold">
                    <th className="px-5 py-3">Alias</th>
                    <th className="px-5 py-3">Binary File Location / System Call</th>
                    <th className="px-5 py-3">Type</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                  <tr>
                    <td className="px-5 py-3 font-semibold text-zinc-100">notepad</td>
                    <td className="px-5 py-3 font-mono text-zinc-400">notepad.exe</td>
                    <td className="px-5 py-3"><span className="px-2 py-0.5 bg-zinc-900 text-zinc-500 rounded text-[9px] font-bold border border-zinc-800">DEFAULT SYSTEM ROUTE</span></td>
                  </tr>
                  <tr>
                    <td className="px-5 py-3 font-semibold text-zinc-100">calculator</td>
                    <td className="px-5 py-3 font-mono text-zinc-400">calc.exe</td>
                    <td className="px-5 py-3"><span className="px-2 py-0.5 bg-zinc-900 text-zinc-500 rounded text-[9px] font-bold border border-zinc-800">DEFAULT SYSTEM ROUTE</span></td>
                  </tr>
                  <tr>
                    <td className="px-5 py-3 font-semibold text-zinc-100">paint</td>
                    <td className="px-5 py-3 font-mono text-zinc-400">mspaint.exe</td>
                    <td className="px-5 py-3"><span className="px-2 py-0.5 bg-zinc-900 text-zinc-500 rounded text-[9px] font-bold border border-zinc-800">DEFAULT SYSTEM ROUTE</span></td>
                  </tr>
                  <tr>
                    <td className="px-5 py-3 font-semibold text-zinc-100">browser</td>
                    <td className="px-5 py-3 font-mono text-zinc-400">msedge.exe</td>
                    <td className="px-5 py-3"><span className="px-2 py-0.5 bg-zinc-900 text-zinc-500 rounded text-[9px] font-bold border border-zinc-800">DEFAULT SYSTEM ROUTE</span></td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="p-4 bg-zinc-900/30 border border-zinc-800/60 rounded-xl text-xs text-zinc-400 leading-relaxed font-medium">
              <span className="font-bold text-zinc-200 block mb-1 font-sans">💡 Custom Application Registration</span>
              To add a custom mapping, register it in the backend's SQLAlchemy database. Jarvis automatically looks up your custom mapped tables before executing default process presets.
            </div>
          </div>
        );
      case 'profile':
        return (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 max-w-7xl">
            <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-6 shadow-sm flex flex-col items-center text-center">
              {user.picture ? (
                <img
                  src={user.picture}
                  alt={user.name || 'User'}
                  className="w-16 h-16 rounded-full object-cover border border-zinc-800 shadow-sm"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className="w-16 h-16 rounded-full bg-zinc-800 text-zinc-100 flex items-center justify-center font-bold text-xl border border-zinc-700">
                  {user.name ? user.name.charAt(0).toUpperCase() : 'U'}
                </div>
              )}
              <h3 className="text-sm font-bold text-zinc-100 mt-4">{user.name || 'Operator'}</h3>
              <p className="text-[11px] text-zinc-500 font-medium mt-0.5">{user.email || 'operator@jarvis.local'}</p>
              
              <div className="w-full border-t border-zinc-800/60 mt-6 pt-5">
                <button
                  onClick={handleLogout}
                  className="w-full text-center bg-rose-950/20 hover:bg-rose-900/30 text-rose-450 border border-rose-900/30 rounded-lg py-2 text-xs font-bold transition-colors duration-150 cursor-pointer"
                >
                  Terminate Active Session
                </button>
              </div>
            </div>

            <div className="lg:col-span-2 bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-6 shadow-sm space-y-5">
              <h3 className="text-xs font-bold text-zinc-100 uppercase tracking-wider border-b border-zinc-800 pb-3 font-sans">Session Metadata</h3>
              
              <div className="space-y-4 text-xs font-medium">
                <div className="grid grid-cols-3 gap-2">
                  <span className="text-zinc-500">Authenticated Provider</span>
                  <span className="col-span-2 text-zinc-300">Google accounts identity provider</span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <span className="text-zinc-500">Google Client ID</span>
                  <span className="col-span-2 text-zinc-450 font-mono break-all text-[10px]">{googleClientId || 'Null Configuration'}</span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <span className="text-zinc-500">Application JWT</span>
                  <span className="col-span-2 font-mono text-[9px] break-all bg-zinc-900/50 border border-zinc-800/60 p-3 rounded-lg block max-h-32 overflow-y-auto text-zinc-400">
                    {token}
                  </span>
                </div>

                <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-xl p-6 shadow-sm flex flex-col h-[280px]">
                  <div className="flex justify-between items-center mb-4 shrink-0">
                    <div>
                      <h3 className="text-sm font-bold text-zinc-100">Smart File Memory Indexer</h3>
                      <p className="text-xs text-zinc-400 mt-0.5">Workspace Files in C:\Users\Public\JarvisWorkspace</p>
                    </div>
                    <button
                      onClick={fetchWorkspaceFiles}
                      className="text-[10px] font-bold text-indigo-400 hover:text-indigo-300 hover:underline cursor-pointer"
                    >
                      Sync Index
                    </button>
                  </div>
                  
                  <div className="flex-1 overflow-y-auto space-y-2 pr-1 text-[11px] font-medium scrollbar-thin">
                    {files.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center text-zinc-550 border border-dashed border-zinc-850/60 p-4 rounded-xl">
                        <span className="italic block font-mono text-[10px]">[ INDEX EMPTY ]</span>
                        <span className="block mt-1 leading-relaxed text-zinc-500">No memory files found inside the workspace namespace. Ask the assistant to write notes or create files to populate.</span>
                      </div>
                    ) : (
                      files.map(file => (
                        <div key={file.name} className="flex justify-between items-center p-2.5 bg-zinc-900/30 border border-zinc-850/60 hover:border-zinc-700/60 rounded-xl transition-all duration-150">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <span className="w-2 h-2 rounded bg-indigo-500 shrink-0"></span>
                            <div className="min-w-0">
                              <span className="font-mono text-zinc-200 block truncate text-xs">{file.name}</span>
                              <span className="text-[10px] text-zinc-550 block font-mono mt-0.5">{new Date(file.modified).toLocaleTimeString()}</span>
                            </div>
                          </div>
                          <span className="text-[10px] text-zinc-500 font-mono shrink-0 select-none bg-zinc-950 px-2 py-0.5 rounded border border-zinc-900">{(file.size / 1024).toFixed(2)} KB</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  if (isOverlayOpen && isAuthenticated) {
    return (
      <div className="fixed inset-0 z-50 bg-zinc-950 text-zinc-100" onClick={() => setIsOverlayOpen(false)}>
        <div className="absolute inset-0 bg-zinc-950/95 backdrop-blur-sm" />
        <div className="flex min-h-screen flex-col justify-end px-4 pb-8" onClick={(e) => e.stopPropagation()}>
          <div className="w-full max-w-5xl mx-auto mb-24 px-6 py-4 rounded-3xl border border-zinc-800/60 bg-zinc-900/70 shadow-2xl shadow-black/40 backdrop-blur-md">
            <div className="flex flex-col gap-2 text-center">
              <p className="text-[10px] uppercase tracking-[0.32em] text-zinc-500 font-semibold">Jarvis Command Canvas</p>
              <h1 className="text-xl font-bold text-white">Minimal desktop dispatch interface</h1>
              <p className="text-sm text-zinc-400">Use the pill bar below to issue a command or quick system task.</p>
            </div>
          </div>

          <div className="fixed bottom-0 left-0 right-0 z-50 flex justify-center px-4 pb-6">
            <div className="w-full max-w-2xl rounded-full border border-zinc-800/80 bg-zinc-900/95 px-4 py-3 shadow-2xl shadow-black/40 backdrop-blur-md flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <input
                    ref={overlayInputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    placeholder="Ask Jarvis.."
                    className="w-full bg-transparent border-none text-lg text-zinc-100 placeholder-zinc-500 focus:outline-none"
                  />
                </div>

                <button
                  type="button"
                  onClick={toggleVoiceRecognition}
                  disabled={!speechSupported}
                  className={`flex h-12 w-12 items-center justify-center rounded-full transition ${isListening ? 'bg-red-500/20 ring-2 ring-red-500 text-red-300 animate-pulse' : speechSupported ? 'bg-zinc-950/90 text-zinc-200 hover:bg-zinc-900' : 'bg-zinc-700/80 text-zinc-500 cursor-not-allowed'}`}
                  title={speechSupported ? (isListening ? 'Listening...' : 'Start voice input') : 'Voice recognition not supported'}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                    <path d="M12 1v11" />
                    <path d="M5 10a7 7 0 0014 0" />
                    <path d="M19 10v2a7 7 0 01-14 0v-2" />
                    <path d="M8 18.5a4 4 0 008 0" />
                  </svg>
                </button>

                <button
                  onClick={() => handleSend()}
                  className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-500 text-white shadow-lg shadow-blue-500/20 transition hover:bg-blue-400"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                    <path d="M5 12h14" />
                    <path d="M13 6l6 6-6 6" />
                  </svg>
                </button>
              </div>

              <div className="flex flex-wrap justify-between gap-3 text-[10px] text-zinc-500">
                <span>Ctrl + Space to toggle • Enter to submit • Esc to close</span>
                {!speechSupported && <span className="text-rose-400">Voice recognition not supported in this browser.</span>}
                {speechSupported && isListening && <span className="text-emerald-300">Listening... speak now.</span>}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-screen bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.08),transparent_25%),radial-gradient(circle_at_bottom_right,_rgba(168,85,247,0.1),transparent_20%),#020617] text-zinc-100 font-sans antialiased">
      <div className="mx-auto flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <p className="text-xs uppercase tracking-[0.4em] text-zinc-500 mb-4 font-semibold">Jarvis Command Canvas</p>
        <h1 className="text-5xl sm:text-6xl font-extrabold text-white mb-4">Minimal desktop launcher</h1>
        <p className="max-w-2xl text-sm leading-8 text-zinc-400">
          A calm, modern canvas for your Jarvis workflow. The command pill is already available below—type, speak, and send when ready.
        </p>
      </div>

      <div className="fixed bottom-0 left-0 right-0 z-50 flex justify-center px-4 pb-6">
        <div className="w-full max-w-2xl rounded-full border border-zinc-800/80 bg-zinc-900/95 px-4 py-3 shadow-2xl shadow-black/40 backdrop-blur-md flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <input
                ref={overlayInputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Ask Jarvis.."
                className="w-full bg-transparent border-none text-lg text-zinc-100 placeholder-zinc-500 focus:outline-none"
              />
            </div>

            <button
              type="button"
              onClick={toggleVoiceRecognition}
              disabled={!speechSupported}
              className={`flex h-12 w-12 items-center justify-center rounded-full transition ${isListening ? 'bg-red-500/20 ring-2 ring-red-500 text-red-300 animate-pulse' : speechSupported ? 'bg-zinc-950/90 text-zinc-200 hover:bg-zinc-900' : 'bg-zinc-700/80 text-zinc-500 cursor-not-allowed'}`}
              title={speechSupported ? (isListening ? 'Listening...' : 'Start voice input') : 'Voice recognition not supported'}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                <path d="M12 1v11" />
                <path d="M5 10a7 7 0 0014 0" />
                <path d="M19 10v2a7 7 0 01-14 0v-2" />
                <path d="M8 18.5a4 4 0 008 0" />
              </svg>
            </button>

            <button
              onClick={() => handleSend()}
              className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-500 text-white shadow-lg shadow-blue-500/20 transition hover:bg-blue-400"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                <path d="M5 12h14" />
                <path d="M13 6l6 6-6 6" />
              </svg>
            </button>
          </div>

          <div className="flex flex-wrap justify-between gap-3 text-[10px] text-zinc-500">
            {!speechSupported && <span className="text-rose-400">Voice recognition not supported in this browser.</span>}
            {speechSupported && isListening && <span className="text-emerald-300">Listening... speak now.</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
