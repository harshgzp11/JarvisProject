import sys

new_ui = """  return (
    <div className="flex h-screen bg-[#020617] text-zinc-100 font-sans overflow-hidden">
      {/* Left Sidebar */}
      <div className="w-16 md:w-64 bg-zinc-950/80 border-r border-zinc-800/50 flex flex-col justify-between shrink-0 transition-all duration-300 z-50 relative">
        <div className="p-3 md:p-4 space-y-6">
          {/* Logo Area */}
          <div className="flex items-center justify-center md:justify-start gap-3 px-1 md:px-2 cursor-pointer mb-2 group" onClick={() => setActiveTab('dashboard')}>
            <span className="text-white text-2xl font-extrabold select-none leading-none group-hover:scale-105 transition-transform">▲</span>
            <span className="font-bold tracking-widest text-sm uppercase hidden md:inline-block">Jarvis</span>
          </div>

          {/* New Chat / Home Button */}
          <button 
            onClick={() => {
               setMessages([]);
               setActiveTab('dashboard');
               setInput('');
            }}
            title="Home"
            className="w-full flex items-center justify-center md:justify-start gap-3 px-0 md:px-4 py-3 md:py-2.5 rounded-xl bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 transition-all text-sm font-semibold border border-indigo-500/20 cursor-pointer active:scale-95"
          >
            <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            <span className="hidden md:inline-block text-zinc-300">Home</span>
          </button>
        </div>

        {/* Bottom Section: Settings & Profile */}
        <div className="p-3 md:p-4 space-y-2 border-t border-zinc-800/40">
          <button 
            onClick={() => setActiveTab('settings')}
            title="Settings"
            className={`w-full flex items-center justify-center md:justify-start gap-3 px-0 md:px-4 py-3 md:py-2.5 rounded-xl transition-colors text-sm font-medium cursor-pointer ${activeTab === 'settings' ? 'bg-zinc-800/80 text-white' : 'text-zinc-400 hover:bg-zinc-900 hover:text-white'}`}
          >
            <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="hidden md:inline-block">Settings</span>
          </button>
          
          <button 
            onClick={() => setActiveTab('profile')}
            title="Profile"
            className={`w-full flex items-center justify-center md:justify-start gap-3 px-0 md:px-4 py-3 md:py-2.5 rounded-xl transition-colors text-sm font-medium cursor-pointer ${activeTab === 'profile' ? 'bg-zinc-800/80 text-white' : 'text-zinc-400 hover:bg-zinc-900 hover:text-white'}`}
          >
            {user.picture ? (
              <img src={user.picture} alt="Profile" className="w-6 h-6 rounded-full object-cover shrink-0 border border-zinc-700" />
            ) : (
              <div className="w-6 h-6 shrink-0 rounded-full bg-zinc-700 flex items-center justify-center text-[10px] font-bold text-white border border-zinc-600">
                {user.name ? user.name.charAt(0).toUpperCase() : 'U'}
              </div>
            )}
            <span className="hidden md:inline-block truncate max-w-[140px]">{user.name || 'Operator'}</span>
          </button>
        </div>
      </div>

      {/* Main Original UI Area */}
      <div className="flex-1 relative overflow-y-auto bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.08),transparent_25%),radial-gradient(circle_at_bottom_right,_rgba(168,85,247,0.1),transparent_20%),#020617] scrollbar-thin">
        
        {activeTab === 'dashboard' || activeTab === 'assistant' ? (
          <>
            <div className="mx-auto flex min-h-full flex-col items-center justify-center px-6 text-center pb-32">
              <p className="text-xs uppercase tracking-[0.4em] text-zinc-500 mb-4 font-semibold">Jarvis Command Canvas</p>
              <h1 className="text-5xl sm:text-6xl font-extrabold text-white mb-4">Minimal desktop launcher</h1>
              <p className="max-w-2xl text-sm leading-8 text-zinc-400">
                A calm, modern canvas for your Jarvis workflow. The command pill is already available below—type, speak, and send when ready.
              </p>
            </div>

            {/* Original Bottom Pill */}
            <div className="absolute bottom-0 left-0 right-0 flex justify-center px-4 pb-6 pointer-events-none z-40">
              <div className="w-full max-w-2xl rounded-full border border-zinc-800/80 bg-zinc-900/95 px-4 py-3 shadow-2xl shadow-black/40 backdrop-blur-md flex flex-col gap-3 pointer-events-auto">
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
          </>
        ) : (
          <div className="max-w-7xl mx-auto px-4 md:px-8 py-8 min-h-full bg-zinc-950/40">
             {renderTabContent()}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
"""

with open('src/App.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

out = []
found_split = False
for i, line in enumerate(lines):
    # We want to keep everything before the final `return (` 
    if line.startswith('  return (') and 'min-h-screen w-screen bg-[radial-gradient' in lines[i+1]:
        found_split = True
        break
    out.append(line)

if not found_split:
    print('Failed to find split point')
    sys.exit(1)

out.append(new_ui)

with open('src/App.jsx', 'w', encoding='utf-8') as f:
    f.writelines(out)

print('Successfully applied sidebar to original UI')
