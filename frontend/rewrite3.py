import sys

new_sidebar = """      {/* Left Minimal Icon Sidebar */}
      <div className="w-[68px] flex flex-col items-center justify-between shrink-0 transition-all duration-300 z-50 py-4 bg-[#1e1f22]/50 border-r border-white/5">
        <div className="flex flex-col items-center gap-5 w-full">
          {/* Top Logo Area (Sparkle) */}
          <button 
            onClick={() => setActiveTab('dashboard')} 
            title="Jarvis" 
            className="cursor-pointer mb-2 hover:bg-white/10 transition-colors flex items-center justify-center w-11 h-11 rounded-full text-indigo-400"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6">
               <path d="M12 2l2.4 7.6H22l-6.2 4.5 2.4 7.6-6.2-4.5-6.2 4.5 2.4-7.6L2 9.6h7.6L12 2z" />
            </svg>
          </button>

          {/* Minimal Icon Nav Items */}
          <button 
            onClick={() => { setMessages([]); setInput(''); setActiveTab('dashboard'); }} 
            title="New Chat" 
            className="flex items-center justify-center w-10 h-10 rounded-full transition-colors text-zinc-400 hover:bg-white/10 hover:text-zinc-200"
          >
             <svg className="w-[22px] h-[22px]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
          </button>
          
          <button 
            onClick={() => setActiveTab('assistant')} 
            title="Search / Assistant" 
            className={`flex items-center justify-center w-10 h-10 rounded-full transition-colors ${activeTab === 'assistant' ? 'bg-white/10 text-white' : 'text-zinc-400 hover:bg-white/10 hover:text-zinc-200'}`}
          >
             <svg className="w-[22px] h-[22px]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          </button>
          
          <button 
            onClick={() => setActiveTab('dashboard')} 
            title="Gallery" 
            className="flex items-center justify-center w-10 h-10 rounded-full transition-colors text-zinc-400 hover:bg-white/10 hover:text-zinc-200"
          >
             <svg className="w-[22px] h-[22px]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
          </button>

          <button 
            onClick={() => setActiveTab('dashboard')} 
            title="Files" 
            className="flex items-center justify-center w-10 h-10 rounded-full transition-colors text-zinc-400 hover:bg-white/10 hover:text-zinc-200"
          >
             <svg className="w-[22px] h-[22px]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" /></svg>
          </button>
          
          <button 
            onClick={() => setActiveTab('dashboard')} 
            title="Apps" 
            className="flex items-center justify-center w-10 h-10 rounded-full transition-colors text-zinc-400 hover:bg-white/10 hover:text-zinc-200"
          >
             <svg className="w-[22px] h-[22px]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2v-4zM14 16a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2v-4z" /></svg>
          </button>
        </div>

        {/* Bottom Section: Settings & Profile */}
        <div className="flex flex-col items-center gap-3 w-full">
          <button 
            onClick={() => setActiveTab('settings')} 
            title="Settings" 
            className={`flex items-center justify-center w-10 h-10 rounded-full transition-colors ${activeTab === 'settings' ? 'bg-white/10 text-white' : 'text-zinc-400 hover:bg-white/10 hover:text-zinc-200'}`}
          >
            <svg className="w-[22px] h-[22px]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
          
          <button 
            onClick={() => setActiveTab('profile')} 
            title="Profile" 
            className={`flex items-center justify-center w-[30px] h-[30px] rounded-full transition-colors mb-2 ${activeTab === 'profile' ? 'ring-2 ring-white/20 ring-offset-2 ring-offset-[#131314]' : ''}`}
          >
            {user.picture ? (
              <img src={user.picture} alt="Profile" className="w-full h-full rounded-full object-cover" />
            ) : (
              <div className="w-full h-full rounded-full bg-[#3b4b5e] flex items-center justify-center text-[11px] font-semibold text-white/90">
                {user.name ? user.name.charAt(0).toUpperCase() : 'H'}
              </div>
            )}
          </button>
        </div>
      </div>"""

with open('src/App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the start of the sidebar and the start of the main original UI area
start_marker = "{/* Left Sidebar */}"
end_marker = "{/* Main Original UI Area */}"

if start_marker in content and end_marker in content:
    before = content.split(start_marker)[0]
    after = content.split(end_marker)[1]
    
    # Also change the overall app background to a more solid gemini-like dark grey
    before = before.replace('bg-[#020617]', 'bg-[#131314]')
    
    # And replace the main area gradient with solid dark color too, to match Gemini
    after = after.replace('bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.08),transparent_25%),radial-gradient(circle_at_bottom_right,_rgba(168,85,247,0.1),transparent_20%),#020617]', 'bg-[#131314]')
    
    new_content = before + new_sidebar + "\\n\\n      {/* Main Original UI Area */}" + after
    
    with open('src/App.jsx', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Sidebar replaced successfully.")
else:
    print("Could not find markers!")
    sys.exit(1)
